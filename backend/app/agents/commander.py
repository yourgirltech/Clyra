"""00-commander — pure decision node for the claim-lifecycle agent pipeline.

Implements the ordered rule table from docs/agents/00-commander.md exactly:
rules are evaluated top to bottom, first match wins. Commander itself makes
no I/O calls of any kind — it is handed a read-only claim-state snapshot and
a trigger event, and returns a single routing decision. Fetching that
snapshot, invoking the returned agent, and persisting anything are all the
caller's responsibility, not Commander's.

This module is Phase 4 build step 1: Commander's routing logic only. No
specialist agent (01-06) is implemented yet — `dispatch_stub` stands in for
"Commander would invoke this agent now" without actually calling anything.
"""

from __future__ import annotations

from dataclasses import dataclass

# Agent names Commander can route to. 01-05 are not built yet (see dispatch_stub);
# 06-escalation-agent is the target of every non-happy-path rule from day one.
AGENT_ANALYZER = "01-analyzer-agent"
AGENT_REASONING = "02-reasoning-agent"
AGENT_RECOMMENDATION = "03-recommendation-agent"
AGENT_FOLLOWUP = "04-followup-agent"
AGENT_REMINDER = "05-reminder-agent"
AGENT_ESCALATION = "06-escalation-agent"

# Sentinel decision meaning "no agent is invoked."
NO_ACTION = "no_action"

# Claim status taxonomy (docs/agents/00-commander.md, "Claim status taxonomy").
TERMINAL_STATUSES = frozenset({"Paid", "Denied", "Rejected", "Withdrawn", "Closed"})

# Trigger types that represent the human resolving an outstanding approval.
_APPROVAL_DECISION_TRIGGERS = frozenset({"human_approved", "human_declined_action"})

# Action types 03-recommendation-agent can emit (docs/agents/03-recommendation-agent.md).
_EXECUTABLE_ACTION_TYPES = frozenset({"follow_up", "payer_reminder"})
_NON_EXECUTABLE_ACTION_TYPES = frozenset({"manual_review_needed", "no_action_needed"})


@dataclass(frozen=True)
class CommanderDecision:
    """One routing outcome: either the single agent to invoke next, or NO_ACTION."""

    decision: str  # one of the AGENT_* constants, or NO_ACTION
    reason_code: str
    rule: int  # which numbered rule in the table produced this decision (1-20)


def _is_valid_trigger(trigger: object) -> bool:
    if not isinstance(trigger, dict):
        return False
    trigger_type = trigger.get("type")
    return isinstance(trigger_type, str) and trigger_type != ""


def _is_valid_claim_state(claim_state: object) -> bool:
    # Commander does not fetch the claim itself. A caller who could not resolve
    # claim_id to a claim, or who hands Commander an incomplete snapshot, signals
    # that by passing None or a dict missing the required fields — either way,
    # that is itself a routable condition (rule 1), not an exception to raise.
    if not isinstance(claim_state, dict):
        return False
    return "claim_id" in claim_state and "status" in claim_state


