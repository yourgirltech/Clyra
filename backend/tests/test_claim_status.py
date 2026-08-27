"""Pure-logic tests for the claim status <-> computed risk coherence rules.
No database — see docs/architecture.md, "Claim status and computed risk"."""
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services import claim_status as cs
from app.services.claim_status import ReconcileResult


def _claim(age_days=5):
    return SimpleNamespace(created_at=datetime.utcnow() - timedelta(days=age_days))


def test_high_risk_is_always_at_risk():
    assert cs.derive_active_status(_claim(), has_issues=True, risk_level="High") == "At Risk"


def test_any_open_issue_is_at_least_needs_review():
    assert cs.derive_active_status(_claim(), has_issues=True, risk_level="Low") == "Needs Review"
    assert cs.derive_active_status(_claim(), has_issues=True, risk_level="Medium") == "Needs Review"


def test_medium_risk_is_needs_review_even_without_issue_rows():
    assert cs.derive_active_status(_claim(), has_issues=False, risk_level="Medium") == "Needs Review"


def test_clean_low_risk_never_gets_an_internal_judgment_status():
    for age, expected in [(2, "Draft"), (20, "Submitted"), (90, "Processing")]:
        status = cs.derive_active_status(_claim(age), has_issues=False, risk_level="Low")
        assert status == expected
        assert status not in cs.INTERNAL_JUDGMENT_STATUSES


def _result(**kw):
    base = dict(
        claim_id="CL-1", status_before="Draft", status_after="Draft",
        risk_level="Low", risk_score=0, issue_count=0,
        repaired=False, documented_divergence=None, commander_decision="01-analyzer-agent",
    )
    base.update(kw)
    return ReconcileResult(**base)


def test_check_invariants_flags_at_risk_without_high():
    v = cs.check_invariants([_result(status_after="At Risk", risk_level="Medium", issue_count=2)])
    assert len(v) == 1 and "At Risk" in v[0]


def test_check_invariants_flags_needs_review_without_issues():
    v = cs.check_invariants([_result(status_after="Needs Review", risk_level="Low", issue_count=0)])
    assert len(v) == 1 and "Needs Review" in v[0]


def test_check_invariants_flags_active_status_with_issues():
    v = cs.check_invariants([_result(status_after="Processing", issue_count=1)])
    assert len(v) == 1 and "Processing" in v[0]


def test_check_invariants_flags_paid_with_issues():
    v = cs.check_invariants([_result(status_after="Paid", issue_count=1)])
    assert len(v) == 1 and "Paid" in v[0]


def test_check_invariants_allows_denied_divergence():
    # Denied with no internal risk, and Denied with open issues, are both fine.
    assert cs.check_invariants([_result(status_after="Denied", risk_level="Low", issue_count=0)]) == []
    assert cs.check_invariants([_result(status_after="Denied", risk_level="High", issue_count=3)]) == []


def test_check_invariants_clean_coherent_dataset():
    assert cs.check_invariants([
        _result(claim_id="CL-1", status_after="At Risk", risk_level="High", issue_count=2),
        _result(claim_id="CL-2", status_after="Needs Review", risk_level="Low", issue_count=1),
        _result(claim_id="CL-3", status_after="Processing", risk_level="Low", issue_count=0),
        _result(claim_id="CL-4", status_after="Paid", risk_level="Low", issue_count=0),
        _result(claim_id="CL-5", status_after="Denied", risk_level="Low", issue_count=0),
    ]) == []
