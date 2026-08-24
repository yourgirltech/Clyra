# 05 — Reminder Agent

## Status
Planning document. No runtime has been chosen.

## Role
The Reminder Agent carries out a payer-reminder action that a human has already approved — e.g., generating and logging a reminder/inquiry directed at the payer about a claim's status. Same shape as [04-followup-agent](./04-followup-agent.md): it executes an already-decided, already-approved action mechanically, it does not decide whether or what to remind, and it does not exercise any judgment about the claim itself.

## Triggered by
Commander rule 15 (`human_approved` where `recommendation.action_type == payer_reminder`) — see [00-commander](./00-commander.md).

## Receives
- `claim_id`
- The approved recommendation record: `action_type`, approver identity, approval timestamp, and the fully-specified reminder content/parameters (who/what system the reminder targets, the message content, any reference numbers) fixed at approval time — this agent does not draft or edit that content
- No open-ended instruction, same constraint as the Follow-up Agent: an under-specified approved action is a failure condition, not something to guess-fill.

## Returns
On success:
- A record of the reminder sent (payer/target, content, timestamp) and an `ActivityLog` entry tying it to the specific approval that authorized it
- Emits `reminder_completed` to Commander (routes to rule 18 — no further action, claim returns to steady state)

On failure: see below.

## What it explicitly does NOT do
- Does not decide whether a reminder is warranted or what it should say — already decided upstream.
- Does not touch claim status directly.
- Does not send more than the one approved reminder per approval, and does not silently mark a reminder sent that wasn't actually delivered/logged.

## What happens when its first attempt fails
Identical fallback structure to [04-followup-agent](./04-followup-agent.md), applied to payer-reminder delivery instead of follow-up creation:

1. **Transient** (payer-facing system/channel temporarily unavailable, timeout): bounded automatic retry (e.g., up to 2 attempts) with backoff. A successful retry logs the retry in the `ActivityLog` entry but does not require a fresh approval.
2. **Non-transient** (missing required content, approval revoked before execution, invalid target): no retry — it fails immediately rather than repeating a broken attempt.

Once retries are exhausted or a non-transient failure occurs, the agent emits `reminder_failed` with the specific reason and stops. It does not substitute a different channel or action on its own. Commander routes `reminder_failed` straight to [06-escalation-agent](./06-escalation-agent.md) (rule 17), so a human sees exactly what was approved, what was attempted, and why it didn't go through.

## Evidence & audit
Every attempt (success, retry, or failure) is logged to `ActivityLog`, tied to the approving human and timestamp — reminders are payer-facing communication, so the audit trail needs to make it unambiguous exactly what was sent, when, and under whose authorization.
