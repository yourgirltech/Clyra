"""Tests for 03-recommendation-agent (backend/app/agents/recommendation.py)
and its wiring into Commander's dispatch (backend/app/agents/dispatch.py).

The LLM call is mocked for every test in this file, same pattern as
test_reasoning.py. The one real Claude API call lives in
test_recommendation_live.py, run separately and on purpose.
"""

from types import SimpleNamespace

import pytest

from app.agents.commander import (
    AGENT_ESCALATION,
    AGENT_FOLLOWUP,
    AGENT_RECOMMENDATION,
    AGENT_REMINDER,
    commander_route,
)
from app.agents.dispatch import route_and_dispatch
from app.agents.escalation import EscalationResult
from app.agents.reasoning import ReasoningResult
from app.agents.recommendation import (
    INSUFFICIENT_BASIS_RATIONALE,
    RecommendationFailure,
    RecommendationOption,
    RecommendationOutput,
    RecommendationResult,
    run_recommendation,
)
from app.services.risk_rules import Issue


class FakeMessages:
    """Stands in for client.messages — .parse() returns a canned parsed_output."""

    def __init__(self, parsed_output):
        self._parsed_output = parsed_output
        self.calls = 0

    def parse(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(parsed_output=self._parsed_output)


class FakeClient:
    def __init__(self, parsed_output):
        self.messages = FakeMessages(parsed_output)


class _FakeEscalationDB:
    """Minimal duck-typed stand-in for a SQLAlchemy Session — just enough for
    run_escalation's add/commit/refresh calls to succeed without a real DB.
    Escalation persistence correctness itself is test_escalation.py's job;
    these two tests only care that recommendation's real action_type reaches
    Commander's rule 14/15 correctly."""

    def add(self, obj):
        self._obj = obj

    def commit(self):
        from datetime import datetime

        self._obj.id = 1
        self._obj.created_at = datetime.utcnow()

    def refresh(self, obj):
        pass

    def rollback(self):
        pass


def make_issue(issue_type="missing_authorization", severity="high"):
    return Issue(
        issue_type=issue_type,
        severity=severity,
        description=f"{issue_type} description",
        evidence={"some_field": 0},
    )


def _claim_state(**overrides):
    state = {
        "claim_id": "CL-1",
        "status": "Submitted",
        "risk_score": 50,
        "risk_level": "High",
        "latest_issues": [],
        "latest_recommendation": None,
        "agent_run_in_progress": False,
    }
    state.update(overrides)
    return state


def make_reasoning_result(issue_types=("missing_authorization",)):
    return ReasoningResult(
        claim_id="CL-1",
        issue_explanations={t: f"{t} explained." for t in issue_types},
        cross_issue_notes="",
        uncertainty_notes="",
        summary="Issues found." if issue_types else "No issues to explain.",
        raw_model_response="{}",
    )


# ---------------------------------------------------------------------------
# High confidence -> a real, grounded recommendation.
# ---------------------------------------------------------------------------

def test_high_confidence_produces_grounded_follow_up_recommendation():
    issues = [make_issue("missing_authorization", "high")]
    mock_output = RecommendationOutput(
        primary=RecommendationOption(
            action_type="follow_up",
            rationale="Authorization is missing and must be chased before resubmission.",
            cited_issue_types=["missing_authorization"],
            confidence="High",
        ),
    )
    client = FakeClient(mock_output)

    result = run_recommendation(
        "CL-1", issues, 80, "High",
        {"missing_authorization": "explained"}, "", "", "Issues found.",
        client=client,
    )

    assert isinstance(result, RecommendationResult)
    assert client.messages.calls == 1
    assert result.action_type == "follow_up"
    assert result.confidence == "High"
    assert result.low_confidence is False
    assert result.cited_issue_types == ["missing_authorization"]
    assert result.raw_model_response


def test_refuses_to_cite_an_issue_not_in_the_list():
    issues = [make_issue("missing_authorization", "high")]
    mock_output = RecommendationOutput(
        primary=RecommendationOption(
            action_type="follow_up",
            rationale="Fabricated rationale.",
            cited_issue_types=["missing_authorization", "fraud_suspected"],  # invented
            confidence="High",
        ),
    )
    client = FakeClient(mock_output)

    result = run_recommendation(
        "CL-1", issues, 80, "High",
        {"missing_authorization": "explained"}, "", "", "Issues found.",
        client=client,
    )

    assert isinstance(result, RecommendationFailure)
    assert result.reason == "ungrounded_output"
    assert "fraud_suspected" in result.detail


# ---------------------------------------------------------------------------
# Low confidence: a valid *result*, never a failure — and never upgraded.
# ---------------------------------------------------------------------------

def test_low_confidence_is_a_success_result_not_a_failure():
    issues = [make_issue("code_mismatch", "medium")]
    mock_output = RecommendationOutput(
        primary=RecommendationOption(
            action_type="manual_review_needed",
            rationale=INSUFFICIENT_BASIS_RATIONALE,
            cited_issue_types=[],
            confidence="Low",
        ),
    )
    client = FakeClient(mock_output)

    result = run_recommendation(
        "CL-1", issues, 40, "Medium",
        {"code_mismatch": "ambiguous"}, "", "conflicting signals", "Hard to tell.",
        client=client,
    )

    # A Low-confidence recommendation is still a RecommendationResult, never
    # a RecommendationFailure — this agent doesn't get to treat "not sure" as
    # an error, and it must never silently flip the confidence it was given.
    assert isinstance(result, RecommendationResult)
    assert result.confidence == "Low"
    assert result.low_confidence is True
    assert result.rationale == INSUFFICIENT_BASIS_RATIONALE


def test_low_confidence_recommendation_completed_routes_to_commander_rule13():
    # This agent has no way to force a low-confidence result past Commander's
    # gate — prove that gate actually fires off this result's own boolean.
    issues = [make_issue("code_mismatch", "medium")]
    mock_output = RecommendationOutput(
        primary=RecommendationOption(
            action_type="manual_review_needed",
            rationale=INSUFFICIENT_BASIS_RATIONALE,
            cited_issue_types=[],
            confidence="Low",
        ),
    )
    result = run_recommendation(
        "CL-1", issues, 40, "Medium",
        {"code_mismatch": "ambiguous"}, "", "", "Hard to tell.",
        client=FakeClient(mock_output),
    )
    assert result.low_confidence is True

    claim_state = _claim_state(
        latest_recommendation={
            "action_type": result.action_type,
            "low_confidence": result.low_confidence,
            "approval_status": "none",
        }
    )
    decision = commander_route(claim_state, {"type": "recommendation_completed", "payload": {}})
    assert decision.rule == 13
    assert decision.decision == AGENT_ESCALATION
    assert decision.reason_code == "low_confidence"


def test_high_confidence_recommendation_completed_routes_to_commander_rule12():
    issues = [make_issue("missing_authorization", "high")]
    mock_output = RecommendationOutput(
        primary=RecommendationOption(
            action_type="follow_up",
            rationale="Chase the missing authorization.",
            cited_issue_types=["missing_authorization"],
            confidence="High",
        ),
    )
    result = run_recommendation(
        "CL-1", issues, 80, "High",
        {"missing_authorization": "explained"}, "", "", "Issues found.",
        client=FakeClient(mock_output),
    )
    assert result.low_confidence is False

    claim_state = _claim_state(
        latest_recommendation={
            "action_type": result.action_type,
            "low_confidence": result.low_confidence,
            "approval_status": "none",
        }
    )
    decision = commander_route(claim_state, {"type": "recommendation_completed", "payload": {}})
    assert decision.rule == 12
    assert decision.decision == "no_action"
    assert decision.reason_code == "awaiting_human_approval"


# ---------------------------------------------------------------------------
# Malformed input: structured failure, never a crash, routes to rule 11.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "claim_id,issues,risk_score,risk_level,explanations,summary",
    [
        (None, [make_issue()], 50, "High", {"missing_authorization": "x"}, "s"),
        ("", [make_issue()], 50, "High", {"missing_authorization": "x"}, "s"),
        ("CL-1", "not-a-list", 50, "High", {"missing_authorization": "x"}, "s"),
        ("CL-1", [{"issue_type": "x"}], 50, "High", {"missing_authorization": "x"}, "s"),  # not an Issue
        ("CL-1", [make_issue()], 150, "High", {"missing_authorization": "x"}, "s"),  # score out of range
        ("CL-1", [make_issue()], 50, "Extreme", {"missing_authorization": "x"}, "s"),  # invalid level
        ("CL-1", [make_issue()], 50, "High", "not-a-dict", "s"),  # explanations wrong type
        ("CL-1", [make_issue()], 50, "High", {"missing_authorization": "x"}, ""),  # empty summary
    ],
)
def test_malformed_input_returns_structured_failure_not_a_crash(
    claim_id, issues, risk_score, risk_level, explanations, summary
):
    client = FakeClient(parsed_output=None)  # must never be reached

    result = run_recommendation(
        claim_id, issues, risk_score, risk_level, explanations, "", "", summary, client=client
    )

    assert isinstance(result, RecommendationFailure)
    assert result.reason == "malformed_input"
    assert client.messages.calls == 0


