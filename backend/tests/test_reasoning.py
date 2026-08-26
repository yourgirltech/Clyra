"""Tests for 02-reasoning-agent (backend/app/agents/reasoning.py) and its
wiring into Commander's dispatch (backend/app/agents/dispatch.py).

The LLM call is mocked for every test in this file — grounding, refusal to
invent issues, the empty-issues short-circuit, and malformed-input failure
routing are all verified without touching the network. The one real Claude
API call lives in test_reasoning_live.py, run separately and on purpose.
"""

from types import SimpleNamespace

import pytest

from app.agents.commander import (
    AGENT_ESCALATION,
    AGENT_FOLLOWUP,
    AGENT_REASONING,
    AGENT_RECOMMENDATION,
    AGENT_REMINDER,
    commander_route,
)
from app.agents.dispatch import route_and_dispatch
from app.agents.reasoning import (
    IssueExplanation,
    ReasoningFailure,
    ReasoningOutput,
    ReasoningResult,
    run_reasoning,
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


def make_issue(issue_type="missing_authorization", severity="high", evidence=None):
    if evidence is None:  # distinct from an intentionally empty {} in the malformed-input tests
        evidence = {"some_field": 0}
    return Issue(
        issue_type=issue_type,
        severity=severity,
        description=f"{issue_type} description",
        evidence=evidence,
    )


def make_claim_context(**overrides):
    ctx = {"payer": "Example Health", "amount": 1240.0, "status": "At Risk", "claim_age_days": 12}
    ctx.update(overrides)
    return ctx


# ---------------------------------------------------------------------------
# Grounding: explanations must match the given issues, no more, no less.
# ---------------------------------------------------------------------------

def test_grounded_explanation_returns_result_covering_given_issues():
    issues = [make_issue("missing_authorization", "high"), make_issue("code_mismatch", "medium")]
    mock_output = ReasoningOutput(
        issue_explanations=[
            IssueExplanation(issue_type="missing_authorization", explanation="Auth is required and absent."),
            IssueExplanation(issue_type="code_mismatch", explanation="Coding doesn't match payer rules."),
        ],
        cross_issue_notes="Missing authorization combined with a coding mismatch compounds denial risk.",
        uncertainty_notes="",
        summary="Two issues found; authorization is the more severe of the two.",
    )
    client = FakeClient(mock_output)

    result = run_reasoning("CL-1", issues, 80, "High", make_claim_context(), client=client)

    assert isinstance(result, ReasoningResult)
    assert client.messages.calls == 1
    assert set(result.issue_explanations.keys()) == {"missing_authorization", "code_mismatch"}
    assert "compounds" in result.cross_issue_notes
    assert result.summary
    assert result.raw_model_response  # full structured output preserved for audit


def test_refuses_to_invent_an_issue_not_in_the_list():
    issues = [make_issue("missing_authorization", "high")]
    # Model hallucinates a second issue that was never in the input.
    mock_output = ReasoningOutput(
        issue_explanations=[
            IssueExplanation(issue_type="missing_authorization", explanation="Auth is required and absent."),
            IssueExplanation(issue_type="fraud_suspected", explanation="This claim looks fraudulent."),
        ],
        cross_issue_notes="",
        uncertainty_notes="",
        summary="Fabricated summary.",
    )
    client = FakeClient(mock_output)

    result = run_reasoning("CL-1", issues, 50, "High", make_claim_context(), client=client)

    assert isinstance(result, ReasoningFailure)
    assert result.reason == "ungrounded_output"
    assert "fraud_suspected" in result.detail


# ---------------------------------------------------------------------------
# Empty issue list: "no issues to explain," no model call at all.
# ---------------------------------------------------------------------------

def test_empty_issue_list_short_circuits_without_calling_the_model():
    client = FakeClient(parsed_output=None)  # would fail loudly if actually called

    result = run_reasoning("CL-1", [], 0, "Low", make_claim_context(), client=client)

    assert isinstance(result, ReasoningResult)
    assert result.summary == "No issues to explain."
    assert result.issue_explanations == {}
    assert client.messages.calls == 0


# ---------------------------------------------------------------------------
# Malformed input: structured failure, never a crash, routes to rule 9.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "claim_id,issues,risk_score,risk_level,claim_context",
    [
        (None, [make_issue()], 50, "High", make_claim_context()),
        ("", [make_issue()], 50, "High", make_claim_context()),
        ("CL-1", "not-a-list", 50, "High", make_claim_context()),
        ("CL-1", [{"issue_type": "x"}], 50, "High", make_claim_context()),  # not an Issue, missing fields
        ("CL-1", [make_issue(evidence={})], 50, "High", make_claim_context()),  # empty evidence
        ("CL-1", [make_issue()], 150, "High", make_claim_context()),  # score out of range
        ("CL-1", [make_issue()], 50, "Extreme", make_claim_context()),  # invalid level
        ("CL-1", [make_issue()], 50, "High", {"payer": "X"}),  # missing context fields
    ],
)
def test_malformed_input_returns_structured_failure_not_a_crash(
    claim_id, issues, risk_score, risk_level, claim_context
):
    client = FakeClient(parsed_output=None)  # must never be reached

    result = run_reasoning(claim_id, issues, risk_score, risk_level, claim_context, client=client)

    assert isinstance(result, ReasoningFailure)
    assert result.reason == "malformed_input"
    assert client.messages.calls == 0


