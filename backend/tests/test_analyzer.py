"""Tests for 01-analyzer-agent (backend/app/agents/analyzer.py) and its wiring
into Commander's dispatch (backend/app/agents/dispatch.py).

Three layers, per the build-step-2 scope:
1. run_analyzer is a faithful wrapper — same issues/score/level the Phase 3
   rule engine already produces for the same inputs (mirrors
   tests/test_risk_engine.py's cases).
2. Commander's rule 6 (claim_created / claim_evidence_updated) actually
   invokes the analyzer now, in place of the "would call: 01-analyzer-agent"
   stub. (02/03/06 became real in later build steps — their own "not a stub"
   coverage lives in test_reasoning.py / test_recommendation.py /
   test_escalation.py.)
3. A real seeded claim, read from the actual demo Postgres database, produces
   the expected issues/risk_score/risk_level through this exact path — not
   just synthetic dicts.
"""

from datetime import datetime, timedelta

import pytest

from app.agents.analyzer import AnalyzerResult, run_analyzer
from app.agents.commander import AGENT_ANALYZER
from app.agents.dispatch import route_and_dispatch


def make_claim_state(status="Submitted", claim_id="CL-TEST-1"):
    return {
        "claim_id": claim_id,
        "status": status,
        "risk_score": 0,
        "risk_level": "Low",
        "latest_issues": [],
        "latest_recommendation": None,
        "agent_run_in_progress": False,
    }


def make_trigger(type_):
    return {"type": type_, "payload": {}}


# ---------------------------------------------------------------------------
# 1. run_analyzer is a thin, faithful wrapper around the Phase 3 rule engine.
# ---------------------------------------------------------------------------

def test_run_analyzer_packages_issues_score_and_level():
    claim_evidence = {
        "authorization_present": 0,
        "documentation_present": 1,
        "coding_matches": 1,
        "last_followup_at": None,
    }
    payer_config = {
        "authorization_required": 1,
        "documentation_required": 0,
        "follow_up_threshold_days": 30,
    }
    result = run_analyzer("CL-TEST-1", claim_evidence, payer_config, [])

    assert isinstance(result, AnalyzerResult)
    assert result.claim_id == "CL-TEST-1"
    assert any(i.issue_type == "missing_authorization" for i in result.issues)
    assert result.risk_score >= 40
    assert result.ruleset_version == "phase3-v1"
    assert isinstance(result.run_at, datetime)


def test_run_analyzer_no_issues_when_claim_is_clean():
    claim_evidence = {
        "authorization_present": 1,
        "documentation_present": 1,
        "coding_matches": 1,
        "last_followup_at": None,
    }
    payer_config = {
        "authorization_required": 0,
        "documentation_required": 0,
        "follow_up_threshold_days": 0,
    }
    result = run_analyzer("CL-TEST-2", claim_evidence, payer_config, [])

    assert result.issues == []
    assert result.risk_score == 0
    assert result.risk_level == "Low"


def test_run_analyzer_overdue_follow_up_matches_rule_engine():
    old = datetime.utcnow() - timedelta(days=100)
    claim_evidence = {
        "authorization_present": 1,
        "documentation_present": 1,
        "coding_matches": 1,
        "last_followup_at": old,
    }
    payer_config = {
        "authorization_required": 0,
        "documentation_required": 0,
        "follow_up_threshold_days": 30,
    }
    result = run_analyzer("CL-TEST-3", claim_evidence, payer_config, [])

    assert any(i.issue_type == "overdue_follow_up" for i in result.issues)


# ---------------------------------------------------------------------------
# 2. Commander's rule 6 actually invokes the analyzer now.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trigger_type", ["claim_created", "claim_evidence_updated"])
def test_rule06_dispatches_a_real_analyzer_run_not_a_stub(trigger_type):
    claim_evidence = {
        "authorization_present": 0,
        "documentation_present": 0,
        "coding_matches": 0,
        "last_followup_at": None,
    }
    payer_config = {
        "authorization_required": 1,
        "documentation_required": 1,
        # 0 disables the overdue-follow-up check so this test isolates exactly
        # the three issues below (last_followup_at=None would otherwise also
        # trigger overdue_follow_up).
        "follow_up_threshold_days": 0,
    }

    decision, result = route_and_dispatch(
        make_claim_state(),
        make_trigger(trigger_type),
        claim_evidence=claim_evidence,
        payer_config=payer_config,
        follow_ups=[],
    )

    assert decision.rule == 6
    assert decision.decision == AGENT_ANALYZER
    # The real thing, not the "would call: 01-analyzer-agent" placeholder string.
    assert isinstance(result, AnalyzerResult)
    assert result.risk_level == "High"
    assert {i.issue_type for i in result.issues} == {
        "missing_authorization",
        "missing_documentation",
        "code_mismatch",
    }


def test_rule06_missing_required_inputs_raises_rather_than_guessing():
    with pytest.raises(ValueError):
        route_and_dispatch(make_claim_state(), make_trigger("claim_created"))


# As of build step 5 (06-escalation-agent), every agent Commander can route
# to in Phase 4 (01, 02, 03, 06) is real — there's no longer a rule that
# leaves dispatch.py returning the stub placeholder for a reachable decision,
# so there's nothing left for a generic "is it still stubbed" test in this
# file to guard. Rule 7 (analyzer_failed -> 06-escalation-agent)'s "is it
# real" coverage lives in test_escalation.py; the only two agents still out
# of reach (04-followup-agent, 05-reminder-agent) are proven unreachable in
# test_reasoning.py's test_04_and_05_are_never_even_reachable_as_a_commander_decision.


# ---------------------------------------------------------------------------
# 3. A real seeded claim, through this exact path, produces the expected
# issues/risk_score/risk_level — not synthetic dicts.
# ---------------------------------------------------------------------------

def test_real_seeded_claim_cl_10002_through_commander_and_analyzer():
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

        claim_state = make_claim_state(status=claim.status, claim_id=claim.claim_id)
        decision, result = route_and_dispatch(
            claim_state,
            make_trigger("claim_created"),
            claim_evidence=claim_evidence,
            payer_config=payer_config,
            follow_ups=follow_up_dicts,
        )

        assert decision.decision == AGENT_ANALYZER
        assert isinstance(result, AnalyzerResult)
        assert result.claim_id == "CL-10002"

        # Known-good values for this seeded claim, previously verified via the
        # live /api/claims/CL-10002/analyze endpoint (same rule engine, same
        # data): missing authorization, missing documentation, code mismatch,
        # and an overdue follow-up all fire, capping risk_score at 100/High.
        issue_types = {i.issue_type for i in result.issues}
        assert issue_types == {
            "missing_authorization",
            "missing_documentation",
            "code_mismatch",
            "overdue_follow_up",
        }
        assert result.risk_score == 100
        assert result.risk_level == "High"

        # And it agrees with what's already persisted on the claim from the
        # Phase 3 seeding/analysis pass — this new path isn't computing
        # something different from the one the app already trusts.
        assert result.risk_score == claim.risk_score
        assert result.risk_level == claim.risk_level
    finally:
        db.close()
