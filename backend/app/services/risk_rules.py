from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class Issue:
    issue_type: str
    severity: str  # 'low' | 'medium' | 'high'
    description: str
    evidence: dict


# severity weights used to compute risk score
SEVERITY_WEIGHTS = {
    'low': 10,
    'medium': 30,
    'high': 50,
}


def evaluate_claim_rules(claim_dict: dict, payer_cfg: dict, follow_ups: List[dict]) -> List[Issue]:
    issues: List[Issue] = []

    # missing authorization
    if payer_cfg.get('authorization_required') and not claim_dict.get('authorization_present'):
        issues.append(Issue(
            issue_type='missing_authorization',
            severity='high',
            description='Authorization required by payer but missing on claim.',
            evidence={'authorization_present': claim_dict.get('authorization_present')}
        ))

    # missing documentation
    if payer_cfg.get('documentation_required') and not claim_dict.get('documentation_present'):
        issues.append(Issue(
            issue_type='missing_documentation',
            severity='medium',
            description='Required documentation not found for this claim.',
            evidence={'documentation_present': claim_dict.get('documentation_present')}
        ))

    # code mismatch
    if not claim_dict.get('coding_matches'):
        issues.append(Issue(
            issue_type='code_mismatch',
            severity='medium',
            description='Claim coding does not match expected payer coding rules.',
            evidence={'coding_matches': claim_dict.get('coding_matches')}
        ))

    # overdue follow up
    threshold_days = payer_cfg.get('follow_up_threshold_days', 30)
    last_followup = claim_dict.get('last_followup_at')
    now = datetime.utcnow()
    overdue = False
    # treat non-positive threshold as 'no follow-up requirement'
    if threshold_days and threshold_days > 0:
        if last_followup:
            overdue = (now - last_followup).days > threshold_days
        else:
            overdue = True

    if overdue:
        issues.append(Issue(
            issue_type='overdue_follow_up',
            severity='low' if len(follow_ups) else 'medium',
            description=f'Follow-up overdue by payer policy ({threshold_days} days).',
            evidence={'last_followup_at': str(last_followup), 'follow_up_count': len(follow_ups)}
        ))

    return issues


def score_and_level_from_issues(issues: List[Issue]) -> tuple[int, str]:
    score = 0
    for it in issues:
        score += SEVERITY_WEIGHTS.get(it.severity, 0)
    score = min(100, score)
    if score >= 70:
        level = 'High'
    elif score >= 40:
        level = 'Medium'
    else:
        level = 'Low'
    return score, level
