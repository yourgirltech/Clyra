"""Tests for 05-reminder-agent (backend/app/agents/reminder.py).

Same shape as test_followup.py: no LLM involved, real Postgres writes for
success (PayerReminder + ActivityLog), the bounded transient-retry-with-
backoff path (deliberately triggered via `simulate_transient_failures`), and
the two non-transient failure paths (missing fields, revoked approval) that
never retry.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from app import models
from app.agents.reminder import MAX_RETRIES, ReminderFailure, ReminderResult, run_reminder
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
        claim_id="CL-TEST-REMINDER",
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
    db.query(models.PayerReminder).filter(models.PayerReminder.claim_id == row.id).delete()
    db.query(models.Claim).filter(models.Claim.id == row.id).delete()
    db.commit()


def _approved_action(**overrides):
    action = {"target": "DistPayerHigh", "content": "Please confirm status of claim CL-TEST-REMINDER.", "reference_number": "CL-TEST-REMINDER"}
    action.update(overrides)
    return action


def test_success_creates_real_reminder_and_activity_log(db, claim):
    result = run_reminder(
        db,
        claim_id=claim.claim_id,
        claim_pk=claim.id,
        approved_action=_approved_action(),
        approver="A. Carter",
        approved_at=datetime.utcnow(),
    )

    assert isinstance(result, ReminderResult)
    assert result.attempts == 1

    row = db.query(models.PayerReminder).filter(models.PayerReminder.id == result.reminder_id).first()
    assert row is not None
    assert row.claim_id == claim.id
    assert row.target == "DistPayerHigh"
    assert row.reference_number == "CL-TEST-REMINDER"

    log = db.query(models.ActivityLog).filter(models.ActivityLog.id == result.activity_log_id).first()
    assert log is not None
    assert log.action == "reminder_completed"
    details = json.loads(log.details)
    assert details["reminder_id"] == row.id
    assert details["approver"] == "A. Carter"


def test_transient_failure_retries_then_succeeds(db, claim):
    result = run_reminder(
        db,
        claim_id=claim.claim_id,
        claim_pk=claim.id,
        approved_action=_approved_action(),
        approver="A. Carter",
        approved_at=datetime.utcnow(),
        simulate_transient_failures=1,
    )

    assert isinstance(result, ReminderResult)
    assert result.attempts == 2

    log = db.query(models.ActivityLog).filter(models.ActivityLog.id == result.activity_log_id).first()
    details = json.loads(log.details)
    assert details["attempts"] == 2
    outcomes = [a["outcome"] for a in details["attempt_log"]]
    assert outcomes == ["transient_failure", "success"]

    count = db.query(models.PayerReminder).filter(models.PayerReminder.claim_id == claim.id).count()
    assert count == 1


def test_transient_failure_exhausts_retries(db, claim):
    result = run_reminder(
        db,
        claim_id=claim.claim_id,
        claim_pk=claim.id,
        approved_action=_approved_action(),
        approver="A. Carter",
        approved_at=datetime.utcnow(),
        simulate_transient_failures=MAX_RETRIES + 1,
    )

    assert isinstance(result, ReminderFailure)
    assert result.reason == "transient_exhausted"
    assert result.attempts == MAX_RETRIES + 1

    count = db.query(models.PayerReminder).filter(models.PayerReminder.claim_id == claim.id).count()
    assert count == 0

    log = db.query(models.ActivityLog).filter(models.ActivityLog.id == result.activity_log_id).first()
    assert log.action == "reminder_failed"


@pytest.mark.parametrize("bad_action", [{}, {"target": ""}, {"target": "Payer", "content": ""}, {"target": "Payer"}])
def test_missing_fields_fails_without_retry(db, claim, bad_action):
    result = run_reminder(
        db,
        claim_id=claim.claim_id,
        claim_pk=claim.id,
        approved_action=bad_action,
        approver="A. Carter",
        approved_at=datetime.utcnow(),
        simulate_transient_failures=5,
    )

    assert isinstance(result, ReminderFailure)
    assert result.reason == "missing_fields"
    assert result.attempts == 0

    count = db.query(models.PayerReminder).filter(models.PayerReminder.claim_id == claim.id).count()
    assert count == 0


def test_revoked_approval_fails_without_retry(db, claim):
    result = run_reminder(
        db,
        claim_id=claim.claim_id,
        claim_pk=claim.id,
        approved_action=_approved_action(),
        approver="A. Carter",
        approved_at=datetime.utcnow(),
        approval_still_valid=False,
    )

    assert isinstance(result, ReminderFailure)
    assert result.reason == "approval_revoked"
    assert result.attempts == 0

    count = db.query(models.PayerReminder).filter(models.PayerReminder.claim_id == claim.id).count()
    assert count == 0
