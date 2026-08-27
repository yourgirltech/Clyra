"""Tests for 04-followup-agent (backend/app/agents/followup.py).

No LLM involved — 04 never calls one, per spec. What's under test instead:
a real Postgres write for a successful execution (FollowUp + ActivityLog),
the bounded transient-retry-with-backoff path (deliberately triggered via
`simulate_transient_failures`, not left as untestable theory), and the two
non-transient failure paths (missing fields, revoked approval) that never
retry.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app import models
from app.agents.followup import FollowUpFailure, FollowUpResult, MAX_RETRIES, run_followup
from app.db.database import SessionLocal


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def claim(db):
    clinic = db.query(models.Clinic).first()
    payer = db.query(models.Payer).first()
    assert clinic is not None and payer is not None, "run backend/scripts/seed_claims.py first"

    row = models.Claim(
        claim_id="CL-TEST-FOLLOWUP",
        clinic_id=clinic.id,
        payer_id=payer.id,
        amount=50.0,
        status="Submitted",
        risk_level="Low",
        risk_score=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    yield row

    db.query(models.ActivityLog).filter(models.ActivityLog.claim_id == row.id).delete()
    db.query(models.FollowUp).filter(models.FollowUp.claim_id == row.id).delete()
    db.query(models.Claim).filter(models.Claim.id == row.id).delete()
    db.commit()


def _approved_action(**overrides):
    action = {"note": "Call payer to confirm authorization status.", "due_at": datetime.utcnow() + timedelta(days=14)}
    action.update(overrides)
    return action


def test_success_creates_real_followup_and_activity_log(db, claim):
    result = run_followup(
        db,
        claim_id=claim.claim_id,
        claim_pk=claim.id,
        approved_action=_approved_action(),
        approver="A. Carter",
        approved_at=datetime.utcnow(),
    )

    assert isinstance(result, FollowUpResult)
    assert result.attempts == 1

    row = db.query(models.FollowUp).filter(models.FollowUp.id == result.followup_id).first()
    assert row is not None
    assert row.claim_id == claim.id
    assert row.note == "Call payer to confirm authorization status."

    log = db.query(models.ActivityLog).filter(models.ActivityLog.id == result.activity_log_id).first()
    assert log is not None
    assert log.action == "followup_completed"
    details = json.loads(log.details)
    assert details["followup_id"] == row.id
    assert details["approver"] == "A. Carter"


def test_transient_failure_retries_then_succeeds(db, claim):
    result = run_followup(
        db,
        claim_id=claim.claim_id,
        claim_pk=claim.id,
        approved_action=_approved_action(),
        approver="A. Carter",
        approved_at=datetime.utcnow(),
        simulate_transient_failures=1,  # first attempt fails, second succeeds
    )

    assert isinstance(result, FollowUpResult)
    assert result.attempts == 2

    log = db.query(models.ActivityLog).filter(models.ActivityLog.id == result.activity_log_id).first()
    details = json.loads(log.details)
    assert details["attempts"] == 2
    outcomes = [a["outcome"] for a in details["attempt_log"]]
    assert outcomes == ["transient_failure", "success"]

    # A retry that eventually succeeds does not require a fresh approval —
    # exactly one FollowUp row exists, not one per attempt.
    count = db.query(models.FollowUp).filter(models.FollowUp.claim_id == claim.id).count()
    assert count == 1


def test_transient_failure_exhausts_retries_and_escalable(db, claim):
    result = run_followup(
        db,
        claim_id=claim.claim_id,
        claim_pk=claim.id,
        approved_action=_approved_action(),
        approver="A. Carter",
        approved_at=datetime.utcnow(),
        simulate_transient_failures=MAX_RETRIES + 1,  # every attempt fails
    )

    assert isinstance(result, FollowUpFailure)
    assert result.reason == "transient_exhausted"
    assert result.attempts == MAX_RETRIES + 1

    # No FollowUp row exists — a failure never fabricates a success record.
    count = db.query(models.FollowUp).filter(models.FollowUp.claim_id == claim.id).count()
    assert count == 0

    log = db.query(models.ActivityLog).filter(models.ActivityLog.id == result.activity_log_id).first()
    assert log.action == "followup_failed"
    details = json.loads(log.details)
    assert details["reason"] == "transient_exhausted"
    assert details["attempts"] == MAX_RETRIES + 1


@pytest.mark.parametrize("bad_action", [{}, {"note": ""}, {"note": "   "}, {"note": None}])
def test_missing_fields_fails_without_retry(db, claim, bad_action):
    result = run_followup(
        db,
        claim_id=claim.claim_id,
        claim_pk=claim.id,
        approved_action=bad_action,
        approver="A. Carter",
        approved_at=datetime.utcnow(),
        simulate_transient_failures=5,  # would exhaust retries if this path retried at all
    )

    assert isinstance(result, FollowUpFailure)
    assert result.reason == "missing_fields"
    assert result.attempts == 0  # never even attempted — no retry for a broken input

    count = db.query(models.FollowUp).filter(models.FollowUp.claim_id == claim.id).count()
    assert count == 0


def test_revoked_approval_fails_without_retry(db, claim):
    result = run_followup(
        db,
        claim_id=claim.claim_id,
        claim_pk=claim.id,
        approved_action=_approved_action(),
        approver="A. Carter",
        approved_at=datetime.utcnow(),
        approval_still_valid=False,
    )

    assert isinstance(result, FollowUpFailure)
    assert result.reason == "approval_revoked"
    assert result.attempts == 0

    count = db.query(models.FollowUp).filter(models.FollowUp.claim_id == claim.id).count()
    assert count == 0
