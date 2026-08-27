from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.services.risk_rules import evaluate_claim_rules, score_and_level_from_issues, Issue
from app import models


def analyze_and_persist(db: Session, claim: models.Claim) -> List[Issue]:
    # build claim_dict
    claim_dict = {
        'authorization_present': int(getattr(claim, 'authorization_present', 0)),
        'documentation_present': int(getattr(claim, 'documentation_present', 0)),
        'coding_matches': int(getattr(claim, 'coding_matches', 1)),
        'last_followup_at': getattr(claim, 'last_followup_at', None),
        'created_at': claim.created_at,
    }

    payer = claim.payer
    payer_cfg = {
        'authorization_required': int(getattr(payer, 'authorization_required', 0)),
        'documentation_required': int(getattr(payer, 'documentation_required', 0)),
        'follow_up_threshold_days': int(getattr(payer, 'follow_up_threshold_days', 30)),
    }

    # get follow ups
    fups = db.query(models.FollowUp).filter(models.FollowUp.claim_id == claim.id).all()
    follow_ups = [{'due_at': f.due_at} for f in fups]

    issues = evaluate_claim_rules(claim_dict, payer_cfg, follow_ups)

    # persist: remove old issues and add new
    db.query(models.ClaimIssue).filter(models.ClaimIssue.claim_id == claim.id).delete()
    for it in issues:
        ci = models.ClaimIssue(
            claim_id=claim.id,
            issue_type=it.issue_type,
            severity=it.severity,
            description=it.description,
            evidence=str(it.evidence),
        )
        db.add(ci)

    # update claim risk
    score, level = score_and_level_from_issues(issues)
    claim.risk_score = score
    claim.risk_level = level
    db.add(claim)
    db.commit()
    return issues


def analyze_all_claims(db: Session) -> int:
    claims = db.query(models.Claim).all()
    count = 0
    for c in claims:
        analyze_and_persist(db, c)
        count += 1
    return count
