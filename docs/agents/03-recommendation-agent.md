# 03 — Recommendation Agent

## Status
Planning document. No runtime has been chosen.

## Role
The Recommendation Agent turns the Reasoning Agent's explanation into a concrete, actionable recommendation with a stated confidence level. It is the last stop before a human is asked to approve or decline something — it proposes, it never executes.

## Triggered by
Commander rule 10 (`reasoning_completed`) — see [00-commander](./00-commander.md).

## Receives
- `claim_id`, the Reasoning Agent's explanation output (per-issue explanations, cross-issue notes, uncertainty callouts)
- The underlying `Issue` list, `risk_score`, `risk_level` (passed through for traceability, not recomputed here either)

## Returns
- One primary recommended action, and optionally secondary options, each as: `action_type` (`follow_up` | `payer_reminder` | `manual_review_needed` | `no_action_needed`), a rationale that references the specific issues/explanation driving it, and a per-option confidence
- An overall `confidence` for the primary recommendation, expressed as a band: **High / Medium / Low** (an exact numeric cutoff between these bands is a tuning decision left for the runtime-build phase, not fixed here)
- `low_confidence: true/false` — a simple flag Commander's rule table keys off directly (see rules 12/13 in [00-commander](./00-commander.md))

On success, emits `recommendation_completed` (carrying the confidence band) to Commander.

## Confidence and what happens when it isn't confident
This agent is explicitly allowed to say "I'm not sure." A Low-confidence recommendation is **never** presented to a human as a one-click approve/decline card — that would dress up a guess as a vetted suggestion. Instead:
- High/Medium confidence → Commander (rule 12) surfaces it to the human as `awaiting_human_approval`, exactly the normal path.
- Low confidence → Commander (rule 13) routes straight to [06-escalation-agent](./06-escalation-agent.md) instead. The human still sees everything (issues, explanation, the agent's attempted recommendation and *why* it wasn't confident), but framed as "this needs a human to figure out from scratch," not "approve this."

The agent does not have a way to force a low-confidence output into the approval path — that gate lives in Commander, not in this agent's own judgment, precisely so it can't be argued around by a persuasive-sounding but shaky recommendation.

## What it explicitly does NOT do
- Does not execute anything — no follow-up is created, no reminder is sent, no claim status changes as a result of this agent running.
- Does not contact a payer, patient, or provider directly or indirectly.
- Does not bypass human approval at any confidence level, including High. Confidence affects *how* something is routed for human review, never *whether* it needs human review.
- Does not invent an action type outside the fixed set above. If none of `follow_up` / `payer_reminder` / `manual_review_needed` fit, it uses `no_action_needed` with rationale rather than stretching a category to fit.

## What happens when something goes wrong
- If it cannot produce any recommendation at all (e.g., the Reasoning Agent's output is too thin or contradictory to act on), that is itself a Low-confidence outcome — it does not fail silently, it reports `low_confidence: true` with "insufficient basis for a recommendation" as the rationale, and lets Commander's rule 13 route it to escalation.
- A true internal error (malformed input, exception) is reported as `recommendation_failed` to Commander, which routes to [06-escalation-agent](./06-escalation-agent.md) (rule 11).

## Evidence & audit
Every recommended `action_type` must cite the specific issue(s)/explanation driving it. A reviewer approving or declining should be able to see exactly which deterministic finding and which piece of reasoning led to this suggestion, not just a bare action label.
