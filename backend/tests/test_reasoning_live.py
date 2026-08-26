"""ONE real call to the actual Claude API — not mocked.

Deliberately kept out of test_reasoning.py: everything in that file runs
without network access or credentials; this file requires a real
ANTHROPIC_API_KEY and spends real tokens, so it's opt-in, not part of the
default test run. Run explicitly:

    .venv/Scripts/python.exe -m pytest tests/test_reasoning_live.py -v -s

(-s so the printed explanation isn't captured/hidden by pytest.)

Uses CL-10002's real output from 01-analyzer-agent (same seeded claim
test_analyzer.py's integration test already verifies: missing_authorization,
missing_documentation, code_mismatch, overdue_follow_up — risk_score 100,
risk_level High) and runs it through the real 02-reasoning-agent, so what
gets printed is what the model actually says about a real analyzed claim,
not a synthetic example.
"""

import os
from datetime import datetime, timezone

import pytest

from app.agents.analyzer import run_analyzer
from app.agents.reasoning import ReasoningFailure, ReasoningResult, run_reasoning
from app.core.config import get_settings

_settings = get_settings()
_has_key = bool(_settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"))

pytestmark = pytest.mark.skipif(
    not _has_key,
    reason="ANTHROPIC_API_KEY not set — this test makes a real Claude API call",
)


def test_real_claude_call_explains_cl_10002():
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

        # Step 1 (already-proven path): real 01-analyzer-agent output for CL-10002.
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

        # Step 2 — the real call. No `client=` override: this hits the actual API.
        result = run_reasoning(
            analysis.claim_id,
            analysis.issues,
            analysis.risk_score,
            analysis.risk_level,
            claim_context,
        )

        print("\n" + "=" * 78)
        print(f"02-reasoning-agent live output for {analysis.claim_id}")
        print("=" * 78)

        if isinstance(result, ReasoningFailure):
            print(f"FAILURE — reason: {result.reason}\ndetail: {result.detail}")
            if result.raw_model_response:
                print(f"\nRAW MODEL RESPONSE:\n{result.raw_model_response}")
            pytest.fail(f"run_reasoning returned a failure: {result.reason} — {result.detail}")

        assert isinstance(result, ReasoningResult)

        print(f"\nSUMMARY:\n{result.summary}")
        print("\nPER-ISSUE EXPLANATIONS:")
        for issue_type, explanation in result.issue_explanations.items():
            print(f"\n  [{issue_type}]\n  {explanation}")
        print(f"\nCROSS-ISSUE NOTES:\n{result.cross_issue_notes or '(none)'}")
        print(f"\nUNCERTAINTY NOTES:\n{result.uncertainty_notes or '(none)'}")
        print("\n" + "=" * 78)

        # Grounding, not just "the call succeeded": every issue Analyzer found
        # is explained, and nothing beyond that set is.
        given_issue_types = {i.issue_type for i in analysis.issues}
        assert set(result.issue_explanations.keys()) == given_issue_types
        assert result.summary.strip() != ""
    finally:
        db.close()
