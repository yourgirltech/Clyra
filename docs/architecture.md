# Architecture

## Overview
Clyra uses a React frontend, a Python FastAPI backend, and PostgreSQL for persistence. A future n8n automation layer will connect human-approved actions to downstream workflows.

## Principles
- Deterministic rule evaluation is the source of truth for risk scoring; AI review reasons about and explains that output.
- AI analysis supports recommendations, not autonomous actions.
- All development occurs on synthetic data only.

## Risk Scoring

Risk scoring is deterministic and computed from rule `issues` produced by the `risk_rules` module.

As of Phase 4, this rule engine (`risk_rules.evaluate_claim_rules` / `score_and_level_from_issues`) is called directly by the 01-analyzer-agent in the Commander-orchestrated agent system, rather than run as a preprocessing step the API runs before returning a response. See [`docs/ai-design.md`](./ai-design.md) for the Commander pattern and the numbered specialist agents. The scoring logic itself, and its weights/thresholds, are unchanged: this is a change in how the engine is invoked, not a change in what it computes.

- Severity weights:
	- `low`: 10 points
	- `medium`: 30 points
	- `high`: 50 points

- Score computation: the numeric `risk_score` is the sum of weights for all detected issues, capped at 100.

- Risk level mapping:
	- `High` : `risk_score` >= 70
	- `Medium` : 40 <= `risk_score` < 70
	- `Low` : `risk_score` < 40

This formula is implemented in `backend/app/services/risk_rules.py` in the `score_and_level_from_issues` function.
