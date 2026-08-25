from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app import models

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard_metrics(clinic_id: int | None = None, db: Session = Depends(get_db)):
    # For now assume clinic_id 1 if not provided
    if clinic_id is None:
        clinic_id = 1

    total = db.query(func.count(models.Claim.id)).filter(models.Claim.clinic_id == clinic_id).scalar() or 0
    at_risk = db.query(func.count(models.Claim.id)).filter(models.Claim.clinic_id == clinic_id, models.Claim.risk_level == "High").scalar() or 0
    denied = db.query(func.count(models.Claim.id)).filter(models.Claim.clinic_id == clinic_id, models.Claim.status == "Denied").scalar() or 0
    needs_review = db.query(func.count(models.Claim.id)).filter(models.Claim.clinic_id == clinic_id, models.Claim.status == "Needs Review").scalar() or 0

    top_attention = (
        db.query(models.Claim)
        .filter(models.Claim.clinic_id == clinic_id)
        .order_by(models.Claim.risk_score.desc())
        .limit(10)
        .all()
    )

    # Surface each claim's primary (highest-severity) issue from claim_issues —
    # this is the same deterministic rule-engine output ClaimDetail already renders,
    # just picked down to one representative issue per row for the summary table.
    severity_rank = {"high": 3, "medium": 2, "low": 1}
    claim_ids = [c.id for c in top_attention]
    issues_by_claim: dict[int, list[models.ClaimIssue]] = {}
    if claim_ids:
        for issue in db.query(models.ClaimIssue).filter(models.ClaimIssue.claim_id.in_(claim_ids)).all():
            issues_by_claim.setdefault(issue.claim_id, []).append(issue)

    def primary_issue_for(claim_pk: int) -> models.ClaimIssue | None:
        issues = issues_by_claim.get(claim_pk)
        if not issues:
            return None
        return max(issues, key=lambda i: (severity_rank.get(i.severity, 0), i.created_at))

    rows = []
    for c in top_attention:
        issue = primary_issue_for(c.id)
        rows.append({
            "claim_id": c.claim_id,
            "payer_id": c.payer_id,
            "payer_name": getattr(c.payer, "name", None),
            "patient_id": getattr(c, "patient_id", None),
            "patient_name": f"{getattr(c.patient, 'first_name', '')} {getattr(c.patient, 'last_name', '')}".strip() or None,
            "amount": float(c.amount),
            "risk_score": c.risk_score,
            "primary_issue_type": issue.issue_type if issue else None,
            "primary_issue_severity": issue.severity if issue else None,
        })

    return {
        "total_claims": total,
        "at_risk": at_risk,
        "denied": denied,
        "needs_review": needs_review,
        "claims_needing_attention": rows,
    }