def test_malformed_input_failure_routes_to_commander_rule9_escalation():
    # The failure itself doesn't call Commander — but the reasoning_failed
    # trigger it implies is exactly what Commander's rule 9 escalates.
    client = FakeClient(parsed_output=None)
    result = run_reasoning("CL-1", "not-a-list", 50, "High", make_claim_context(), client=client)
    assert isinstance(result, ReasoningFailure)

    claim_state = {
        "claim_id": "CL-1",
        "status": "Submitted",
        "risk_score": 50,
        "risk_level": "High",
        "latest_issues": [],
        "latest_recommendation": None,
        "agent_run_in_progress": False,
    }
    decision = commander_route(claim_state, {"type": "reasoning_failed", "payload": {}})
    assert decision.rule == 9
    assert decision.decision == AGENT_ESCALATION
    assert decision.reason_code == "reasoning_error"


def test_llm_exception_returns_structured_failure_not_a_crash():
    class ExplodingMessages:
        def parse(self, **kwargs):
            raise RuntimeError("network exploded")

    class ExplodingClient:
        messages = ExplodingMessages()

    result = run_reasoning(
        "CL-1", [make_issue()], 50, "High", make_claim_context(), client=ExplodingClient()
    )

    assert isinstance(result, ReasoningFailure)
    assert result.reason == "llm_call_failed"
    assert "network exploded" in result.detail


# ---------------------------------------------------------------------------
# Commander's rule 8 actually invokes the reasoning agent now.
# ---------------------------------------------------------------------------

def test_rule08_dispatches_a_real_reasoning_run_not_a_stub():
    issues = [make_issue("missing_authorization", "high")]
    mock_output = ReasoningOutput(
        issue_explanations=[
            IssueExplanation(issue_type="missing_authorization", explanation="Explained."),
        ],
        cross_issue_notes="",
        uncertainty_notes="",
        summary="One issue found.",
    )
    client = FakeClient(mock_output)

    claim_state = {
        "claim_id": "CL-1",
        "status": "Submitted",
        "risk_score": 50,
        "risk_level": "High",
        "latest_issues": [],
        "latest_recommendation": None,
        "agent_run_in_progress": False,
    }
    decision, result = route_and_dispatch(
        claim_state,
        {"type": "analyzer_completed", "payload": {}},
        reasoning_issues=issues,
        reasoning_risk_score=50,
        reasoning_risk_level="High",
        reasoning_claim_context=make_claim_context(),
        anthropic_client=client,
    )

    assert decision.rule == 8
    assert decision.decision == AGENT_REASONING
    assert isinstance(result, ReasoningResult)
    assert result.summary == "One issue found."


