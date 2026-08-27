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

## Claim status and computed risk

A claim's `status` and its computed `risk_score` / `risk_level` / `claim_issues`
come from two different kinds of source, and the rules about when they may
disagree follow from that.

### Internal-judgment statuses — must always match a fresh analysis

**`At Risk`** and **`Needs Review`** are *our own system's output*. They are
produced by the deterministic rule engine / 01-analyzer-agent, nothing else.
There is no legitimate reason for them to disagree with a fresh analysis, so
the seed enforces these invariants (`app/services/claim_status.py`,
`check_invariants`):

| Status | Invariant |
| --- | --- |
| `At Risk` | `risk_level == "High"` (computed `risk_score` ≥ 70) |
| `Needs Review` | at least one open row in `claim_issues` |
| `Draft` / `Submitted` / `Processing` | **zero** open issues — a clean, low-risk claim |

`derive_active_status()` is the single function that assigns these: High →
`At Risk`; any open issue (or Medium risk) → `Needs Review`; genuinely clean and
low-risk → an active pipeline status picked by claim age. A `Needs Review` claim
may still show `risk_level: Low` (e.g. one medium-severity issue = 30 points):
that is coherent — an open issue always warrants a look, and the numeric score
is shown separately.

### Terminal statuses — may diverge, and that divergence is documented

**`Denied`** records an outcome decided *outside* our four rule checks — payer
policy, external medical review, eligibility, timely-filing, etc. A claim can be
denied for a reason Clyra never measured, so **`Denied` is allowed to diverge
from the internal risk score**, including `Denied` with `risk_score == 0` and no
issues. The reconcile step never overwrites a `Denied` status; it records the
divergence type (`denied_no_internal_risk` / `denied_with_open_issues`) so the
audit report shows it is intentional, not an accident.

**`Paid`** is held to the stricter bar in our synthetic dataset: a paid claim is
expected to be internally coherent, so **`Paid` must have zero open issues**. A
`Paid` row that a fresh analysis finds issues on is treated as incoherent and
repaired to the appropriate active status.

### How this is kept true

`backend/scripts/seed_claims.py` runs in two phases: (1) create claims with
realistic evidence fields only, then (2) **reconcile every claim in the database**
through the real analyzer + Commander (`claim_status.reconcile_all_claims`) —
persisting its issues/risk from the actual rule engine and then setting a
coherent status. Phase 2 runs on every invocation and is a pure function of each
claim's evidence, so re-running the seed against an existing (e.g. production)
database repairs any incoherent rows in place. The seed exits non-zero if any
invariant above is still violated afterward.

`backend/scripts/risk_distribution.py` is a read-only report of the current
distribution and any violations — safe to run against production without
changing anything.
