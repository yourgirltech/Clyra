"""ONE real call to the actual Claude API for 03-recommendation-agent — not
mocked. (Two real calls total, actually: this agent's input is 02-reasoning-
agent's output, and a mocked reasoning input wouldn't be "CL-10002's actual
reasoning output" as asked — so this test runs the real reasoning call too,
then feeds its real result into the real recommendation call.)

Deliberately kept out of test_recommendation.py: everything in that file runs
without network access or credentials; this file requires a real
ANTHROPIC_API_KEY and spends real tokens, so it's opt-in, not part of the
default test run. Run explicitly:

    .venv/Scripts/python.exe -m pytest tests/test_recommendation_live.py -v -s

(-s so the printed recommendation isn't captured/hidden by pytest.)
"""

import os
from datetime import datetime, timezone

import pytest

from app.agents.analyzer import run_analyzer
from app.agents.reasoning import ReasoningFailure, ReasoningResult, run_reasoning
from app.agents.recommendation import RecommendationFailure, RecommendationResult, run_recommendation
from app.core.config import get_settings

_settings = get_settings()
_has_key = bool(_settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"))

pytestmark = pytest.mark.skipif(
    not _has_key,
    reason="ANTHROPIC_API_KEY not set — this test makes real Claude API calls",
)


def test_real_claude_recommendation_for_cl_10002():
    from app import models
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        claim = db.query(models.Claim).filter(models.Claim.claim_id == "CL-10002").first()
        assert claim is not None, "CL-10002 must exist in the seeded demo database for this test"

        payer = claim.payer
        follow_ups = db.query(models.FollowUp).filter(models.FollowUp.claim_id == claim.id).all()

        claim_evidence = {
            "authorization_present": int(claim.authorization_present),
            "documentation_present": int(claim.documentation_present),
            "coding_matches": int(claim.coding_matches),
            "last_followup_at": claim.last_followup_at,
        }
        payer_config = {
            "authorization_required": int(payer.authorization_required),
            "documentation_required": int(payer.documentation_required),
            "follow_up_threshold_days": int(payer.follow_up_threshold_days),
        }
        follow_up_dicts = [{"due_at": f.due_at} for f in follow_ups]

        # Step 1 (deterministic, free): real 01-analyzer-agent output for CL-10002.
        analysis = run_analyzer(claim.claim_id, claim_evidence, payer_config, follow_up_dicts)
        assert analysis.risk_score == 100
        assert analysis.risk_level == "High"

        claim_age_days = (datetime.now(timezone.utc) - claim.created_at.replace(tzinfo=timezone.utc)).days
        claim_context = {
            "payer": payer.name,
            "amount": float(claim.amount),
            "status": claim.status,
            "claim_age_days": claim_age_days,
        }

        # Step 2 (real call #1): 02-reasoning-agent's actual explanation.
        reasoning = run_reasoning(
            analysis.claim_id, analysis.issues, analysis.risk_score, analysis.risk_level, claim_context
        )
        if isinstance(reasoning, ReasoningFailure):
            pytest.fail(f"run_reasoning returned a failure: {reasoning.reason} — {reasoning.detail}")
        assert isinstance(reasoning, ReasoningResult)

        # Step 3 (real call #2) — the one under test. No `client=` override.
        result = run_recommendation(
            analysis.claim_id,
            analysis.issues,
            analysis.risk_score,
            analysis.risk_level,
            reasoning.issue_explanations,
            reasoning.cross_issue_notes,
            reasoning.uncertainty_notes,
            reasoning.summary,
        )

        print("\n" + "=" * 78)
        print(f"03-recommendation-agent live output for {analysis.claim_id}")
        print("=" * 78)

        if isinstance(result, RecommendationFailure):
            print(f"FAILURE — reason: {result.reason}\ndetail: {result.detail}")
            pytest.fail(f"run_recommendation returned a failure: {result.reason} — {result.detail}")

        assert isinstance(result, RecommendationResult)

        print(f"\nACTION TYPE: {result.action_type}")
        print(f"CONFIDENCE: {result.confidence}  (low_confidence={result.low_confidence})")
        print(f"CITED ISSUES: {result.cited_issue_types}")
        print(f"\nRATIONALE:\n{result.rationale}")
        if result.secondary_options:
            print("\nSECONDARY OPTIONS:")
            for opt in result.secondary_options:
                print(f"  - {opt['action_type']} ({opt['confidence']}): {opt['rationale']}")
        else:
            print("\nSECONDARY OPTIONS: (none)")
        print("\n" + "=" * 78)

        # Grounding, not just "the call succeeded."
        assert result.action_type in (
            "follow_up", "payer_reminder", "manual_review_needed", "no_action_needed"
        )
        assert result.confidence in ("High", "Medium", "Low")
        given_issue_types = {i.issue_type for i in analysis.issues}
        assert set(result.cited_issue_types).issubset(given_issue_types)
        assert result.rationale.strip() != ""
    finally:
        db.close()
