"""04-followup-agent — executes an approved follow_up recommendation
(docs/agents/04-followup-agent.md).

Mechanical, on purpose: it does not decide whether or what to follow up —
03-recommendation-agent proposed the action and a human already approved it.
This agent's only job is to create a durable record of what was done, or
fail honestly and say why.

Synthetic-data demo: there is no real downstream system to call, so
"executing" a follow-up means simulating that call and creating a real,
durable `FollowUp` + `ActivityLog` row — never fabricating success without
those rows actually existing.

Retry policy (docs, "What happens when its first attempt fails"): a
transient failure (a downstream dependency being briefly unavailable) gets
a small bounded automatic retry with backoff; a non-transient failure
(missing required fields, a revoked approval) never retries — retrying a
broken input just delays the human finding out. `simulate_transient_failures`
makes the transient path deliberately triggerable for tests, rather than
leaving it as untestable theory.
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
class FollowUpResult:
    claim_id: str
    followup_id: int
    note: str
    due_at: Optional[datetime]
    attempts: int
    activity_log_id: int


@dataclass(frozen=True)
class FollowUpFailure:
    claim_id: Optional[str]
    reason: str  # "missing_fields" | "approval_revoked" | "transient_exhausted"
    detail: str
    attempts: int
    activity_log_id: Optional[int]


def _validate_approved_action(approved_action: object) -> Optional[str]:
    if not isinstance(approved_action, dict):
        return "approved_action must be a dict"
    note = approved_action.get("note")
    if not isinstance(note, str) or not note.strip():
        return "note content is missing or empty"
    return None


def _log_activity(db: Session, claim_pk: int, action: str, details: dict) -> models.ActivityLog:
    entry = models.ActivityLog(claim_id=claim_pk, action=action, details=json.dumps(details, default=str))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def run_followup(
    db: Session,
    *,
    claim_id: str,
    claim_pk: int,
    approved_action: dict,
    approver: str,
    approved_at: datetime,
    approval_still_valid: bool = True,
    simulate_transient_failures: int = 0,
) -> Union[FollowUpResult, FollowUpFailure]:
    """Execute one approved follow_up action.

    `approved_action` must already carry the fixed content decided at
    approval time — `{"note": str, "due_at": datetime | None}`. This agent
    never drafts or edits it. `approval_still_valid=False` and
    `simulate_transient_failures>0` are test-only levers for the two failure
    paths the spec calls out; production callers never need them.
    """
    # Non-transient checks first — no retry, ever.
    if not approval_still_valid:
        detail = "approval was revoked between routing and execution"
        entry = _log_activity(
            db, claim_pk, "followup_failed",
            {"reason": "approval_revoked", "detail": detail, "attempts": 0, "approver": approver, "approved_at": approved_at},
        )
        return FollowUpFailure(claim_id, "approval_revoked", detail, 0, entry.id)

    error = _validate_approved_action(approved_action)
    if error:
        entry = _log_activity(
            db, claim_pk, "followup_failed",
            {"reason": "missing_fields", "detail": error, "attempts": 0, "approver": approver, "approved_at": approved_at},
        )
        return FollowUpFailure(claim_id, "missing_fields", error, 0, entry.id)

    attempt_log: list[dict] = []
    attempt = 0
    while True:
        attempt += 1
        if attempt <= simulate_transient_failures:
            attempt_log.append({"attempt": attempt, "outcome": "transient_failure", "detail": "simulated downstream timeout"})
            if attempt >= MAX_RETRIES + 1:
                detail = f"downstream unavailable after {attempt} attempt(s)"
                entry = _log_activity(
                    db, claim_pk, "followup_failed",
                    {
                        "reason": "transient_exhausted", "detail": detail, "attempts": attempt,
                        "approver": approver, "approved_at": approved_at, "attempt_log": attempt_log,
                    },
                )
                return FollowUpFailure(claim_id, "transient_exhausted", detail, attempt, entry.id)
            time.sleep(BACKOFF_BASE_SECONDS * attempt)
            continue

        attempt_log.append({"attempt": attempt, "outcome": "success"})
        break

    row = models.FollowUp(claim_id=claim_pk, note=approved_action["note"], due_at=approved_action.get("due_at"))
    db.add(row)
    db.commit()
    db.refresh(row)

    entry = _log_activity(
        db, claim_pk, "followup_completed",
        {
            "followup_id": row.id, "approver": approver, "approved_at": approved_at,
            "attempts": attempt, "attempt_log": attempt_log,
        },
    )
    return FollowUpResult(claim_id, row.id, row.note, row.due_at, attempt, entry.id)
