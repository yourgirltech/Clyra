import json
from typing import Any
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app import models
from app.utils.sorting import parse_sort_params
from app.schemas.claims import ClaimOut, ClaimListQuery, ClaimListResponse
from app.services import risk_engine, pipeline

router = APIRouter(tags=["claims"])


def get_current_clinic(x_clinic_id: int | None = Header(None)) -> int:
    # Enforce clinic-level isolation via header `X-Clinic-Id` for now.
    if x_clinic_id is None:
        # default to clinic 1 for local dev
        return 1
    return x_clinic_id


@router.get("/claims", response_model=ClaimListResponse)
def list_claims(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=200),
    status: str | None = Query(None),
    risk_level: str | None = Query(None),
    payer_id: int | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    search: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_dir: str | None = Query(None),
    clinic_id: int = Depends(get_current_clinic),
    db: Session = Depends(get_db),
) -> list[ClaimOut]:
    base_q = db.query(models.Claim).filter(models.Claim.clinic_id == clinic_id)

    if status:
        base_q = base_q.filter(models.Claim.status == status)
    if risk_level:
        base_q = base_q.filter(models.Claim.risk_level == risk_level)
    if payer_id:
        base_q = base_q.filter(models.Claim.payer_id == payer_id)
    if start_date:
        base_q = base_q.filter(models.Claim.created_at >= start_date)
    if end_date:
        base_q = base_q.filter(models.Claim.created_at <= end_date)
    if search:
        base_q = base_q.filter(models.Claim.claim_id.ilike(f"%{search}%"))

    total = base_q.count()

    sort_list = parse_sort_params(sort_by, sort_dir)

    sort_map = {
        'created_at': models.Claim.created_at,
        'amount': models.Claim.amount,
        'status': models.Claim.status,
        'risk_score': models.Claim.risk_score,
        'claim_id': models.Claim.claim_id,
    }

    applied_any = False
    for col_name, dir_ in sort_list:
        if col_name in sort_map:
            col = sort_map[col_name]
            if dir_ == 'asc':
                base_q = base_q.order_by(col.asc())
            else:
                base_q = base_q.order_by(col.desc())
            applied_any = True

    if not applied_any:
        base_q = base_q.order_by(models.Claim.created_at.desc())

    q = base_q.offset((page - 1) * size).limit(size)
    results = []
    for c in q.all():
        results.append({
            "id": c.id,
            "claim_id": c.claim_id,
            "clinic_id": c.clinic_id,
            "payer_id": c.payer_id,
            "payer_name": getattr(c.payer, "name", None),
            "patient_id": getattr(c, "patient_id", None),
            "patient_name": f"{getattr(c.patient, 'first_name', '')} {getattr(c.patient, 'last_name', '')}".strip() or None,
            "amount": float(c.amount),
            "status": c.status,
            "risk_level": c.risk_level,
            "risk_score": c.risk_score,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        })
    return {"items": results, "total": total, "page": page, "size": size}