def test_rule08_missing_required_inputs_raises_rather_than_guessing():
    claim_state = {
        "claim_id": "CL-1",
        "status": "Submitted",
        "risk_score": 50,
        "risk_level": "High",
        "latest_issues": [],
        "latest_recommendation": None,
        "agent_run_in_progress": False,
    }
    with pytest.raises(ValueError):
        route_and_dispatch(claim_state, {"type": "analyzer_completed", "payload": {}})


# ---------------------------------------------------------------------------
# 03-06 remain stubbed. Same guard pattern as the rule-6/rule-8 "is it real"
# tests above, just asserting the opposite: dispatch_stub's placeholder
# string, never a real result object.
#
# 03-recommendation-agent (rule 10) and 06-escalation-agent (rules 7, 9, and
# the rule 14/15 Phase-4 carve-out) are each directly reachable through
# Commander's decision.decision, so route_and_dispatch's fallback branch
# (`dispatch_stub(decision.decision)`) is what's under test for them.
#
# 04-followup-agent and 05-reminder-agent are different: Commander's Phase 4
# build scope means decision.decision can never actually equal AGENT_FOLLOWUP
# or AGENT_REMINDER in the first place (see docs/agents/00-commander.md's
# "Design scope vs. Phase 4 implementation") — an approved follow_up/
# payer_reminder routes to escalation instead (rules 14/15), which
# test_commander.py already proves at the routing level
# (test_rule14_..._not_04 / test_rule15_..._not_05). The two rule-14/15 cases
# below re-confirm the same thing one layer up, at dispatch: since Commander
# itself never emits AGENT_FOLLOWUP/AGENT_REMINDER as a decision, dispatch.py
# has no real-agent branch for either — there's nothing to stub around.
# ---------------------------------------------------------------------------

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


@pytest.mark.parametrize(
    "rule,trigger,claim_state,expected_agent",
    [
        (10, {"type": "reasoning_completed", "payload": {}}, _claim_state(), AGENT_RECOMMENDATION),
        (7, {"type": "analyzer_failed", "payload": {}}, _claim_state(), AGENT_ESCALATION),
        (9, {"type": "reasoning_failed", "payload": {}}, _claim_state(), AGENT_ESCALATION),
        (
            14,
            {"type": "human_approved", "payload": {}},
            _claim_state(latest_recommendation={"action_type": "follow_up", "low_confidence": False, "approval_status": "pending"}),
            AGENT_ESCALATION,
        ),
        (
            15,
            {"type": "human_approved", "payload": {}},
            _claim_state(latest_recommendation={"action_type": "payer_reminder", "low_confidence": False, "approval_status": "pending"}),
            AGENT_ESCALATION,
        ),
    ],
)
def test_agents_beyond_02_are_still_stubbed(rule, trigger, claim_state, expected_agent):
    decision, result = route_and_dispatch(claim_state, trigger)

    assert decision.rule == rule
    assert decision.decision == expected_agent
    assert result == f"would call: {expected_agent}"
    # Never the real dataclasses 03/04/05/06 would eventually return.
    assert not hasattr(result, "issue_explanations")
    assert not hasattr(result, "risk_score")


def test_04_and_05_are_never_even_reachable_as_a_commander_decision():
    # Direct confirmation that AGENT_FOLLOWUP/AGENT_REMINDER never appear as
    # decision.decision in Phase 4 — dispatch has no real branch for them
    # because Commander itself never routes there (rules 14/15 carve-out).
    follow_up_state = _claim_state(
        latest_recommendation={"action_type": "follow_up", "low_confidence": False, "approval_status": "pending"}
    )
    decision = commander_route(follow_up_state, {"type": "human_approved", "payload": {}})
    assert decision.decision != AGENT_FOLLOWUP

    reminder_state = _claim_state(
        latest_recommendation={"action_type": "payer_reminder", "low_confidence": False, "approval_status": "pending"}
    )
    decision = commander_route(reminder_state, {"type": "human_approved", "payload": {}})
    assert decision.decision != AGENT_REMINDER
