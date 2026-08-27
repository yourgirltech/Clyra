"""Exhaustive tests for 00-commander's routing table (docs/agents/00-commander.md).

Every one of the 20 numbered rules gets its own test (or parametrized set),
named `test_rule##_<reason_code>` so `pytest -v` output lists each rule
individually rather than collapsing into one pass/fail. Malformed/missing
input and rule-ordering (first-match-wins) are covered explicitly, per rules
1 and 2's own emphasis on never crashing and never being bypassed.
"""

import pytest

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


def make_claim(
    status="Submitted",
    agent_run_in_progress=False,
    latest_recommendation=None,
    **overrides,
):
    claim = {
        "claim_id": "CL-TEST-1",
        "status": status,
        "risk_score": 50,
        "risk_level": "Medium",
        "latest_issues": [],
        "latest_recommendation": latest_recommendation,
        "agent_run_in_progress": agent_run_in_progress,
    }
    claim.update(overrides)
    return claim


def make_trigger(type_, payload=None):
    return {"type": type_, "payload": payload or {}}


def make_recommendation(action_type=None, low_confidence=False, approval_status="none"):
    return {
        "action_type": action_type,
        "confidence_band": "Low" if low_confidence else "High",
        "low_confidence": low_confidence,
        "approval_status": approval_status,
    }


# ---------------------------------------------------------------------------
# Rule 1 — invalid_trigger (malformed trigger, or claim_id doesn't resolve /
# incomplete snapshot). Covers "malformed/missing input" explicitly.
# ---------------------------------------------------------------------------

def test_rule01_invalid_trigger_none():
    decision = commander_route(make_claim(), None)
    assert decision == CommanderDecision(AGENT_ESCALATION, "invalid_trigger", 1)


def test_rule01_invalid_trigger_not_a_dict():
    decision = commander_route(make_claim(), "claim_created")
    assert decision == CommanderDecision(AGENT_ESCALATION, "invalid_trigger", 1)


def test_rule01_invalid_trigger_missing_type_key():
    decision = commander_route(make_claim(), {"payload": {}})
    assert decision == CommanderDecision(AGENT_ESCALATION, "invalid_trigger", 1)


def test_rule01_invalid_trigger_empty_type_string():
    decision = commander_route(make_claim(), make_trigger(""))
    assert decision == CommanderDecision(AGENT_ESCALATION, "invalid_trigger", 1)


def test_rule01_invalid_trigger_non_string_type():
    decision = commander_route(make_claim(), {"type": 123})
    assert decision == CommanderDecision(AGENT_ESCALATION, "invalid_trigger", 1)


