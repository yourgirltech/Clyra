# 00 — Commander

## Status
Planning document. No runtime (Python / n8n / other) has been chosen. This file describes decision logic only — nothing here implies an implementation.

## Role
Commander is a pure decision node. Given the current state of one claim and a triggering event, it decides which single specialist agent (if any) runs next. It never talks to a user, never generates content, never calls a tool, and never executes an action itself. Its entire behavior is the ordered rule table below — nothing else. This makes Commander fully auditable: for any claim + event pair, the routing decision can be verified by reading the table, no model call required.

Commander's scope is the **claim lifecycle only** — agents 01 through 06. [07-assistant-agent](./07-assistant-agent.md) is invoked directly by the AI Assistant chat UI when a user sends a message; it is not dispatched by Commander's rule table, because it isn't reacting to a claim-state trigger, it's reacting to a chat message. See the note at the bottom of this file for why that split is deliberate rather than an oversight.

## Inputs
Commander receives exactly two things per invocation:

1. **Claim state** — a read-only snapshot:
   - `claim_id`, `status` (current claim status string)
   - `risk_score`, `risk_level` (last computed values, if any)
   - `latest_issues` (last Analyzer output for this claim, if any)
   - `latest_recommendation` — `{ action_type, confidence_band, low_confidence, approval_status }` if one exists (`approval_status` ∈ `pending | approved | declined | none`). `low_confidence` is the boolean flag [03-recommendation-agent](./03-recommendation-agent.md) actually emits — Commander's rules key off that boolean directly, never off `confidence_band` or a numeric score.
   - `agent_run_in_progress` — boolean, whether an agent is currently executing for this claim (idempotency guard)
2. **Trigger event** — `{ type, payload }`. See the trigger taxonomy below.

Commander does not fetch anything itself. If the state snapshot it was handed is incomplete or the referenced claim doesn't exist, that is itself a routable condition (rule 1).

## Output
A single routing decision: either the name of exactly one agent to invoke next, or `no_action` with a reason code. Reason codes exist so every "nothing happens" outcome is still logged and explainable, never a silent no-op.

## Claim status taxonomy (for this rule table)
- **Terminal statuses** (claim lifecycle is over): `Paid`, `Denied`, `Rejected`, `Withdrawn`/`Closed`.
- **Open statuses** (claim lifecycle is active): `Draft`, `Submitted`, `Processing`, `At Risk`, `Needs Review`.

> Assumption flagged for review: the backend's current seed data (`backend/scripts/seed_claims.py`) uses `Draft, Submitted, Processing, At Risk, Denied, Paid, Needs Review` — it does not yet have a distinct `Rejected` status. The product brief for this roadmap calls out `Rejected` as its own terminal state (commonly: clearinghouse/eligibility rejection *before* payer adjudication, vs. `Denied` = payer adjudicated and refused). This table treats them as distinct terminal statuses on the assumption that distinction gets added to the status field later. If `Rejected` and `Denied` turn out to be the same status in practice, collapse them — the rule table's logic doesn't change either way.

## Trigger event taxonomy
Each pipeline stage emits either a `*_completed` or a `*_failed` event; nothing is inferred from silence.

`claim_created`, `claim_evidence_updated`, `analyzer_completed`, `analyzer_failed`, `reasoning_completed`, `reasoning_failed`, `recommendation_completed`, `recommendation_failed`, `human_approved`, `human_declined_action`, `followup_completed`, `followup_failed`, `reminder_completed`, `reminder_failed`.

## Decision logic — ordered rule table
Rules are evaluated top to bottom. **First match wins.** Safety/terminal guards (1–5) are checked before any pipeline rule, so a terminal or locked claim can never reach a downstream agent regardless of what event just arrived.

