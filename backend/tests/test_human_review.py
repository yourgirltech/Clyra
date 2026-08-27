"""Tests for wiring Human Review to real endpoints: `app.services.pipeline`
(generate_recommendation / decide_recommendation) and the
/claims/{id}/recommendation* routes in app.api.routes.claims.

The LLM call is mocked throughout — same pattern as test_recommendation.py —
so confidence/action_type are deterministic and every test runs without
network access or credentials. What's NOT mocked, anywhere in this file: the
Postgres writes (ClaimIssue, Recommendation, ActivityLog, Escalation,
FollowUp, PayerReminder), Commander's real routing logic, or 04/05's own
execution (retry/failure coverage for those two agents individually lives in
test_followup.py/test_reminder.py — this file covers the full chain: approve
-> Commander -> real executor agent -> real record). One test
(`test_end_to_end_...`) goes through the actual FastAPI HTTP layer via
TestClient rather than calling the service functions directly, to prove the
wiring is real end to end, not just at the function-call level.
"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import models
from app.agents.commander import AGENT_ESCALATION, AGENT_FOLLOWUP, AGENT_REMINDER, NO_ACTION
from app.agents.followup import FollowUpResult
from app.agents.reasoning import ReasoningOutput, IssueExplanation
from app.agents.recommendation import RecommendationOption, RecommendationOutput
from app.agents.reminder import ReminderResult
from app.db.database import SessionLocal
from app.services import pipeline
from main import app


class FakeMessages:
    """Stands in for client.messages — returns a canned parsed_output keyed
    off which agent's output_format is being requested this call, so one
    fake client can serve both the reasoning and recommendation steps."""

    def __init__(self, reasoning_output, recommendation_output):
        self._reasoning_output = reasoning_output
        self._recommendation_output = recommendation_output

    def parse(self, **kwargs):
        output_format = kwargs.get("output_format")
        if output_format is ReasoningOutput:
            return SimpleNamespace(parsed_output=self._reasoning_output)
        if output_format is RecommendationOutput:
            return SimpleNamespace(parsed_output=self._recommendation_output)
        raise AssertionError(f"unexpected output_format: {output_format!r}")


class FakeClient:
    def __init__(self, reasoning_output=None, recommendation_output=None):
        self.messages = FakeMessages(reasoning_output, recommendation_output)


def _reasoning_output(issue_type="missing_authorization"):
    return ReasoningOutput(
        issue_explanations=[IssueExplanation(issue_type=issue_type, explanation="Explained for test.")],
        cross_issue_notes="",
        uncertainty_notes="",
        summary="Test summary.",
    )


def _recommendation_output(action_type, confidence, cited=("missing_authorization",)):
    option = RecommendationOption(
        action_type=action_type,
        rationale="insufficient basis for a recommendation" if confidence == "Low" else "Test rationale citing the issue.",
        cited_issue_types=[] if confidence == "Low" else list(cited),
        confidence=confidence,
    )
    return RecommendationOutput(primary=option, secondary_options=[])


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded_claim(db):
    """A real, freshly-created claim with exactly one deterministic issue
    (missing_authorization) — reuses an existing seeded clinic/payer so this
    doesn't depend on seed_claims.py having been run with any particular
    randomized spread. Fully cleaned up afterward: this is the shared demo
    DB, not a throwaway test database."""
    clinic = db.query(models.Clinic).first()
    assert clinic is not None, "run backend/scripts/seed_claims.py first"
    payer = db.query(models.Payer).filter(models.Payer.authorization_required == 1).first()
    assert payer is not None, "need a seeded payer with authorization_required=1"

    claim = models.Claim(
        claim_id="CL-TEST-HUMAN-REVIEW",
        clinic_id=clinic.id,
        payer_id=payer.id,
        amount=123.45,
        status="Submitted",
        risk_level="Low",
        risk_score=0,
        authorization_present=0,
        documentation_present=1,
        coding_matches=1,
        # recent, so overdue_follow_up never fires regardless of payer config
        # — this claim must produce exactly one deterministic issue.
        last_followup_at=datetime.utcnow(),
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    yield claim

    db.query(models.ActivityLog).filter(models.ActivityLog.claim_id == claim.id).delete()
    db.query(models.Escalation).filter(models.Escalation.claim_id == claim.claim_id).delete()
    db.query(models.PayerReminder).filter(models.PayerReminder.claim_id == claim.id).delete()
    db.query(models.FollowUp).filter(models.FollowUp.claim_id == claim.id).delete()
    db.query(models.Recommendation).filter(models.Recommendation.claim_id == claim.id).delete()
    db.query(models.ClaimIssue).filter(models.ClaimIssue.claim_id == claim.id).delete()
    db.query(models.Claim).filter(models.Claim.id == claim.id).delete()
    db.commit()


# ---------------------------------------------------------------------------
# generate_recommendation
# ---------------------------------------------------------------------------

def test_generate_recommendation_persists_pending_row_for_high_confidence(db, seeded_claim):
    client = FakeClient(_reasoning_output(), _recommendation_output("follow_up", "High"))
    outcome = pipeline.generate_recommendation(db, seeded_claim, anthropic_client=client)

    assert outcome.stage == "pending"
    assert outcome.decision.decision == NO_ACTION
    assert outcome.decision.reason_code == "awaiting_human_approval"
    assert outcome.recommendation is not None
    assert outcome.recommendation.approval_status == pipeline.STATUS_PENDING
    assert outcome.recommendation.action_type == "follow_up"
    assert not outcome.recommendation.low_confidence

    # Real deterministic issue was actually persisted, not fabricated.
    issues = db.query(models.ClaimIssue).filter(models.ClaimIssue.claim_id == seeded_claim.id).all()
    assert [i.issue_type for i in issues] == ["missing_authorization"]


def test_generate_recommendation_low_confidence_escalates_immediately(db, seeded_claim):
    client = FakeClient(_reasoning_output(), _recommendation_output("follow_up", "Low"))
    outcome = pipeline.generate_recommendation(db, seeded_claim, anthropic_client=client)

    assert outcome.stage == "escalated"
    assert outcome.decision.decision == AGENT_ESCALATION
    assert outcome.decision.reason_code == "low_confidence"
    assert outcome.decision.rule == 13
    assert outcome.escalation is not None
    assert outcome.escalation.persisted is True

    # Never offered as a one-click approval — approval_status reflects that.
    assert outcome.recommendation.approval_status == pipeline.STATUS_ESCALATED

    row = db.query(models.Escalation).filter(models.Escalation.id == outcome.escalation.escalation_id).first()
    assert row is not None
    assert row.reason_code == "low_confidence"
    assert row.claim_id == seeded_claim.claim_id


def test_generate_recommendation_refuses_second_run_while_pending(db, seeded_claim):
    client = FakeClient(_reasoning_output(), _recommendation_output("follow_up", "High"))
    first = pipeline.generate_recommendation(db, seeded_claim, anthropic_client=client)
    assert first.stage == "pending"

    second = pipeline.generate_recommendation(db, seeded_claim, anthropic_client=client)
    assert second.stage == "no_action"
    assert second.decision.reason_code == "awaiting_human_decision"
    assert second.decision.rule == 3

    # Still exactly one recommendation row — rule 3 actually prevented a second.
    count = db.query(models.Recommendation).filter(models.Recommendation.claim_id == seeded_claim.id).count()
    assert count == 1


# ---------------------------------------------------------------------------
# decide_recommendation — rules 5, 14, 15, 16, and the 17/18/19 second hop
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "action_type,expected_rule,agent_decision,record_model,completed_action",
    [
        ("follow_up", 14, AGENT_FOLLOWUP, "FollowUp", "followup_completed"),
        ("payer_reminder", 15, AGENT_REMINDER, "PayerReminder", "reminder_completed"),
    ],
)
def test_approve_executable_action_dispatches_to_real_agent(
    db, seeded_claim, action_type, expected_rule, agent_decision, record_model, completed_action
):
    client = FakeClient(_reasoning_output(), _recommendation_output(action_type, "High"))
    generated = pipeline.generate_recommendation(db, seeded_claim, anthropic_client=client)
    rec = generated.recommendation

    outcome = pipeline.decide_recommendation(db, seeded_claim, rec, approved=True)

    # First hop: Commander dispatches straight to the real executor agent —
    # no escalation, rules 14/15 are no longer a carve-out.
    assert outcome.decision.decision == agent_decision
    assert outcome.decision.rule == expected_rule
    assert outcome.escalation is None
    assert isinstance(outcome.execution, (FollowUpResult, ReminderResult))
    assert outcome.recommendation.approval_status == pipeline.STATUS_APPROVED

    # Second hop: the agent's own *_completed event reaches Commander for
    # real too (rule 19, no_action) — an accurate audit trail, not a no-op.
    assert outcome.execution_decision.decision == NO_ACTION
    assert outcome.execution_decision.rule == 19
    assert outcome.execution_decision.reason_code == "action_executed"

    model = getattr(models, record_model)
    row = db.query(model).filter(model.claim_id == seeded_claim.id).first()
    assert row is not None

    assert outcome.activity.action == "human_approved"
    details = json.loads(outcome.activity.details)
    assert details["commander_decision"] == agent_decision
    assert details["execution_decision"] == NO_ACTION
    assert details["escalation_id"] is None

    log = (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.claim_id == seeded_claim.id, models.ActivityLog.action == completed_action)
        .first()
    )
    assert log is not None


@pytest.mark.parametrize(
    "action_type,expected_rule,fail_reason",
    [("follow_up", 17, "followup_execution_failed"), ("payer_reminder", 18, "reminder_execution_failed")],
)
def test_approve_with_simulated_execution_failure_escalates_via_real_rule(
    db, seeded_claim, action_type, expected_rule, fail_reason
):
    # 04/05's own retry policy is test_followup.py's/test_reminder.py's job —
    # this confirms the OTHER side: a non-recoverable execution failure
    # reaches Commander for real and lands in 06, via rules 17/18, which
    # were unreachable in Phase 4 (nothing could ever emit followup_failed/
    # reminder_failed for real, since 04/05 didn't exist).
    client = FakeClient(_reasoning_output(), _recommendation_output(action_type, "High"))
    generated = pipeline.generate_recommendation(db, seeded_claim, anthropic_client=client)

    from app.agents.followup import MAX_RETRIES

    outcome = pipeline.decide_recommendation(
        db, seeded_claim, generated.recommendation, approved=True,
        simulate_transient_failures=MAX_RETRIES + 1,  # exhaust every retry
    )

    assert outcome.execution_decision.decision == AGENT_ESCALATION
    assert outcome.execution_decision.rule == expected_rule
    assert outcome.execution_decision.reason_code == fail_reason
    assert outcome.escalation is not None and outcome.escalation.persisted is True

    row = db.query(models.Escalation).filter(models.Escalation.id == outcome.escalation.escalation_id).first()
    assert row.reason_code == fail_reason
    assert row.rule == expected_rule

    details = json.loads(outcome.activity.details)
    assert details["escalation_id"] == outcome.escalation.escalation_id


def test_approve_no_action_needed_does_not_escalate(db, seeded_claim):
    client = FakeClient(_reasoning_output(), _recommendation_output("manual_review_needed", "High"))
    generated = pipeline.generate_recommendation(db, seeded_claim, anthropic_client=client)

    outcome = pipeline.decide_recommendation(db, seeded_claim, generated.recommendation, approved=True)

    assert outcome.decision.decision == NO_ACTION
    assert outcome.decision.reason_code == "approval_acknowledged_no_agent_needed"
    assert outcome.decision.rule == 16
    assert outcome.escalation is None
    assert outcome.recommendation.approval_status == pipeline.STATUS_APPROVED


def test_decline_records_decision_without_escalating(db, seeded_claim):
    client = FakeClient(_reasoning_output(), _recommendation_output("follow_up", "High"))
    generated = pipeline.generate_recommendation(db, seeded_claim, anthropic_client=client)

    outcome = pipeline.decide_recommendation(db, seeded_claim, generated.recommendation, approved=False)

    assert outcome.decision.decision == NO_ACTION
    assert outcome.decision.reason_code == "decision_recorded"
    assert outcome.decision.rule == 5
    assert outcome.escalation is None
    assert outcome.recommendation.approval_status == pipeline.STATUS_DECLINED
    assert outcome.activity.action == "human_declined_action"


def test_deciding_an_already_decided_recommendation_raises(db, seeded_claim):
    client = FakeClient(_reasoning_output(), _recommendation_output("follow_up", "High"))
    generated = pipeline.generate_recommendation(db, seeded_claim, anthropic_client=client)
    pipeline.decide_recommendation(db, seeded_claim, generated.recommendation, approved=True)

    with pytest.raises(ValueError):
        pipeline.decide_recommendation(db, seeded_claim, generated.recommendation, approved=False)


# ---------------------------------------------------------------------------
# One real end-to-end test — the actual HTTP API, actual DB, actual
# Commander routing, actual 04-followup-agent execution. Only the Claude API
# call (recommendation generation) is mocked, for determinism; approving is a
# real HTTP POST through the real FastAPI app, and it must create a real
# FollowUp record and activity log entry — NOT an escalation, now that 04
# actually exists.
# ---------------------------------------------------------------------------

def test_end_to_end_approve_via_http_creates_real_followup(db, seeded_claim):
    client = FakeClient(_reasoning_output(), _recommendation_output("follow_up", "High"))
    generated = pipeline.generate_recommendation(db, seeded_claim, anthropic_client=client)
    assert generated.stage == "pending"
    rec_id = generated.recommendation.id

    http = TestClient(app)
    response = http.post(f"/api/claims/{seeded_claim.claim_id}/recommendation/{rec_id}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["decision"] == AGENT_FOLLOWUP
    assert body["decision"]["rule"] == 14
    assert body["decision"]["reason_code"] == "execute_followup"
    assert body["recommendation"]["approval_status"] == "approved"
    assert body["escalation_id"] is None
    assert body["execution"]["kind"] == "FollowUpResult"
    followup_id = body["execution"]["followup_id"]
    assert body["execution_decision"]["rule"] == 19

    # Re-fetch from the DB directly (a fresh session) — proves the HTTP
    # request actually committed real rows, not just returned a plausible
    # response body.
    verify_db = SessionLocal()
    try:
        followup = verify_db.query(models.FollowUp).filter(models.FollowUp.id == followup_id).first()
        assert followup is not None
        assert followup.claim_id == seeded_claim.id
        assert followup.note  # the recommendation's own rationale, not fabricated

        # No escalation was created — this was a genuine success, not a
        # disguised failure.
        assert verify_db.query(models.Escalation).filter(models.Escalation.claim_id == seeded_claim.claim_id).count() == 0

        rec = verify_db.query(models.Recommendation).filter(models.Recommendation.id == rec_id).first()
        assert rec.approval_status == "approved"

        approved_log = (
            verify_db.query(models.ActivityLog)
            .filter(models.ActivityLog.claim_id == seeded_claim.id, models.ActivityLog.action == "human_approved")
            .first()
        )
        assert approved_log is not None

        completed_log = (
            verify_db.query(models.ActivityLog)
            .filter(models.ActivityLog.claim_id == seeded_claim.id, models.ActivityLog.action == "followup_completed")
            .first()
        )
        assert completed_log is not None
    finally:
        verify_db.close()

    # Timeline endpoint reflects both real events.
    timeline = http.get(f"/api/claims/{seeded_claim.claim_id}/activity").json()
    actions = {item["action"] for item in timeline["items"]}
    assert {"human_approved", "followup_completed"}.issubset(actions)

    # A second approve attempt on the now-resolved recommendation is refused.
    again = http.post(f"/api/claims/{seeded_claim.claim_id}/recommendation/{rec_id}/approve")
    assert again.status_code == 409
