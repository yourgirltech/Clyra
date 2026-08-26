# 01 — Analyzer Agent

## Status
Implemented. `backend/app/agents/analyzer.py` (`run_analyzer`) wraps the existing Phase 3 rule engine (`evaluate_claim_rules` / `score_and_level_from_issues`) exactly as described below — no LLM, no persistence in this build step. Commander's rule 6 dispatches to it for real via `backend/app/agents/dispatch.py`, in place of the earlier stub. Covered by `backend/tests/test_analyzer.py`, including a real seeded claim (CL-10002) verified end to end through Commander → Analyzer. Every other agent (02-06) is still `dispatch_stub` — only 01 is wired up so far.

## Role
The Analyzer is the grounding step for everything downstream. It takes one claim, runs it through the **existing deterministic rule engine** (`backend/app/services/risk_rules.py` — `evaluate_claim_rules` / `score_and_level_from_issues`, unchanged by this roadmap), and reports back exactly what the engine found. It performs no reasoning, no explanation, and no judgment of its own — it is a thin, faithful wrapper around code that already exists and is already the system's source of truth for risk.

## Triggered by
Commander rules 6 (`claim_created` / `claim_evidence_updated`) — see [00-commander](./00-commander.md).

## Receives
- `claim_id`
- Claim evidence fields, matching the existing `Claim` model: `authorization_present`, `documentation_present`, `coding_matches`, `last_followup_at`
- Payer configuration, matching the existing `Payer` model: `authorization_required`, `documentation_required`, `follow_up_threshold_days`
- The claim's existing follow-up history (`FollowUp` rows) — the rule engine uses the count to decide severity of an overdue-follow-up issue

Nothing else. The Analyzer does not go looking for additional context — if the rule engine needs a field it wasn't given, that's a failure (see below), not a reason to fetch more data on its own initiative.

## Returns
- The canonical `Issue` list exactly as produced by `evaluate_claim_rules`: `issue_type`, `severity`, `description`, `evidence`
- `risk_score`, `risk_level` exactly as produced by `score_and_level_from_issues`
- `claim_id`, a `run_id`/timestamp, and which ruleset version ran (so results are reproducible and auditable later even if the rule engine changes)

The Analyzer's output is treated as the canonical record for this claim's issues and risk score — it persists the `Issue` list to `claim_issues` and updates the claim's `risk_score`/`risk_level` fields, the same fields that already exist on the `Claim` model today. This is what "deterministic rule evaluation is the source of truth" (`docs/architecture.md`) means in practice: nothing downstream is allowed to recompute or override these values, only explain them.

On success, it emits `analyzer_completed` back to Commander with a pointer to this run's output.

## What it explicitly does NOT do
- Does not explain *why* an issue matters, what it means for the claim, or how issues interact — that is [02-reasoning-agent](./02-reasoning-agent.md)'s job entirely.
- Does not recommend any action.
- Does not call an LLM. There is no reasoning step here — if a future version ever needs LLM assistance to *extract* evidence fields from unstructured source documents, that would be a different, earlier stage feeding evidence *into* the Analyzer, not something the Analyzer itself does.
- Does not decide claim status.
- Does not retry with modified or guessed inputs. If required evidence is missing or malformed, it fails loudly rather than substituting a default and pretending the analysis is complete.

## What happens when something goes wrong
The rule engine is deterministic code, not a model call, so "failure" here means: missing/malformed payer config, a claim evidence field that doesn't resolve, or an unhandled exception inside the rule engine itself.

- The Analyzer does not catch this and improvise. It returns a structured failure (`analyzer_failed`, with the specific missing/invalid field named) to Commander.
- Commander routes that straight to [06-escalation-agent](./06-escalation-agent.md) (rule 7) — a human sees exactly what data was missing, rather than the pipeline silently stalling or fabricating a risk score.
- No partial or guessed `risk_score`/`risk_level` is ever written. Either the full deterministic evaluation succeeds and is persisted, or nothing is persisted and the claim's last-known-good risk data is left untouched.

## Evidence & audit
Every `Issue` already carries its own `evidence` dict (this is existing rule-engine behavior, not new). The Analyzer doesn't add interpretation to it — it passes it through unchanged, so a reviewer can trace any downstream statement back to the exact evidence field that triggered it.
