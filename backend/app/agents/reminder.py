"""05-reminder-agent — executes an approved payer_reminder recommendation
(docs/agents/05-reminder-agent.md).

Same shape as 04-followup-agent: mechanical execution of an already-decided,
already-approved action. Does not decide whether or what to remind a payer
about — that was 03-recommendation-agent's proposal and a human's approval.

Synthetic-data demo: there is no real payer channel to call, so "sending" a
reminder means simulating that call and creating a real, durable
`PayerReminder` + `ActivityLog` row — never fabricating success without those
rows actually existing.

Retry policy is identical to 04's: bounded automatic retry with backoff for
a transient failure, no retry for a non-transient one. `simulate_transient_
failures` makes the transient path deliberately triggerable for tests.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union

from sqlalchemy.orm import Session

from app import models

MAX_RETRIES = 2  # up to 2 retries beyond the first attempt = 3 attempts total
BACKOFF_BASE_SECONDS = 0.05  # kept tiny on purpose — this is a synchronous demo request


@dataclass(frozen=True)
class ReminderResult:
    claim_id: str
    reminder_id: int
    target: str
    content: str
    reference_number: Optional[str]
    attempts: int
    activity_log_id: int


@dataclass(frozen=True)
class ReminderFailure:
    claim_id: Optional[str]
    reason: str  # "missing_fields" | "approval_revoked" | "transient_exhausted"
    detail: str
    attempts: int
    activity_log_id: Optional[int]


def _validate_approved_action(approved_action: object) -> Optional[str]:
    if not isinstance(approved_action, dict):
        return "approved_action must be a dict"
    target = approved_action.get("target")
    content = approved_action.get("content")
    if not isinstance(target, str) or not target.strip():
        return "target (who/what system the reminder is directed at) is missing or empty"
    if not isinstance(content, str) or not content.strip():
        return "reminder content is missing or empty"
    return None


def _log_activity(db: Session, claim_pk: int, action: str, details: dict) -> models.ActivityLog:
    entry = models.ActivityLog(claim_id=claim_pk, action=action, details=json.dumps(details, default=str))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def run_reminder(
    db: Session,
    *,
    claim_id: str,
    claim_pk: int,
    approved_action: dict,
    approver: str,
    approved_at: datetime,
    approval_still_valid: bool = True,
    simulate_transient_failures: int = 0,
) -> Union[ReminderResult, ReminderFailure]:
    """Execute one approved payer_reminder action.

    `approved_action` must already carry the fixed content decided at
    approval time — `{"target": str, "content": str, "reference_number": str
    | None}`. This agent never drafts or edits it. `approval_still_valid=
    False` and `simulate_transient_failures>0` are test-only levers for the
    two failure paths the spec calls out; production callers never need
    them.
    """
    if not approval_still_valid:
        detail = "approval was revoked between routing and execution"
        entry = _log_activity(
            db, claim_pk, "reminder_failed",
            {"reason": "approval_revoked", "detail": detail, "attempts": 0, "approver": approver, "approved_at": approved_at},
        )
        return ReminderFailure(claim_id, "approval_revoked", detail, 0, entry.id)

    error = _validate_approved_action(approved_action)
    if error:
        entry = _log_activity(
            db, claim_pk, "reminder_failed",
            {"reason": "missing_fields", "detail": error, "attempts": 0, "approver": approver, "approved_at": approved_at},
        )
        return ReminderFailure(claim_id, "missing_fields", error, 0, entry.id)

    attempt_log: list[dict] = []
    attempt = 0
    while True:
        attempt += 1
        if attempt <= simulate_transient_failures:
            attempt_log.append({"attempt": attempt, "outcome": "transient_failure", "detail": "simulated payer channel timeout"})
            if attempt >= MAX_RETRIES + 1:
                detail = f"payer channel unavailable after {attempt} attempt(s)"
                entry = _log_activity(
                    db, claim_pk, "reminder_failed",
                    {
                        "reason": "transient_exhausted", "detail": detail, "attempts": attempt,
                        "approver": approver, "approved_at": approved_at, "attempt_log": attempt_log,
                    },
                )
                return ReminderFailure(claim_id, "transient_exhausted", detail, attempt, entry.id)
            time.sleep(BACKOFF_BASE_SECONDS * attempt)
            continue

        attempt_log.append({"attempt": attempt, "outcome": "success"})
        break

    sent_at = datetime.utcnow()
    row = models.PayerReminder(
        claim_id=claim_pk,
        target=approved_action["target"],
        content=approved_action["content"],
        reference_number=approved_action.get("reference_number"),
        sent_at=sent_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    entry = _log_activity(
        db, claim_pk, "reminder_completed",
        {
            "reminder_id": row.id, "target": row.target, "approver": approver, "approved_at": approved_at,
            "attempts": attempt, "attempt_log": attempt_log,
        },
    )
    return ReminderResult(claim_id, row.id, row.target, row.content, row.reference_number, attempt, entry.id)
