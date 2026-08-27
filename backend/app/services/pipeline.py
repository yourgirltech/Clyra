"""Orchestrates the real claim-lifecycle pipeline through Commander for one
claim: generating a recommendation (01 -> 02 -> 03, each dispatched via
`app.agents.dispatch.route_and_dispatch`, never called directly), and
recording a human's approve/decline decision on the result (rule 3/5/14-16).

This is the seam that makes Human Review real: everything upstream of this
module (Commander, 01-06) already existed as pure functions with no caller
wiring them together end to end. `generate_recommendation` and
`decide_recommendation` are that caller.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import anthropic
from sqlalchemy.orm import Session

from app import models
from app.agents.analyzer import AnalyzerResult
from app.agents.commander import (
    AGENT_ESCALATION,
    AGENT_FOLLOWUP,
    AGENT_REMINDER,
    NO_ACTION,
    CommanderDecision,
)
from app.agents.dispatch import route_and_dispatch
from app.agents.escalation import EscalationResult
from app.agents.followup import FollowUpFailure, FollowUpResult
from app.agents.reasoning import ReasoningFailure, ReasoningResult
from app.agents.recommendation import RecommendationFailure, RecommendationResult
from app.agents.reminder import ReminderFailure, ReminderResult

DEFAULT_APPROVER = "A. Carter"  # no auth system yet — see app.api.routes.claims.get_current_clinic

logger = logging.getLogger("clyra.pipeline")

# Recommendation.approval_status values. "escalated" is a DB/UI-only detail —
# Commander's own vocabulary (docs/agents/00-commander.md) is only
# pending|approved|declined|none, so it's mapped to "none" whenever this
# module talks to Commander (see `_commander_approval_status`).
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_DECLINED = "declined"
STATUS_ESCALATED = "escalated"


@dataclass(frozen=True)
class PipelineOutcome:
    stage: str  # "no_action" | "pending" | "escalated"
    recommendation: Optional[models.Recommendation]
    escalation: Optional[EscalationResult]
    decision: Optional[CommanderDecision]
    detail: str = ""


@dataclass(frozen=True)
class DecisionOutcome:
    recommendation: models.Recommendation
    decision: CommanderDecision  # the rule 5/14/15/16/20 routing decision for the approve/decline itself
    execution: Optional[Union[FollowUpResult, FollowUpFailure, ReminderResult, ReminderFailure]]
    execution_decision: Optional[CommanderDecision]  # rule 17/18/19, set only when 04/05 actually ran
    escalation: Optional[EscalationResult]  # set whenever any hop above resulted in an escalation
    activity: models.ActivityLog


def _commander_approval_status(db_status: str) -> str:
    if db_status in ("pending", "approved", "declined"):
        return db_status
    return "none"


def build_claim_state(db: Session, claim: models.Claim) -> dict:
    """Assemble Commander's read-only claim-state snapshot from the DB —
    the seam Commander's own docs describe as "the caller's responsibility"."""
    latest_rec = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.claim_id == claim.id)
        .order_by(models.Recommendation.created_at.desc(), models.Recommendation.id.desc())
        .first()
    )
    latest_recommendation = None
    if latest_rec is not None:
        latest_recommendation = {
            "id": latest_rec.id,
            "action_type": latest_rec.action_type,
            "confidence_band": latest_rec.confidence,
            "low_confidence": bool(latest_rec.low_confidence),
            "approval_status": _commander_approval_status(latest_rec.approval_status),
        }

    issues = db.query(models.ClaimIssue).filter(models.ClaimIssue.claim_id == claim.id).all()
    latest_issues = [
        {"issue_type": i.issue_type, "severity": i.severity, "description": i.description}
        for i in issues
    ]

    return {
        "claim_id": claim.claim_id,
        "status": claim.status,
        "risk_score": claim.risk_score,
        "risk_level": claim.risk_level,
        "latest_issues": latest_issues,
        "latest_recommendation": latest_recommendation,
        # No concurrency/run tracking exists yet — every invocation is
        # synchronous end-to-end, so there is never a run genuinely "in
        # progress" when the next request is evaluated.
        "agent_run_in_progress": False,
    }


