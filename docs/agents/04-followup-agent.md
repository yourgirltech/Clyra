# 04 — Follow-up Agent

## Status
Implemented. `backend/app/agents/followup.py` (`run_followup`) is a plain Python function, same pattern as 01/02/03/06/07 — no n8n, no real external delivery. This is a synthetic-data demo: "executing" a follow-up means simulating the action and creating a real, durable `FollowUp` + `ActivityLog` record, not actually contacting anyone. Wired into Commander's dispatch (`app.agents.dispatch.route_and_dispatch`) at rule 14, and into the approval flow (`app.services.pipeline.decide_recommendation`), which fixes the follow-up's content (note text, due date) at approval time from the recommendation's own rationale and the claim's payer config — this agent never drafts that content itself. Covered by `backend/tests/test_followup.py` (success, transient retry-then-success, transient-exhausted, missing-fields, revoked-approval) and the full-chain tests in `backend/tests/test_human_review.py`.

## Role
The Follow-up Agent carries out a follow-up action that a human has already approved. It does not decide *whether* to follow up, and it does not decide *what* the follow-up says — those decisions were made by [03-recommendation-agent](./03-recommendation-agent.md) and then approved by a human. This agent's job is narrow and mechanical: execute exactly the approved action, record that it happened, and report success or failure honestly.

## Triggered by
Commander rule 14 (`human_approved` where `recommendation.action_type == follow_up`) — see [00-commander](./00-commander.md).

## Receives
- `claim_id`
- The approved recommendation record: `action_type`, the approver's identity, the approval timestamp, and the fully-specified content/parameters of what to do (e.g., the follow-up note text and any due date) — this content was already fixed at approval time, this agent does not draft or edit it
- No open-ended instruction. If the approved action is under-specified (missing note content, no due date where one is required), that is a failure condition, not something this agent fills in with a reasonable-sounding default.

## Returns
On success:
- A `FollowUp` record (matching the existing `FollowUp` model: `claim_id`, `note`, `due_at`) and an `ActivityLog` entry recording what was done, by which approval, and when
- Emits `followup_completed` to Commander (routes to rule 19 — no further action, claim returns to steady state)

On failure: see below — it never reports success unless the follow-up record was actually durably created.

## What it explicitly does NOT do
- Does not decide whether a follow-up is warranted — that's already decided by the time this agent runs.
- Does not compose or alter the follow-up's content beyond what was approved.
- Does not touch claim status directly (status changes, if any result from this action, flow back through the normal claim-update path that would re-trigger [01-analyzer-agent](./01-analyzer-agent.md), not through this agent short-circuiting it).
- Does not retry indefinitely, and does not silently mark something done that didn't actually happen.

## What happens when its first attempt fails
Failures are split into two kinds, handled differently:

1. **Transient** (e.g., a downstream system/dependency is temporarily unavailable, a timeout): the agent retries automatically, a small bounded number of times (e.g., up to 2 retries) with backoff between attempts. If a retry succeeds, it proceeds as a normal success — the retry itself is logged in the `ActivityLog` entry for transparency, but it is not treated as a new event requiring a fresh human approval.
2. **Non-transient** (e.g., the approved action is missing required fields, the approval was revoked between routing and execution, a validation error): no retry. Retrying a broken input doesn't fix it, and doing so would just delay the human finding out.

If all permitted retries are exhausted (case 1) or a non-transient failure occurs (case 2), the agent emits `followup_failed` with the specific reason, and stops — it does not fall back to a different action type or attempt an alternative on its own initiative. Commander routes `followup_failed` straight to [06-escalation-agent](./06-escalation-agent.md) (rule 17), where a human sees exactly what was approved, what was attempted, and why it didn't go through.

## Evidence & audit
Every execution attempt (success, retry, or failure) is logged to `ActivityLog` with enough detail to answer "what did the system actually do with this human's approval" after the fact — this agent's actions are the one place in the pipeline with real-world side effects, so its audit trail has to be complete, not best-effort.