def test_rule01_claim_id_does_not_resolve_none_claim_state():
    decision = commander_route(None, make_trigger("claim_created"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "invalid_trigger", 1)


def test_rule01_claim_state_not_a_dict():
    decision = commander_route("not-a-claim", make_trigger("claim_created"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "invalid_trigger", 1)


def test_rule01_incomplete_claim_state_missing_status():
    decision = commander_route({"claim_id": "CL-1"}, make_trigger("claim_created"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "invalid_trigger", 1)


def test_rule01_incomplete_claim_state_missing_claim_id():
    decision = commander_route({"status": "Submitted"}, make_trigger("claim_created"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "invalid_trigger", 1)


# ---------------------------------------------------------------------------
# Rule 2 — terminal_no_action. Every terminal status, and proof it pre-empts
# a pipeline rule that would otherwise fire (first-match-wins ordering).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["Paid", "Denied", "Rejected", "Withdrawn", "Closed"])
def test_rule02_terminal_no_action_each_terminal_status(status):
    decision = commander_route(make_claim(status=status), make_trigger("claim_evidence_updated"))
    assert decision == CommanderDecision(NO_ACTION, "terminal_no_action", 2)


def test_rule02_terminal_status_preempts_pipeline_rule():
    # claim_created would normally route to rule 6 (01-analyzer-agent) — a
    # terminal claim must never reach it, regardless of the trigger.
    decision = commander_route(make_claim(status="Paid"), make_trigger("claim_created"))
    assert decision.rule == 2
    assert decision.decision == NO_ACTION


# ---------------------------------------------------------------------------
# Rule 3 — awaiting_human_decision (recommendation pending, non-decision trigger).
# ---------------------------------------------------------------------------

def test_rule03_awaiting_human_decision_blocks_other_triggers():
    claim = make_claim(latest_recommendation=make_recommendation(approval_status="pending"))
    decision = commander_route(claim, make_trigger("claim_evidence_updated"))
    assert decision == CommanderDecision(NO_ACTION, "awaiting_human_decision", 3)


def test_rule03_does_not_block_the_approval_decision_itself():
    claim = make_claim(
        latest_recommendation=make_recommendation(
            action_type="manual_review_needed", approval_status="pending"
        )
    )
    decision = commander_route(claim, make_trigger("human_approved"))
    # Passes rule 3 and is handled by rule 16, not blocked as rule 3.
    assert decision.rule != 3


# ---------------------------------------------------------------------------
# Rule 4 — run_in_progress (idempotency guard, unconditional on trigger type).
# ---------------------------------------------------------------------------

def test_rule04_run_in_progress_blocks_pipeline_trigger():
    claim = make_claim(agent_run_in_progress=True)
    decision = commander_route(claim, make_trigger("claim_created"))
    assert decision == CommanderDecision(NO_ACTION, "run_in_progress", 4)


def test_rule04_run_in_progress_blocks_even_a_human_decision():
    claim = make_claim(
        agent_run_in_progress=True,
        latest_recommendation=make_recommendation(approval_status="pending"),
    )
    decision = commander_route(claim, make_trigger("human_approved"))
    assert decision == CommanderDecision(NO_ACTION, "run_in_progress", 4)


# ---------------------------------------------------------------------------
# Rule 5 — decision_recorded.
# ---------------------------------------------------------------------------

def test_rule05_decision_recorded_on_decline():
    claim = make_claim(latest_recommendation=make_recommendation(approval_status="pending"))
    decision = commander_route(claim, make_trigger("human_declined_action"))
    assert decision == CommanderDecision(NO_ACTION, "decision_recorded", 5)


# ---------------------------------------------------------------------------
# Rule 6 — run_analysis.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trigger_type", ["claim_created", "claim_evidence_updated"])
def test_rule06_run_analysis(trigger_type):
    decision = commander_route(make_claim(), make_trigger(trigger_type))
    assert decision == CommanderDecision(AGENT_ANALYZER, "run_analysis", 6)


# ---------------------------------------------------------------------------
# Rule 7 — analyzer_error.
# ---------------------------------------------------------------------------

def test_rule07_analyzer_error():
    decision = commander_route(make_claim(), make_trigger("analyzer_failed"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "analyzer_error", 7)


# ---------------------------------------------------------------------------
# Rule 8 — run_reasoning.
# ---------------------------------------------------------------------------

def test_rule08_run_reasoning():
    decision = commander_route(make_claim(), make_trigger("analyzer_completed"))
    assert decision == CommanderDecision(AGENT_REASONING, "run_reasoning", 8)


# ---------------------------------------------------------------------------
# Rule 9 — reasoning_error.
# ---------------------------------------------------------------------------

def test_rule09_reasoning_error():
    decision = commander_route(make_claim(), make_trigger("reasoning_failed"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "reasoning_error", 9)


# ---------------------------------------------------------------------------
# Rule 10 — run_recommendation.
# ---------------------------------------------------------------------------

def test_rule10_run_recommendation():
    decision = commander_route(make_claim(), make_trigger("reasoning_completed"))
    assert decision == CommanderDecision(AGENT_RECOMMENDATION, "run_recommendation", 10)


# ---------------------------------------------------------------------------
# Rule 11 — recommendation_error.
# ---------------------------------------------------------------------------

def test_rule11_recommendation_error():
    decision = commander_route(make_claim(), make_trigger("recommendation_failed"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "recommendation_error", 11)


# ---------------------------------------------------------------------------
# Rules 12/13 — low_confidence boolean routing, both directions.
# ---------------------------------------------------------------------------

def test_rule12_awaiting_human_approval_when_not_low_confidence():
    claim = make_claim(latest_recommendation=make_recommendation(low_confidence=False))
    decision = commander_route(claim, make_trigger("recommendation_completed"))
    assert decision == CommanderDecision(NO_ACTION, "awaiting_human_approval", 12)


def test_rule13_low_confidence_escalates_instead_of_one_click_approval():
    claim = make_claim(latest_recommendation=make_recommendation(low_confidence=True))
    decision = commander_route(claim, make_trigger("recommendation_completed"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "low_confidence", 13)


def test_rule12_missing_recommendation_defaults_to_not_low_confidence():
    # No latest_recommendation at all — commander must not crash, and must not
    # assume low confidence just because data is thin.
    claim = make_claim(latest_recommendation=None)
    decision = commander_route(claim, make_trigger("recommendation_completed"))
    assert decision == CommanderDecision(NO_ACTION, "awaiting_human_approval", 12)


# ---------------------------------------------------------------------------
# Rules 14/15 — an approved follow_up/payer_reminder dispatches to the real
# executor agent. (Phase 4 briefly carved these out to escalation while 04/05
# didn't exist yet; both are implemented now, so the rule table matches its
# original, final design again — see docs/agents/00-commander.md.)
# ---------------------------------------------------------------------------

def test_rule14_follow_up_approved_dispatches_to_04():
    claim = make_claim(latest_recommendation=make_recommendation(action_type="follow_up"))
    decision = commander_route(claim, make_trigger("human_approved"))
    assert decision == CommanderDecision(AGENT_FOLLOWUP, "execute_followup", 14)
    assert decision.decision != AGENT_ESCALATION


def test_rule15_payer_reminder_approved_dispatches_to_05():
    claim = make_claim(latest_recommendation=make_recommendation(action_type="payer_reminder"))
    decision = commander_route(claim, make_trigger("human_approved"))
    assert decision == CommanderDecision(AGENT_REMINDER, "execute_reminder", 15)
    assert decision.decision != AGENT_ESCALATION


# ---------------------------------------------------------------------------
# Rule 16 — approval_acknowledged_no_agent_needed.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action_type", ["manual_review_needed", "no_action_needed"])
def test_rule16_approval_acknowledged_no_agent_needed(action_type):
    claim = make_claim(latest_recommendation=make_recommendation(action_type=action_type))
    decision = commander_route(claim, make_trigger("human_approved"))
    assert decision == CommanderDecision(NO_ACTION, "approval_acknowledged_no_agent_needed", 16)


# ---------------------------------------------------------------------------
# Rule 17 — followup_execution_failed.
# ---------------------------------------------------------------------------

def test_rule17_followup_execution_failed():
    decision = commander_route(make_claim(), make_trigger("followup_failed"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "followup_execution_failed", 17)


# ---------------------------------------------------------------------------
# Rule 18 — reminder_execution_failed.
# ---------------------------------------------------------------------------

def test_rule18_reminder_execution_failed():
    decision = commander_route(make_claim(), make_trigger("reminder_failed"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "reminder_execution_failed", 18)


# ---------------------------------------------------------------------------
# Rule 19 — action_executed.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trigger_type", ["followup_completed", "reminder_completed"])
def test_rule19_action_executed(trigger_type):
    decision = commander_route(make_claim(), make_trigger(trigger_type))
    assert decision == CommanderDecision(NO_ACTION, "action_executed", 19)


# ---------------------------------------------------------------------------
# Rule 20 — unclassified_trigger catch-all, including the human_approved edge
# case where action_type is outside the fixed set 03-recommendation-agent emits.
# ---------------------------------------------------------------------------

def test_rule20_unclassified_trigger_unknown_event():
    decision = commander_route(make_claim(), make_trigger("some_event_commander_has_never_seen"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "unclassified_trigger", 20)


def test_rule20_human_approved_with_unrecognized_action_type():
    claim = make_claim(latest_recommendation=make_recommendation(action_type="not_a_real_action_type"))
    decision = commander_route(claim, make_trigger("human_approved"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "unclassified_trigger", 20)


def test_rule20_human_approved_with_missing_action_type():
    claim = make_claim(latest_recommendation=make_recommendation(action_type=None))
    decision = commander_route(claim, make_trigger("human_approved"))
    assert decision == CommanderDecision(AGENT_ESCALATION, "unclassified_trigger", 20)


# ---------------------------------------------------------------------------
# dispatch_stub — build-step-1 placeholder for actually invoking 01-06.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "agent_name",
    [AGENT_ANALYZER, AGENT_REASONING, AGENT_RECOMMENDATION, AGENT_FOLLOWUP, AGENT_REMINDER, AGENT_ESCALATION],
)
def test_dispatch_stub_returns_placeholder_for_every_agent(agent_name):
    assert dispatch_stub(agent_name) == f"would call: {agent_name}"
