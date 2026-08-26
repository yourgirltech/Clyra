"""01-analyzer-agent — thin, faithful wrapper around the Phase 3 deterministic
rule engine (docs/agents/01-analyzer-agent.md).

No LLM, no reasoning, no judgment of its own: it runs the existing
`app.services.risk_rules.evaluate_claim_rules` / `score_and_level_from_issues`
and reports back exactly what the engine found. It does not fetch anything
itself — if a required field wasn't given, that's the caller's problem, not
something to guess-fill — and it does not persist anything; wiring this
result into `claim_issues` / the claim's own risk fields is a separate
concern from this build step.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from app.services.risk_rules import Issue, evaluate_claim_rules, score_and_level_from_issues

# Identifies which version of the rule engine produced a given AnalyzerResult,
# so results stay reproducible/auditable even if the rule engine changes later.
RULESET_VERSION = "phase3-v1"


@dataclass(frozen=True)
class AnalyzerResult:
    claim_id: str
    issues: List[Issue]
    risk_score: int
    risk_level: str
    ruleset_version: str
    run_at: datetime


def run_analyzer(
    claim_id: str,
    claim_evidence: dict,
    payer_config: dict,
    follow_ups: list[dict],
) -> AnalyzerResult:
    """Run the deterministic rule engine for one claim and package the result.

    `claim_evidence` matches the fields the rule engine reads off the Claim
    model (authorization_present, documentation_present, coding_matches,
    last_followup_at). `payer_config` matches the Payer model fields
    (authorization_required, documentation_required, follow_up_threshold_days).
    `follow_ups` is the claim's FollowUp history — only its length matters to
    the rule engine's overdue-severity logic.
    """
    issues = evaluate_claim_rules(claim_evidence, payer_config, follow_ups)
    risk_score, risk_level = score_and_level_from_issues(issues)
    return AnalyzerResult(
        claim_id=claim_id,
        issues=issues,
        risk_score=risk_score,
        risk_level=risk_level,
        ruleset_version=RULESET_VERSION,
        run_at=datetime.now(timezone.utc),
    )