def test_malformed_input_failure_routes_to_commander_rule11_escalation():
    result = run_recommendation(
        "CL-1", "not-a-list", 50, "High", {}, "", "", "s", client=FakeClient(None)
    )
    assert isinstance(result, RecommendationFailure)

    decision = commander_route(_claim_state(), {"type": "recommendation_failed", "payload": {}})
    assert decision.rule == 11
    assert decision.decision == AGENT_ESCALATION
    assert decision.reason_code == "recommendation_error"


def test_llm_exception_returns_structured_failure_not_a_crash():
    class ExplodingMessages:
        def parse(self, **kwargs):
            raise RuntimeError("network exploded")

    class ExplodingClient:
        messages = ExplodingMessages()

    result = run_recommendation(
        "CL-1", [make_issue()], 50, "High", {"missing_authorization": "x"}, "", "", "s",
        client=ExplodingClient(),
    )

    assert isinstance(result, RecommendationFailure)
    assert result.reason == "llm_call_failed"
    assert "network exploded" in result.detail


# ---------------------------------------------------------------------------
# Commander's rule 10 actually invokes the recommendation agent now.
# ---------------------------------------------------------------------------

def test_rule10_dispatches_a_real_recommendation_run_not_a_stub():
    issues = [make_issue("missing_authorization", "high")]
    mock_output = RecommendationOutput(
        primary=RecommendationOption(
            action_type="follow_up",
            rationale="Chase the missing authorization.",
            cited_issue_types=["missing_authorization"],
            confidence="High",
        ),
    )
    client = FakeClient(mock_output)
    reasoning_result = make_reasoning_result(("missing_authorization",))

    decision, result = route_and_dispatch(
        _claim_state(),
        {"type": "reasoning_completed", "payload": {}},
        recommendation_issues=issues,
        recommendation_risk_score=80,
        recommendation_risk_level="High",
        recommendation_reasoning=reasoning_result,
        anthropic_client=client,
    )

    assert decision.rule == 10
    assert decision.decision == AGENT_RECOMMENDATION
    assert isinstance(result, RecommendationResult)
    assert result.action_type == "follow_up"


