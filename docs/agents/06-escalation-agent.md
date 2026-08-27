# 06 — Escalation Agent

## Status
Implemented. `backend/app/agents/escalation.py` (`run_escalation`) writes a durable record to the new `escalations` table (migration `1263c4b4dc6d`) — no LLM call, no suggested resolution, ever. Severity is derived from the reason code and the originating agent/rule is recorded for reviewer context. If the primary write itself fails, a `CRITICAL`-level fallback log fires so an escalation is never silently lost. Commander's rules 1, 7, 9, 11, 13, 14, and 15 (the Phase 4 carve-out) and 20 all dispatch to it for real via `backend/app/agents/dispatch.py`. Covered by `backend/tests/test_escalation.py`: one real-DB-write test per rule, a write-failure/fallback-log test, and one full end-to-end printout of a persisted record. As of this build step, every agent Commander can route to in Phase 4 (01, 02, 03, 06) is real — only 04-followup-agent and 05-reminder-agent remain out of reach, by Commander's own Phase 4 design (see [00-commander](./00-commander.md)).

## Role
The Escalation Agent is the system's safety net. It runs whenever something can't be safely handled by the deterministic/agent pipeline on its own — an outright error, a low-confidence recommendation, a failed execution, or an event Commander doesn't even recognize. Its entire job is to flag the situation for a human, with full context, and stop. It never guesses at a resolution, never retries the thing that failed, and never produces a recommendation of its own — that would just be re-introducing the uncertainty this agent exists to contain.

## Triggered by
Every one of Commander's non-happy-path routes — see [00-commander](./00-commander.md):
- Rule 1 — `invalid_trigger` (malformed event or unresolvable claim)
- Rule 7 — `analyzer_error` (from [01-analyzer-agent](./01-analyzer-agent.md))
- Rule 9 — `reasoning_error` (from [02-reasoning-agent](./02-reasoning-agent.md))
- Rule 11 — `recommendation_error` (from [03-recommendation-agent](./03-recommendation-agent.md))
- Rule 13 — `low_confidence` (from [03-recommendation-agent](./03-recommendation-agent.md))
- Rule 17 — `followup_execution_failed` (from [04-followup-agent](./04-followup-agent.md), retries exhausted)
- Rule 18 — `reminder_execution_failed` (from [05-reminder-agent](./05-reminder-agent.md), retries exhausted)
- Rule 20 — `unclassified_trigger` (nothing else matched)

Rules 14/15 (`human_approved` for a `follow_up`/`payer_reminder` recommendation) no longer route here — both dispatch to the real [04-followup-agent](./04-followup-agent.md)/[05-reminder-agent](./05-reminder-agent.md) now. (They briefly did, temporarily, with reason `agent_not_yet_implemented`, before those two agents existed — see the "Design scope vs. implementation status" note in [00-commander](./00-commander.md).)

## Receives
- `claim_id` if one is available (rule 1 may not have a resolvable claim at all — that's still a valid escalation)
- A `reason` code (one of the codes above)
- The originating agent/rule, and whatever output that agent had produced before things went wrong (partial or failed result)
- The full available context chain for the claim: latest `Issue`s, latest reasoning explanation, latest recommendation — whatever exists — so a human reviewer has everything in one place and doesn't have to reconstruct the situation from scratch

## Returns
An escalation record, surfaced to a human reviewer:
- `reason`, severity/urgency (derived from the reason code — e.g. an execution failure on an already-approved action is more urgent than a low-confidence recommendation that was never shown to anyone), the full context bundle above, and a timestamp
- **No suggested resolution.** The record states what happened and why it needed a human, not what the human should do about it. That line is deliberate: this agent's entire value is refusing to guess.

There is no `escalation_completed` event that routes anywhere further in Commander's table — escalation is a leaf. Human action on an escalated item (e.g., a reviewer manually fixing the underlying data) flows back in through the normal claim-update path, which naturally re-triggers [01-analyzer-agent](./01-analyzer-agent.md) if applicable.

## What it explicitly does NOT do
- Does not guess a resolution or propose a workaround.
- Does not retry the action that failed — that decision boundary (transient vs. non-transient, retry count) already lived and was already exhausted inside [04](./04-followup-agent.md)/[05](./05-reminder-agent.md) before this agent was ever invoked.
- Does not auto-close, auto-dismiss, or expire an escalation on its own. It stays flagged until a human resolves it.
- Does not call the rule engine, an LLM for "reasoning" about the failure, or any action-taking tool.

## What happens when something goes wrong here
This is the one agent for which "route the failure to escalation" is not an option — there is nothing beneath it. Two failure modes need distinct answers, both left open for the build phase but explicitly flagged now rather than silently assumed away:
- **The escalation itself fails to persist** (e.g., can't write the flag record): this must be the most reliable write path in the whole system, since it's the backstop for every other agent's failures. Whatever runtime is chosen, this agent's persistence needs the strongest delivery guarantee available (at minimum: durable logging/alerting as a fallback if the primary flag-store write fails), so an escalation is never lost the way an ordinary agent failure might be tolerated to be lost.
- **A claim ends up with no visible escalation despite a failure occurring** (e.g., the escalation was created but never surfaced anywhere a human looks): this is a monitoring/observability concern for the build phase — worth naming now as a requirement ("every escalation must be visibly surfaced, not just recorded"), not something this planning document can fully close out without knowing the runtime.

## Evidence & audit
An escalation is only useful if the human reading it doesn't have to go re-derive context. It must carry the full chain of prior agent outputs it was given, not just the immediate failure — that's the difference between "something broke, good luck" and an actually actionable flag.