| # | Condition | Decision | Reason code |
|---|---|---|---|
| 1 | Trigger is malformed, or `claim_id` does not resolve to a claim | → **06-escalation-agent** | `invalid_trigger` |
| 2 | `claim.status` is a terminal status (`Paid`, `Denied`, `Rejected`, `Withdrawn`/`Closed`) | → **no_action** | `terminal_no_action` |
| 3 | `latest_recommendation.approval_status == pending` **and** the incoming trigger is not the approval decision itself (`human_approved` / `human_declined_action`) | → **no_action** | `awaiting_human_decision` — never generate a second recommendation while one is outstanding |
| 4 | `agent_run_in_progress == true` for this claim | → **no_action** | `run_in_progress` — defer, re-evaluate on the next event rather than double-invoke |
| 5 | Trigger = `human_declined_action` | → **no_action** | `decision_recorded` — log the decline, claim returns to steady state; it re-enters the table only if new evidence later produces `claim_evidence_updated` |
| 6 | Trigger = `claim_created` or `claim_evidence_updated` | → **01-analyzer-agent** | `run_analysis` |
| 7 | Trigger = `analyzer_failed` | → **06-escalation-agent** | `analyzer_error` |
| 8 | Trigger = `analyzer_completed` | → **02-reasoning-agent** | `run_reasoning` |
| 9 | Trigger = `reasoning_failed` | → **06-escalation-agent** | `reasoning_error` |
| 10 | Trigger = `reasoning_completed` | → **03-recommendation-agent** | `run_recommendation` |
| 11 | Trigger = `recommendation_failed` | → **06-escalation-agent** | `recommendation_error` |
| 12 | Trigger = `recommendation_completed` and `low_confidence == false` | → **no_action** | `awaiting_human_approval` — surfaced in the UI for a human to approve/decline; Commander does not act further until it sees `human_approved` or `human_declined_action` |
| 13 | Trigger = `recommendation_completed` and `low_confidence == true` | → **06-escalation-agent** | `low_confidence` — a low-confidence recommendation is never shown as a one-click approval; see [03-recommendation-agent](./03-recommendation-agent.md) |
| 14 | Trigger = `human_approved` and `recommendation.action_type == follow_up` | → **04-followup-agent** | `execute_followup` |
| 15 | Trigger = `human_approved` and `recommendation.action_type == payer_reminder` | → **05-reminder-agent** | `execute_reminder` |
| 16 | Trigger = `human_approved` and `recommendation.action_type` is `manual_review_needed` or `no_action_needed` | → **no_action** | `approval_acknowledged_no_agent_needed` — the human's decision is the terminal step for these two action types; there is nothing left for an agent to execute, so this is not an escalation |
| 17 | Trigger = `followup_failed` (agent's own retries already exhausted) | → **06-escalation-agent** | `followup_execution_failed` |
| 18 | Trigger = `reminder_failed` (agent's own retries already exhausted) | → **06-escalation-agent** | `reminder_execution_failed` |
| 19 | Trigger = `followup_completed` or `reminder_completed` | → **no_action** | `action_executed` — log success, claim returns to steady state |
| 20 | Nothing above matched | → **06-escalation-agent** | `unclassified_trigger` — an event Commander doesn't recognize is never silently dropped |

## What Commander explicitly does NOT do
- Does not decide *what* a recommendation says, only *whether* the pipeline continues.
- Does not retry a failed agent itself — retry policy lives inside each agent (see [04](./04-followup-agent.md)/[05](./05-reminder-agent.md)).
- Does not execute or approve anything. Rule 12 is the hard stop where only a human can move the claim forward.
- Does not hold conversation state — that belongs to [07-assistant-agent](./07-assistant-agent.md).

## Design scope vs. Phase 4 implementation
The 20-rule table above is the **complete, final design** for Commander — it includes routing to [04-followup-agent](./04-followup-agent.md) and [05-reminder-agent](./05-reminder-agent.md) (rules 14/15) even though those two agents are not built until Phase 6. This is deliberate: writing the full design now means Commander's decision logic doesn't need to be revisited or rewritten when Phase 6 lands, only the already-specified rules get wired to real code.

**Phase 4 build scope** — the rules that go live with real behavior behind them: 1–13, 16, 19, 20. Every one of these either dispatches to an agent that exists in Phase 4 (01, 02, 03), or resolves to `no_action`/escalation, neither of which depends on 04 or 05 existing.

**Rules 14 and 15 depend on agents that don't exist yet in Phase 4.** [03-recommendation-agent](./03-recommendation-agent.md) can still produce a `follow_up` or `payer_reminder` recommendation in Phase 4 (e.g., so the UI can show "follow-up recommended" for a human to act on manually, outside the system) — and a human can still approve it. So Commander must not assume rules 14/15 are unreachable in Phase 4; it has to handle them safely rather than assuming they'll never fire.

**Safe fallback:** Phase 4's implementation of rules 14 and 15 is *not* "dispatch to 04/05" — it's "route to [06-escalation-agent](./06-escalation-agent.md) with reason `agent_not_yet_implemented`." Same shape as the rule 20 catch-all, just scoped to these two specific rules. This guarantees Commander never crashes or silently drops an approved action just because the executor agent hasn't been built yet — the human sees an honest "this was approved but can't be auto-executed yet" flag instead. When Phase 6 ships 04/05, this fallback is deleted and rules 14/15 dispatch for real; the rule table itself does not change.

## Why 07-assistant-agent sits outside this table
Rules 1–20 all key off *claim lifecycle* events tied to one claim's automated pipeline. The Assistant is reactive to a human typing a question in the AI Assistant page — it isn't advancing any claim's pipeline, and a single Assistant session may span multiple claims or none at all (e.g. "how many claims are at high risk this week?"). Forcing it through a claim-state routing table would misrepresent what it does. Instead, the Assistant UI invokes 07 directly, and 07 operates under the same guardrails as every other agent (no direct action execution — see [07-assistant-agent.md](./07-assistant-agent.md)) without being part of Commander's state machine. Terminal-claim guard (rule 2) still applies in spirit for 07: it may *discuss* a terminal claim read-only, it may never propose that a terminal claim receive a new automated action.

## Open questions (not decided here)
- How [03-recommendation-agent](./03-recommendation-agent.md) internally decides `low_confidence` (i.e., which confidence band(s) map to `true`) — Commander only ever reads the resulting boolean, it does not own or duplicate that logic.
- Whether `Rejected` becomes a real distinct status value or collapses into `Denied` (see taxonomy note above).
- Runtime: Python orchestrator vs. n8n vs. other — explicitly deferred, not part of this document.