def test_rule10_missing_required_inputs_raises_rather_than_guessing():
    with pytest.raises(ValueError):
        route_and_dispatch(_claim_state(), {"type": "reasoning_completed", "payload": {}})


# ---------------------------------------------------------------------------
# Now that 03 is real: rules 14/15 become reachable with a REAL action_type
# (previously only ever exercised with a hand-typed synthetic value in
# test_commander.py / test_reasoning.py, since nothing could produce one for
# real). Confirm the Phase-4 carve-out still escalates correctly rather than
# crashing or silently routing to 04/05, which still don't exist.
# ---------------------------------------------------------------------------

def test_real_follow_up_recommendation_still_escalates_not_04():
    issues = [make_issue("missing_authorization", "high")]
    mock_output = RecommendationOutput(
        primary=RecommendationOption(
            action_type="follow_up",
            rationale="Chase the missing authorization.",
            cited_issue_types=["missing_authorization"],
            confidence="High",
        ),
    )
    result = run_recommendation(
        "CL-1", issues, 80, "High",
        {"missing_authorization": "explained"}, "", "", "Issues found.",
        client=FakeClient(mock_output),
    )
    assert isinstance(result, RecommendationResult)
    assert result.action_type == "follow_up"  # a REAL value, not hand-typed test data

    claim_state = _claim_state(
        latest_recommendation={
            "action_type": result.action_type,
            "low_confidence": result.low_confidence,
            "approval_status": "pending",
        }
    )
    decision, dispatch_result = route_and_dispatch(
        claim_state, {"type": "human_approved", "payload": {}}, db=_FakeEscalationDB()
    )

    assert decision.rule == 14
    assert decision.decision == AGENT_ESCALATION
    assert decision.reason_code == "agent_not_yet_implemented"
    assert decision.decision != AGENT_FOLLOWUP
    # 06-escalation-agent is real now — a genuine EscalationResult, not the
    # old stub placeholder string.
    assert isinstance(dispatch_result, EscalationResult)
    assert dispatch_result.reason_code == "agent_not_yet_implemented"
    assert dispatch_result.rule == 14


def test_real_payer_reminder_recommendation_still_escalates_not_05():
    issues = [make_issue("overdue_follow_up", "medium")]
    mock_output = RecommendationOutput(
        primary=RecommendationOption(
            action_type="payer_reminder",
            rationale="Remind the payer this claim is overdue for follow-up.",
            cited_issue_types=["overdue_follow_up"],
            confidence="Medium",
        ),
    )
    result = run_recommendation(
        "CL-1", issues, 55, "Medium",
        {"overdue_follow_up": "explained"}, "", "", "Overdue.",
        client=FakeClient(mock_output),
    )
    assert isinstance(result, RecommendationResult)
    assert result.action_type == "payer_reminder"  # a REAL value, not hand-typed test data

    claim_state = _claim_state(
        latest_recommendation={
            "action_type": result.action_type,
            "low_confidence": result.low_confidence,
            "approval_status": "pending",
        }
    )
    decision, dispatch_result = route_and_dispatch(
        claim_state, {"type": "human_approved", "payload": {}}, db=_FakeEscalationDB()
    )

    assert decision.rule == 15
    assert decision.decision == AGENT_ESCALATION
    assert decision.reason_code == "agent_not_yet_implemented"
    assert decision.decision != AGENT_REMINDER
    assert isinstance(dispatch_result, EscalationResult)
    assert dispatch_result.reason_code == "agent_not_yet_implemented"
    assert dispatch_result.rule == 15
