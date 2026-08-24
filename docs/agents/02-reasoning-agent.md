# 02 — Reasoning Agent

## Status
Planning document. No runtime has been chosen.

## Role
The Reasoning Agent is the first place an LLM enters the pipeline. Its only job is to take the Analyzer's deterministic findings and explain them in plain language — grounded strictly in what it was handed. It does not add facts, does not look anything up on its own, and does not decide what should happen next.

## Triggered by
Commander rule 8 (`analyzer_completed`) — see [00-commander](./00-commander.md).

## Receives
Exactly the output of [01-analyzer-agent](./01-analyzer-agent.md), plus the minimum claim context needed to talk about it sensibly — all explicitly passed in by Commander/Analyzer, not fetched by this agent:
- `claim_id`, the full `Issue` list (`issue_type`, `severity`, `description`, `evidence`), `risk_score`, `risk_level`
- Minimal claim context: payer name, claim amount, current status, claim age

This is a closed set. The Reasoning Agent has no tool access and no ability to query the database, the rule engine, or anything else — that constraint is what makes "grounded only in what it was given" enforceable rather than aspirational.

## Returns
- A plain-language explanation for each `Issue` in the list: what it means in practice, why it matters for this claim
- Cross-issue interaction notes where relevant (e.g., "missing authorization combined with missing documentation compounds denial risk, not just adds to it")
- Explicit callouts of uncertainty or missing evidence — where the deterministic data doesn't fully explain the picture, the agent says so rather than filling the gap with a plausible-sounding guess
- A short overall summary tying the above together

Every explanation must reference the specific `issue_type`/`evidence` it is explaining. An explanation that doesn't trace back to an item in the Issue list it was given is out of scope for this agent to produce.

On success, emits `reasoning_completed` to Commander.

## What it explicitly does NOT do
- Does not call the rule engine, and does not recompute or second-guess `risk_score`/`risk_level` — those are the Analyzer's and stay the Analyzer's.
- Does not invent issues that aren't in the list it received. If something looks concerning but isn't reflected in an `Issue`, it may note that as a limitation of the current analysis, but it may not present it as a finding.
- Does not produce a recommendation or next steps — that's [03-recommendation-agent](./03-recommendation-agent.md).
- Does not fetch additional claim history, documents, or context beyond what was explicitly passed in.

## What happens when something goes wrong
- If the `Issue` list it receives is empty, it returns "no issues to explain" plainly — it does not manufacture concerns to have something to say.
- If the input is malformed or internally inconsistent (e.g., an `Issue` referencing a field with no evidence attached), it does not attempt to paper over the gap with inference. It returns a structured failure (`reasoning_failed`) to Commander.
- Commander routes any `reasoning_failed` to [06-escalation-agent](./06-escalation-agent.md) (rule 9) — a human sees the raw Analyzer output directly rather than waiting on an explanation that can't be produced safely.

## Evidence & audit
Each explanation must be traceable to the specific issue/evidence field that grounds it, so a reviewer can check the explanation against the underlying deterministic data without needing to trust the model's judgment on faith.
