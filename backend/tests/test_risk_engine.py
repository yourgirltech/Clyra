from datetime import datetime, timedelta

from app.services.risk_rules import evaluate_claim_rules, score_and_level_from_issues


def test_missing_authorization():
    claim = {'authorization_present': 0, 'documentation_present': 1, 'coding_matches': 1, 'last_followup_at': None}
    payer = {'authorization_required': 1, 'documentation_required': 0, 'follow_up_threshold_days': 30}
    issues = evaluate_claim_rules(claim, payer, [])
    assert any(i.issue_type == 'missing_authorization' for i in issues)
    score, level = score_and_level_from_issues(issues)
    assert score >= 40


def test_missing_documentation():
    claim = {'authorization_present': 1, 'documentation_present': 0, 'coding_matches': 1, 'last_followup_at': None}
    payer = {'authorization_required': 0, 'documentation_required': 1, 'follow_up_threshold_days': 30}
    issues = evaluate_claim_rules(claim, payer, [])
    assert any(i.issue_type == 'missing_documentation' for i in issues)


def test_code_mismatch():
    claim = {'authorization_present': 1, 'documentation_present': 1, 'coding_matches': 0, 'last_followup_at': None}
    payer = {'authorization_required': 0, 'documentation_required': 0, 'follow_up_threshold_days': 30}
    issues = evaluate_claim_rules(claim, payer, [])
    assert any(i.issue_type == 'code_mismatch' for i in issues)


def test_overdue_follow_up_with_last():
    old = datetime.utcnow() - timedelta(days=100)
    claim = {'authorization_present': 1, 'documentation_present': 1, 'coding_matches': 1, 'last_followup_at': old}
    payer = {'authorization_required': 0, 'documentation_required': 0, 'follow_up_threshold_days': 30}
    issues = evaluate_claim_rules(claim, payer, [])
    assert any(i.issue_type == 'overdue_follow_up' for i in issues)


def test_edge_no_rules():
    claim = {'authorization_present': 1, 'documentation_present': 1, 'coding_matches': 1, 'last_followup_at': None}
    payer = {'authorization_required': 0, 'documentation_required': 0, 'follow_up_threshold_days': 0}
    issues = evaluate_claim_rules(claim, payer, [])
    assert issues == []
