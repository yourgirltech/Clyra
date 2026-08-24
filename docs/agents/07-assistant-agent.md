# 07 — Assistant Agent

## Status
Planning document. No runtime has been chosen.

## Role
The Assistant Agent is the conversational, tool-calling agent behind the AI Assistant chat page (`frontend/src/pages/AIAssistant.tsx`). Unlike agents 01–06, it isn't driven by Commander's claim-lifecycle rule table (see the closing note in [00-commander](./00-commander.md) for why) — it's invoked directly by the chat UI whenever a user sends a message. It answers ad-hoc operator questions on demand, under the same guardrail as every other agent: it can look things up and explain, it can never execute an action.

## Triggered by
A user sending a message in the AI Assistant chat UI. Not part of Commander's ordered rule table.

## Receives
- The user's free-text question
- The conversation history for that chat session
- On-demand, read-only tool access to:
  - Claim lookup by `claim_id` (including terminal claims — read-only lookup is fine even where Commander would block further automation)
  - The deterministic rule engine, to run/read `Issue`s and risk score/level for a claim on request
  - Dashboard/aggregate metrics (e.g., claim counts by status/risk level)

It does **not** have standing access to everything in the database — only the specific tool calls above, each of which returns a bounded, specific result.

## Returns
A natural-language answer, grounded in the actual output of whatever tool calls it made to answer the question — not in the model's general knowledge of healthcare claims. Where an answer depends on a specific claim or metric, the response should make clear which claim/tool result it's citing, so the operator reading it can tell the difference between "the system found this" and "the model inferred this."

## What it can answer
- Questions about a specific claim: current status, risk score/level, what issues the rule engine found on it, its follow-up/activity history — including claims in a terminal status, read-only
- Aggregate/dashboard questions: e.g. "how many claims are At Risk right now," "which payer has the most Needs Review claims"
- Explanatory questions about how the rule engine treats a given situation (e.g. "why would a claim be flagged for missing documentation") — grounded in the actual rule logic, not a generic answer

## What it explicitly does NOT do
- Does not execute any follow-up, reminder, or approval action itself, ever — regardless of how the question is phrased ("go ahead and send the reminder now" gets a "here's how you'd approve that" answer, not an executed reminder). This is the same no-autonomous-action guardrail as every routed agent, applied to a conversational surface where it's more tempting to blur.
- Does not invent claim data it hasn't actually looked up via a tool call. If it hasn't called claim lookup for a given `claim_id`, it doesn't answer as if it had.
- Does not access claims/data outside the asking user's clinic/tenant scope.
- Does not silently escalate a question to [06-escalation-agent](./06-escalation-agent.md) — escalation is for claim-lifecycle automation failures, not for "I don't know." Those are handled directly in the chat response instead.

## What it does when it can't answer
- If the question requires information outside its tool access, it says plainly what it doesn't have rather than guessing at an answer that sounds plausible.
- If the question implies an action ("send this," "approve that," "mark this paid"), it explains that it can't take that action and points the user to the actual human-approval flow (e.g., the claim detail page) where they can do it themselves.
- If a tool call it depends on errors out, it reports that plainly to the user in the response ("I wasn't able to look up that claim's issues right now") rather than filling the gap with an unfounded answer.

## Evidence & audit
Every factual claim in a response should be traceable to a specific tool call result from that session. This doesn't need a separate audit record the way 04/05's executed actions do (nothing changed in the system), but the chat transcript itself — question, tool calls made, answer given — is the audit trail, and should be sufficient on its own to check whether an answer was actually grounded.
