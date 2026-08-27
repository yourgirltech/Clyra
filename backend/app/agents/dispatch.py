"""Ties Commander's routing decision to real agent execution.

Commander (`app.agents.commander.commander_route`) only decides *whether* the
pipeline continues and *which* agent runs next — it never calls one. This
module is the thin seam that does: given a routing decision, run the real
agent (01 through 06) that Commander named. `dispatch_stub` remains only as
a defensive fallback for a decision string with no matching branch below,
which should never happen now that every agent 01-06 is implemented.
"""

from __future__ import annotations

from datetime import datetime

import anthropic
from sqlalchemy.orm import Session

from app.agents.analyzer import AnalyzerResult, run_analyzer
from app.agents.commander import (
    AGENT_ANALYZER,
    AGENT_ESCALATION,
    AGENT_FOLLOWUP,
    AGENT_REASONING,
    AGENT_RECOMMENDATION,
    AGENT_REMINDER,
    NO_ACTION,
    CommanderDecision,
    commander_route,
    dispatch_stub,
)
from app.agents.escalation import EscalationResult, run_escalation
from app.agents.followup import FollowUpFailure, FollowUpResult, run_followup
from app.agents.reasoning import ReasoningFailure, ReasoningResult, run_reasoning
from app.agents.recommendation import (
    RecommendationFailure,
    RecommendationResult,
    run_recommendation,
)
from app.agents.reminder import ReminderFailure, ReminderResult, run_reminder
from app.services.risk_rules import Issue