@router.get("/claims/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: str, clinic_id: int = Depends(get_current_clinic), db: Session = Depends(get_db)) -> Any:
    claim = db.query(models.Claim).filter(models.Claim.claim_id == claim_id, models.Claim.clinic_id == clinic_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return {
        "id": claim.id,
        "claim_id": claim.claim_id,
        "clinic_id": claim.clinic_id,
        "payer_id": claim.payer_id,
        "payer_name": getattr(claim.payer, "name", None),
        "patient_id": getattr(claim, "patient_id", None),
        "patient_name": f"{getattr(claim.patient, 'first_name', '')} {getattr(claim.patient, 'last_name', '')}".strip() or None,
        "amount": float(claim.amount),
        "status": claim.status,
        "risk_level": claim.risk_level,
        "risk_score": claim.risk_score,
        "created_at": claim.created_at,
        "updated_at": claim.updated_at,
    }




@router.get('/claims/{claim_id}/analyze')
def analyze_claim(claim_id: str, clinic_id: int = Depends(get_current_clinic), db: Session = Depends(get_db)):
    claim = db.query(models.Claim).filter(models.Claim.claim_id == claim_id, models.Claim.clinic_id == clinic_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail='Claim not found')
    issues = risk_engine.analyze_and_persist(db, claim)
    return {'issues': [issue.__dict__ if hasattr(issue, '__dict__') else issue for issue in issues], 'risk_level': claim.risk_level, 'risk_score': claim.risk_score}


def _get_claim_or_404(claim_id: str, clinic_id: int, db: Session) -> models.Claim:
    claim = db.query(models.Claim).filter(models.Claim.claim_id == claim_id, models.Claim.clinic_id == clinic_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


def _recommendation_out(rec: models.Recommendation) -> dict:
    return {
        "id": rec.id,
        "claim_id": rec.claim_id,
        "action_type": rec.action_type,
        "rationale": rec.note,
        "confidence": rec.confidence,
        "low_confidence": bool(rec.low_confidence),
        "cited_issue_types": json.loads(rec.cited_issue_types) if rec.cited_issue_types else [],
        "secondary_options": json.loads(rec.secondary_options) if rec.secondary_options else [],
        "approval_status": rec.approval_status,
        "created_at": rec.created_at,
        "decided_at": rec.decided_at,
    }


def _activity_out(log: models.ActivityLog) -> dict:
    return {
        "id": log.id,
        "action": log.action,
        "details": json.loads(log.details) if log.details else None,
        "created_at": log.created_at,
    }


def _decision_out(decision) -> dict:
    return {"decision": decision.decision, "reason_code": decision.reason_code, "rule": decision.rule}


def _execution_out(execution) -> dict | None:
    if execution is None:
        return None
    kind = type(execution).__name__  # "FollowUpResult" | "FollowUpFailure" | "ReminderResult" | "ReminderFailure"
    out = {"kind": kind, **execution.__dict__}
    if "due_at" in out and out["due_at"] is not None:
        out["due_at"] = out["due_at"].isoformat()
    return out


@router.get("/claims/{claim_id}/recommendation")
def get_latest_recommendation(claim_id: str, clinic_id: int = Depends(get_current_clinic), db: Session = Depends(get_db)):
    claim = _get_claim_or_404(claim_id, clinic_id, db)
    rec = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.claim_id == claim.id)
        .order_by(models.Recommendation.created_at.desc(), models.Recommendation.id.desc())
        .first()
    )
    return {"recommendation": _recommendation_out(rec) if rec else None}


@router.post("/claims/{claim_id}/recommendation")
def generate_recommendation(claim_id: str, clinic_id: int = Depends(get_current_clinic), db: Session = Depends(get_db)):
    claim = _get_claim_or_404(claim_id, clinic_id, db)
    outcome = pipeline.generate_recommendation(db, claim)
    return {
        "stage": outcome.stage,
        "detail": outcome.detail,
        "decision": _decision_out(outcome.decision) if outcome.decision else None,
        "recommendation": _recommendation_out(outcome.recommendation) if outcome.recommendation else None,
        "escalation_id": outcome.escalation.escalation_id if outcome.escalation else None,
    }


@router.post("/claims/{claim_id}/recommendation/{recommendation_id}/approve")
def approve_recommendation(
    claim_id: str,
    recommendation_id: int,
    clinic_id: int = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    claim = _get_claim_or_404(claim_id, clinic_id, db)
    rec = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.id == recommendation_id, models.Recommendation.claim_id == claim.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if rec.approval_status != pipeline.STATUS_PENDING:
        raise HTTPException(status_code=409, detail=f"Recommendation is not pending approval (status={rec.approval_status})")

    outcome = pipeline.decide_recommendation(db, claim, rec, approved=True)
    return {
        "recommendation": _recommendation_out(outcome.recommendation),
        "decision": _decision_out(outcome.decision),
        "execution": _execution_out(outcome.execution),
        "execution_decision": _decision_out(outcome.execution_decision) if outcome.execution_decision else None,
        "escalation_id": outcome.escalation.escalation_id if outcome.escalation else None,
        "activity": _activity_out(outcome.activity),
    }


@router.post("/claims/{claim_id}/recommendation/{recommendation_id}/decline")
def decline_recommendation(
    claim_id: str,
    recommendation_id: int,
    clinic_id: int = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    claim = _get_claim_or_404(claim_id, clinic_id, db)
    rec = (
        db.query(models.Recommendation)
        .filter(models.Recommendation.id == recommendation_id, models.Recommendation.claim_id == claim.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if rec.approval_status != pipeline.STATUS_PENDING:
        raise HTTPException(status_code=409, detail=f"Recommendation is not pending approval (status={rec.approval_status})")

    outcome = pipeline.decide_recommendation(db, claim, rec, approved=False)
    return {
        "recommendation": _recommendation_out(outcome.recommendation),
        "decision": _decision_out(outcome.decision),
        "execution": _execution_out(outcome.execution),
        "execution_decision": _decision_out(outcome.execution_decision) if outcome.execution_decision else None,
        "escalation_id": outcome.escalation.escalation_id if outcome.escalation else None,
        "activity": _activity_out(outcome.activity),
    }


@router.get("/claims/{claim_id}/activity")
def get_claim_activity(claim_id: str, clinic_id: int = Depends(get_current_clinic), db: Session = Depends(get_db)):
    claim = _get_claim_or_404(claim_id, clinic_id, db)
    logs = (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.claim_id == claim.id)
        .order_by(models.ActivityLog.created_at.desc(), models.ActivityLog.id.desc())
        .all()
    )
    return {"items": [_activity_out(log) for log in logs]}