def _persist_issues_and_risk(db: Session, claim: models.Claim, analysis: AnalyzerResult) -> None:
    db.query(models.ClaimIssue).filter(models.ClaimIssue.claim_id == claim.id).delete()
    for issue in analysis.issues:
        db.add(
            models.ClaimIssue(
                claim_id=claim.id,
                issue_type=issue.issue_type,
                severity=issue.severity,
                description=issue.description,
                evidence=str(issue.evidence),
            )
        )
    claim.risk_score = analysis.risk_score
    claim.risk_level = analysis.risk_level
    db.add(claim)
    db.commit()


def generate_recommendation(
    db: Session,
    claim: models.Claim,
    *,
    anthropic_client: Optional[anthropic.Anthropic] = None,
) -> PipelineOutcome:
    """Run the real Commander-routed chain for one claim: 01-analyzer-agent
    -> 02-reasoning-agent -> 03-recommendation-agent, persisting a pending
    Recommendation row for a human to act on (rule 12), or escalating
    immediately if 03 reports low confidence (rule 13) or any stage fails
    (rules 7/9/11).

    Refuses to start a second run while one recommendation is already
    pending (rule 3) — Commander itself enforces this, not a guard bolted
    on here.
    """
    payer = claim.payer
    follow_ups = db.query(models.FollowUp).filter(models.FollowUp.claim_id == claim.id).all()
    claim_evidence = {
        "authorization_present": int(claim.authorization_present),
        "documentation_present": int(claim.documentation_present),
        "coding_matches": int(claim.coding_matches),
        "last_followup_at": claim.last_followup_at,
    }
    payer_config = {
        "authorization_required": int(getattr(payer, "authorization_required", 0)),
        "documentation_required": int(getattr(payer, "documentation_required", 0)),
        "follow_up_threshold_days": int(getattr(payer, "follow_up_threshold_days", 30)),
    }
    follow_up_dicts = [{"due_at": f.due_at} for f in follow_ups]

    # --- 01-analyzer-agent, via Commander rule 6 ---
    claim_state = build_claim_state(db, claim)
    decision, result = route_and_dispatch(
        claim_state,
        {"type": "claim_evidence_updated", "payload": {}},
        claim_evidence=claim_evidence,
        payer_config=payer_config,
        follow_ups=follow_up_dicts,
        db=db,
    )
    if decision.decision == NO_ACTION:
        # Most commonly rule 3: a recommendation is already pending.
        return PipelineOutcome(stage="no_action", recommendation=None, escalation=None, decision=decision, detail=decision.reason_code)
    if decision.decision == AGENT_ESCALATION:
        return PipelineOutcome(stage="escalated", recommendation=None, escalation=result, decision=decision)
    assert isinstance(result, AnalyzerResult)
    analysis = result
    _persist_issues_and_risk(db, claim, analysis)

    claim_age_days = (datetime.now(timezone.utc) - claim.created_at.replace(tzinfo=timezone.utc)).days
    claim_context = {
        "payer": payer.name,
        "amount": float(claim.amount),
        "status": claim.status,
        "claim_age_days": claim_age_days,
    }

    # --- 02-reasoning-agent, via Commander rule 8 ---
    claim_state = build_claim_state(db, claim)
    decision, result = route_and_dispatch(
        claim_state,
        {"type": "analyzer_completed", "payload": {}},
        reasoning_issues=analysis.issues,
        reasoning_risk_score=analysis.risk_score,
        reasoning_risk_level=analysis.risk_level,
        reasoning_claim_context=claim_context,
        db=db,
        anthropic_client=anthropic_client,
    )
    if isinstance(result, ReasoningFailure):
        decision, escalation = route_and_dispatch(
            claim_state,
            {"type": "reasoning_failed", "payload": {}},
            db=db,
            escalation_extra_context={"reasoning_failure": {"reason": result.reason, "detail": result.detail}},
        )
        return PipelineOutcome(stage="escalated", recommendation=None, escalation=escalation, decision=decision)
    assert isinstance(result, ReasoningResult)
    reasoning = result

    # --- 03-recommendation-agent, via Commander rule 10 ---
    claim_state = build_claim_state(db, claim)
    decision, result = route_and_dispatch(
        claim_state,
        {"type": "reasoning_completed", "payload": {}},
        recommendation_issues=analysis.issues,
        recommendation_risk_score=analysis.risk_score,
        recommendation_risk_level=analysis.risk_level,
        recommendation_reasoning=reasoning,
        db=db,
        anthropic_client=anthropic_client,
    )
    if isinstance(result, RecommendationFailure):
        decision, escalation = route_and_dispatch(
            claim_state,
            {"type": "recommendation_failed", "payload": {}},
            db=db,
            escalation_extra_context={"recommendation_failure": {"reason": result.reason, "detail": result.detail}},
        )
        return PipelineOutcome(stage="escalated", recommendation=None, escalation=escalation, decision=decision)
    assert isinstance(result, RecommendationResult)
    rec_result = result

    # --- Commander rules 12/13 — evaluated on the recommendation 03 JUST
    # produced, before anything is persisted. Rule 3 blocks any non-approval
    # trigger while a recommendation's approval_status is already "pending" —
    # persisting this one as pending first would make that guard mistake
    # this brand-new result for an outstanding one and swallow rule 12/13
    # entirely (rule 3 is checked before them). approval_status is "none"
    # here on purpose: nothing has been persisted yet.
    claim_state = build_claim_state(db, claim)
    claim_state["latest_recommendation"] = {
        "action_type": rec_result.action_type,
        "confidence_band": rec_result.confidence,
        "low_confidence": rec_result.low_confidence,
        "approval_status": "none",
    }
    decision, escalation_result = route_and_dispatch(
        claim_state,
        {"type": "recommendation_completed", "payload": {}},
        db=db,
    )

    row = models.Recommendation(
        claim_id=claim.id,
        note=rec_result.rationale,
        action_type=rec_result.action_type,
        confidence=rec_result.confidence,
        low_confidence=int(rec_result.low_confidence),
        cited_issue_types=json.dumps(rec_result.cited_issue_types),
        secondary_options=json.dumps(rec_result.secondary_options),
        raw_model_response=rec_result.raw_model_response,
        approval_status=STATUS_ESCALATED if decision.decision == AGENT_ESCALATION else STATUS_PENDING,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if decision.decision == AGENT_ESCALATION:
        return PipelineOutcome(stage="escalated", recommendation=row, escalation=escalation_result, decision=decision)
    return PipelineOutcome(stage="pending", recommendation=row, escalation=None, decision=decision)


def _build_followup_action(claim: models.Claim, recommendation: models.Recommendation) -> dict:
    """Fix the follow-up's content at approval time, deterministically —
    04-followup-agent never drafts or edits this itself (docs/agents/
    04-followup-agent.md). The recommendation's own rationale (03's already-
    written explanation) is the note; the due date comes from the payer's
    own configured follow-up threshold, not a model guess."""
    payer = claim.payer
    threshold_days = int(getattr(payer, "follow_up_threshold_days", 0) or 0) or 14
    return {
        "note": recommendation.note,
        "due_at": datetime.utcnow() + timedelta(days=threshold_days),
    }


def _build_reminder_action(claim: models.Claim, recommendation: models.Recommendation) -> dict:
    """Same principle as `_build_followup_action`, for a payer_reminder:
    target is the claim's actual payer, content is 03's own rationale,
    reference_number is the claim's own id — nothing here is invented."""
    return {
        "target": claim.payer.name,
        "content": recommendation.note,
        "reference_number": claim.claim_id,
    }


def decide_recommendation(
    db: Session,
    claim: models.Claim,
    recommendation: models.Recommendation,
    *,
    approved: bool,
    approver: str = DEFAULT_APPROVER,
    approval_still_valid: bool = True,
    simulate_transient_failures: int = 0,
) -> DecisionOutcome:
    """Record a human's approve/decline decision on a pending recommendation
    and run it through Commander for real (rules 5, 14-16, 20), exactly like
    every other agent-triggering event in this pipeline.

    An approved follow_up/payer_reminder recommendation dispatches straight
    to the real 04-followup-agent/05-reminder-agent (rules 14/15). If that
    execution itself fails, a second, equally real Commander hop follows —
    `followup_failed`/`reminder_failed` (rules 17/18) — exactly as if it had
    arrived from anywhere else; a success gets the same second hop with
    `followup_completed`/`reminder_completed` (rule 19, no_action) purely for
    an accurate audit trail.

    `approval_still_valid=False` and `simulate_transient_failures>0` are
    test-only levers threaded straight through to whichever executor agent
    runs — production callers never need them.
    """
    if recommendation.approval_status != STATUS_PENDING:
        raise ValueError(f"recommendation {recommendation.id} is not pending (status={recommendation.approval_status})")

    claim_state = build_claim_state(db, claim)
    trigger_type = "human_approved" if approved else "human_declined_action"
    approved_at = datetime.utcnow()

    followup_action = None
    reminder_action = None
    if approved and recommendation.action_type == "follow_up":
        followup_action = _build_followup_action(claim, recommendation)
    elif approved and recommendation.action_type == "payer_reminder":
        reminder_action = _build_reminder_action(claim, recommendation)

    decision, result = route_and_dispatch(
        claim_state,
        {"type": trigger_type, "payload": {"recommendation_id": recommendation.id}},
        claim_pk=claim.id,
        followup_action=followup_action,
        reminder_action=reminder_action,
        approver=approver,
        approved_at=approved_at,
        approval_still_valid=approval_still_valid,
        simulate_transient_failures=simulate_transient_failures,
        db=db,
    )

    recommendation.approval_status = STATUS_APPROVED if approved else STATUS_DECLINED
    recommendation.decided_at = approved_at
    db.add(recommendation)

    escalation = result if decision.decision == AGENT_ESCALATION else None
    execution: Optional[Union[FollowUpResult, FollowUpFailure, ReminderResult, ReminderFailure]] = None
    execution_decision: Optional[CommanderDecision] = None

    if decision.decision in (AGENT_FOLLOWUP, AGENT_REMINDER):
        execution = result
        is_followup = decision.decision == AGENT_FOLLOWUP
        is_failure = isinstance(result, (FollowUpFailure, ReminderFailure))
        next_trigger = (
            ("followup_failed" if is_followup else "reminder_failed")
            if is_failure
            else ("followup_completed" if is_followup else "reminder_completed")
        )
        # Re-fetch claim_state: the recommendation's approval_status above has
        # already changed in-session, and this is a genuinely new event.
        next_claim_state = build_claim_state(db, claim)
        execution_decision, next_result = route_and_dispatch(
            next_claim_state,
            {"type": next_trigger, "payload": {"recommendation_id": recommendation.id}},
            db=db,
        )
        if execution_decision.decision == AGENT_ESCALATION:
            escalation = next_result

    activity = models.ActivityLog(
        claim_id=claim.id,
        action=trigger_type,
        details=json.dumps(
            {
                "recommendation_id": recommendation.id,
                "action_type": recommendation.action_type,
                "commander_decision": decision.decision,
                "reason_code": decision.reason_code,
                "rule": decision.rule,
                "execution_decision": execution_decision.decision if execution_decision else None,
                "execution_reason_code": execution_decision.reason_code if execution_decision else None,
                "execution_rule": execution_decision.rule if execution_decision else None,
                "escalation_id": escalation.escalation_id if escalation else None,
            }
        ),
    )
    db.add(activity)
    db.commit()
    db.refresh(recommendation)
    db.refresh(activity)

    return DecisionOutcome(
        recommendation=recommendation,
        decision=decision,
        execution=execution,
        execution_decision=execution_decision,
        escalation=escalation,
        activity=activity,
    )