def commander_route(claim_state: dict | None, trigger: dict | None) -> CommanderDecision:
    """Evaluate Commander's 20-rule table against one claim_state + trigger pair.

    Pure function: no I/O, no database access, no calls to any other agent.
    `claim_state` is the read-only snapshot described in the Commander design
    doc (claim_id, status, risk_score, risk_level, latest_issues,
    latest_recommendation, agent_run_in_progress) — pass `None` to represent
    "claim_id did not resolve to a claim." `trigger` is `{"type": ..., "payload": ...}`.
    """
    # Rule 1 — malformed trigger, or claim_id does not resolve / incomplete snapshot.
    if not _is_valid_trigger(trigger) or not _is_valid_claim_state(claim_state):
        return CommanderDecision(AGENT_ESCALATION, "invalid_trigger", 1)

    trigger_type: str = trigger["type"]  # type: ignore[index]
    status = claim_state.get("status")

    # Rule 2 — terminal claim, never dispatch further regardless of trigger.
    if status in TERMINAL_STATUSES:
        return CommanderDecision(NO_ACTION, "terminal_no_action", 2)

    latest_recommendation = claim_state.get("latest_recommendation") or {}
    approval_status = latest_recommendation.get("approval_status", "none")

    # Rule 3 — a recommendation is outstanding; only the approval decision itself
    # may proceed while it's pending.
    if approval_status == "pending" and trigger_type not in _APPROVAL_DECISION_TRIGGERS:
        return CommanderDecision(NO_ACTION, "awaiting_human_decision", 3)

    # Rule 4 — idempotency guard, unconditional on trigger type.
    if claim_state.get("agent_run_in_progress"):
        return CommanderDecision(NO_ACTION, "run_in_progress", 4)

    # Rule 5 — decline recorded, claim returns to steady state.
    if trigger_type == "human_declined_action":
        return CommanderDecision(NO_ACTION, "decision_recorded", 5)

    # Rule 6 — new/updated claim evidence starts the pipeline.
    if trigger_type in ("claim_created", "claim_evidence_updated"):
        return CommanderDecision(AGENT_ANALYZER, "run_analysis", 6)

    # Rule 7
    if trigger_type == "analyzer_failed":
        return CommanderDecision(AGENT_ESCALATION, "analyzer_error", 7)

    # Rule 8
    if trigger_type == "analyzer_completed":
        return CommanderDecision(AGENT_REASONING, "run_reasoning", 8)

    # Rule 9
    if trigger_type == "reasoning_failed":
        return CommanderDecision(AGENT_ESCALATION, "reasoning_error", 9)

    # Rule 10
    if trigger_type == "reasoning_completed":
        return CommanderDecision(AGENT_RECOMMENDATION, "run_recommendation", 10)

    # Rule 11
    if trigger_type == "recommendation_failed":
        return CommanderDecision(AGENT_ESCALATION, "recommendation_error", 11)

    # Rules 12/13 — low_confidence is the boolean 03-recommendation-agent emits;
    # Commander keys off it directly, never off confidence_band or a numeric score.
    if trigger_type == "recommendation_completed":
        low_confidence = bool(latest_recommendation.get("low_confidence", False))
        if not low_confidence:
            return CommanderDecision(NO_ACTION, "awaiting_human_approval", 12)
        return CommanderDecision(AGENT_ESCALATION, "low_confidence", 13)

    # Rules 14/15/16 — human approved a recommendation; which agent (if any) runs
    # next depends on the approved action_type.
    if trigger_type == "human_approved":
        action_type = latest_recommendation.get("action_type")

        # Rules 14/15 — Phase 4 build-scope carve-out. 04-followup-agent and
        # 05-reminder-agent don't exist yet, so an approved follow_up/payer_reminder
        # is routed to escalation with a distinct reason rather than dispatched —
        # same shape as the rule 20 catch-all, scoped to just these two rules.
        # When 04/05 ship (Phase 6), this carve-out is deleted and rules 14/15
        # dispatch for real; the rule table itself does not change.
        if action_type == "follow_up":
            return CommanderDecision(AGENT_ESCALATION, "agent_not_yet_implemented", 14)
        if action_type == "payer_reminder":
            return CommanderDecision(AGENT_ESCALATION, "agent_not_yet_implemented", 15)

        # Rule 16 — these two action types have no executor agent, ever; the
        # human's decision is itself the terminal step.
        if action_type in _NON_EXECUTABLE_ACTION_TYPES:
            return CommanderDecision(NO_ACTION, "approval_acknowledged_no_agent_needed", 16)

        # An action_type outside the fixed set 03-recommendation-agent may emit —
        # falls through to the rule 20 catch-all below, same as any other
        # unrecognized event.

    # Rule 17
    elif trigger_type == "followup_failed":
        return CommanderDecision(AGENT_ESCALATION, "followup_execution_failed", 17)

    # Rule 18
    elif trigger_type == "reminder_failed":
        return CommanderDecision(AGENT_ESCALATION, "reminder_execution_failed", 18)

    # Rule 19
    elif trigger_type in ("followup_completed", "reminder_completed"):
        return CommanderDecision(NO_ACTION, "action_executed", 19)

    # Rule 20 — catch-all. An event Commander doesn't recognize (including an
    # unrecognized action_type on an otherwise-valid human_approved trigger) is
    # never silently dropped.
    return CommanderDecision(AGENT_ESCALATION, "unclassified_trigger", 20)


def dispatch_stub(agent_name: str) -> str:
    """Placeholder for actually invoking a specialist agent.

    Build step 1 implements Commander's routing logic only — 01-06 don't exist
    yet. Once a real agent is wired up, its invocation replaces the
    corresponding branch here; until then this makes "Commander would call X"
    visible and testable without pretending X runs.
    """
    return f"would call: {agent_name}"