def route_and_dispatch(
    claim_state: dict | None,
    trigger: dict | None,
    *,
    claim_evidence: dict | None = None,
    payer_config: dict | None = None,
    follow_ups: list[dict] | None = None,
    reasoning_issues: list[Issue] | None = None,
    reasoning_risk_score: int | None = None,
    reasoning_risk_level: str | None = None,
    reasoning_claim_context: dict | None = None,
    recommendation_issues: list[Issue] | None = None,
    recommendation_risk_score: int | None = None,
    recommendation_risk_level: str | None = None,
    recommendation_reasoning: ReasoningResult | None = None,
    claim_pk: int | None = None,
    followup_action: dict | None = None,
    reminder_action: dict | None = None,
    approver: str | None = None,
    approved_at: datetime | None = None,
    approval_still_valid: bool = True,
    simulate_transient_failures: int = 0,
    db: Session | None = None,
    escalation_extra_context: dict | None = None,
    anthropic_client: anthropic.Anthropic | None = None,
) -> tuple[
    CommanderDecision,
    AnalyzerResult
    | ReasoningResult
    | ReasoningFailure
    | RecommendationResult
    | RecommendationFailure
    | FollowUpResult
    | FollowUpFailure
    | ReminderResult
    | ReminderFailure
    | EscalationResult
    | str
    | None,
]:
    """Run Commander's routing, then actually execute it.

    Returns `(decision, result)`:
    - If Commander routes to 01-analyzer-agent (rule 6), `result` is a real
      `AnalyzerResult` computed from `claim_evidence`/`payer_config`/
      `follow_ups` (required in that case — raises if omitted).
    - If Commander routes to 02-reasoning-agent (rule 8), `result` is a real
      `ReasoningResult` or `ReasoningFailure` computed from
      `reasoning_issues`/`reasoning_risk_score`/`reasoning_risk_level`/
      `reasoning_claim_context` (required in that case — raises if omitted).
    - If Commander routes to 03-recommendation-agent (rule 10), `result` is a
      real `RecommendationResult` or `RecommendationFailure` computed from
      `recommendation_issues`/`recommendation_risk_score`/
      `recommendation_risk_level`/`recommendation_reasoning` — the last being
      a `ReasoningResult`, i.e. 02's own output (required in that case —
      raises if omitted).
      `anthropic_client` is passed through to whichever LLM agent runs, for
      injecting a test double; omit it to use the real Claude API.
    - If Commander routes to 04-followup-agent (rule 14), `result` is a real
      `FollowUpResult` or `FollowUpFailure` computed from `followup_action`/
      `claim_pk`/`approver`/`approved_at` (required in that case — raises if
      omitted). `approval_still_valid`/`simulate_transient_failures` are
      test-only levers, passed straight through.
    - If Commander routes to 05-reminder-agent (rule 15), `result` is a real
      `ReminderResult` or `ReminderFailure` computed from `reminder_action`/
      `claim_pk`/`approver`/`approved_at` (required in that case — raises if
      omitted), with the same test-only levers.
    - If Commander routes to 06-escalation-agent (rules 1, 7, 9, 11, 13, 17,
      18, 20), `result` is a real `EscalationResult` (`db` is required in
      that case — raises if omitted). Context is assembled from the trigger
      and whatever `claim_state` carries (status, risk_score, risk_level,
      latest_issues, latest_recommendation); pass `escalation_extra_context`
      to attach anything richer the caller already has on hand — e.g. the
      actual `ReasoningFailure`/`RecommendationFailure`/`FollowUpFailure`/
      `ReminderFailure` that led here, which `claim_state` alone doesn't
      carry.
    - If Commander routes to `no_action`, `result` is `None`.
    """
    decision = commander_route(claim_state, trigger)
    claim_id = claim_state.get("claim_id") if claim_state else None

    if decision.decision == AGENT_ANALYZER:
        if claim_evidence is None or payer_config is None:
            raise ValueError(
                "claim_evidence and payer_config are required to run 01-analyzer-agent"
            )
        result = run_analyzer(claim_id, claim_evidence, payer_config, follow_ups or [])
        return decision, result

    if decision.decision == AGENT_REASONING:
        if (
            reasoning_issues is None
            or reasoning_risk_score is None
            or reasoning_risk_level is None
            or reasoning_claim_context is None
        ):
            raise ValueError(
                "reasoning_issues, reasoning_risk_score, reasoning_risk_level, and "
                "reasoning_claim_context are required to run 02-reasoning-agent"
            )
        result = run_reasoning(
            claim_id,
            reasoning_issues,
            reasoning_risk_score,
            reasoning_risk_level,
            reasoning_claim_context,
            client=anthropic_client,
        )
        return decision, result

    if decision.decision == AGENT_RECOMMENDATION:
        if (
            recommendation_issues is None
            or recommendation_risk_score is None
            or recommendation_risk_level is None
            or recommendation_reasoning is None
        ):
            raise ValueError(
                "recommendation_issues, recommendation_risk_score, recommendation_risk_level, "
                "and recommendation_reasoning are required to run 03-recommendation-agent"
            )
        result = run_recommendation(
            claim_id,
            recommendation_issues,
            recommendation_risk_score,
            recommendation_risk_level,
            recommendation_reasoning.issue_explanations,
            recommendation_reasoning.cross_issue_notes,
            recommendation_reasoning.uncertainty_notes,
            recommendation_reasoning.summary,
            client=anthropic_client,
        )
        return decision, result

    if decision.decision == AGENT_FOLLOWUP:
        if claim_pk is None or followup_action is None or approver is None or approved_at is None:
            raise ValueError(
                "claim_pk, followup_action, approver, and approved_at are required to run 04-followup-agent"
            )
        if db is None:
            raise ValueError("db is required to run 04-followup-agent")
        result = run_followup(
            db,
            claim_id=claim_id,
            claim_pk=claim_pk,
            approved_action=followup_action,
            approver=approver,
            approved_at=approved_at,
            approval_still_valid=approval_still_valid,
            simulate_transient_failures=simulate_transient_failures,
        )
        return decision, result

    if decision.decision == AGENT_REMINDER:
        if claim_pk is None or reminder_action is None or approver is None or approved_at is None:
            raise ValueError(
                "claim_pk, reminder_action, approver, and approved_at are required to run 05-reminder-agent"
            )
        if db is None:
            raise ValueError("db is required to run 05-reminder-agent")
        result = run_reminder(
            db,
            claim_id=claim_id,
            claim_pk=claim_pk,
            approved_action=reminder_action,
            approver=approver,
            approved_at=approved_at,
            approval_still_valid=approval_still_valid,
            simulate_transient_failures=simulate_transient_failures,
        )
        return decision, result

    if decision.decision == AGENT_ESCALATION:
        if db is None:
            raise ValueError("db is required to run 06-escalation-agent")
        context = {
            "trigger": trigger,
            "claim_status": claim_state.get("status") if claim_state else None,
            "risk_score": claim_state.get("risk_score") if claim_state else None,
            "risk_level": claim_state.get("risk_level") if claim_state else None,
            "latest_issues": claim_state.get("latest_issues") if claim_state else None,
            "latest_recommendation": claim_state.get("latest_recommendation") if claim_state else None,
        }
        if escalation_extra_context:
            context.update(escalation_extra_context)
        result = run_escalation(
            db,
            claim_id=claim_id,
            reason_code=decision.reason_code,
            rule=decision.rule,
            context=context,
        )
        return decision, result

    if decision.decision == NO_ACTION:
        return decision, None

    return decision, dispatch_stub(decision.decision)
