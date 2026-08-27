"""06-escalation-agent — the system's safety net
(docs/agents/06-escalation-agent.md).

Runs whenever something can't be safely handled by the deterministic/agent
pipeline on its own: an outright error, a low-confidence recommendation, a
failed execution, or an event Commander doesn't even recognize. Its entire
job is to flag the situation for a human, with full context, and stop. It
never guesses at a resolution, never retries the thing that failed, never
calls the rule engine or an LLM, and never produces a recommendation of its
own — that would just be re-introducing the uncertainty this agent exists to
contain. There is no `escalation_completed` event: this is a leaf, nothing
routes anywhere from here.

This is the one agent in the pipeline with a real durability requirement:
per the spec, escalation "must be the most reliable write path in the whole
system," since it's the backstop for every other agent's failures. The
primary write is a durable `escalations` table row; if that write itself
fails, a fallback durable log entry is written instead, at CRITICAL level —
an escalation must never simply vanish because the primary flag store was
briefly unavailable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger("clyra.escalations")

# Severity/urgency derived from the reason code (docs/agents/06-escalation-agent.md):
# an execution failure on an already-approved action is more urgent than a
# low-confidence recommendation that was never shown to anyone.
SEVERITY_BY_REASON = {
    "invalid_trigger": "high",
    "analyzer_error": "high",
    "reasoning_error": "medium",
    "recommendation_error": "medium",
    "low_confidence": "low",
    "followup_execution_failed": "high",
    "reminder_execution_failed": "high",
    "unclassified_trigger": "medium",
}
DEFAULT_SEVERITY = "medium"

# Which agent/rule produced the event that led here, for a reviewer's context.
ORIGIN_BY_RULE = {
    1: "commander",
    7: "01-analyzer-agent",
    9: "02-reasoning-agent",
    11: "03-recommendation-agent",
    13: "03-recommendation-agent",
    17: "04-followup-agent",
    18: "05-reminder-agent",
    20: "commander",
}


@dataclass(frozen=True)
class EscalationResult:
    claim_id: Optional[str]
    reason_code: str
    rule: int
    originating_agent: str
    severity: str
    context: dict
    created_at: datetime
    persisted: bool  # True: written to the escalations table. False: fallback log only.
    escalation_id: Optional[int]  # DB row id, when persisted is True


def run_escalation(
    db: Session,
    *,
    claim_id: Optional[str],
    reason_code: str,
    rule: int,
    context: dict,
) -> EscalationResult:
    """Flag a claim/event for human review. No suggested resolution, ever —
    this function has no field or code path that could carry one.

    `claim_id` may be `None` (rule 1: the trigger's claim_id never resolved
    to a claim at all — that is itself a valid escalation, not an error to
    raise). `context` is whatever's available: latest issues, latest
    reasoning/recommendation output, partial output from whatever agent
    failed — the caller assembles it from what it actually has.
    """
    severity = SEVERITY_BY_REASON.get(reason_code, DEFAULT_SEVERITY)
    originating_agent = ORIGIN_BY_RULE.get(rule, f"rule {rule}")
    created_at = datetime.utcnow()
    context_json = json.dumps(context, default=str, indent=2)

    try:
        row = models.Escalation(
            claim_id=claim_id,
            reason_code=reason_code,
            rule=rule,
            originating_agent=originating_agent,
            severity=severity,
            context=context_json,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return EscalationResult(
            claim_id=claim_id,
            reason_code=reason_code,
            rule=rule,
            originating_agent=originating_agent,
            severity=severity,
            context=context,
            created_at=row.created_at,
            persisted=True,
            escalation_id=row.id,
        )
    except Exception as exc:  # the primary write is not allowed to lose this silently
        try:
            db.rollback()
        except Exception:
            pass  # the rollback itself failing must not stop the fallback log below
        logger.critical(
            "ESCALATION WRITE FAILED — falling back to durable log. "
            "claim_id=%s reason_code=%s rule=%s severity=%s originating_agent=%s "
            "db_error=%s context=%s",
            claim_id, reason_code, rule, severity, originating_agent, exc, context_json,
        )
        return EscalationResult(
            claim_id=claim_id,
            reason_code=reason_code,
            rule=rule,
            originating_agent=originating_agent,
            severity=severity,
            context=context,
            created_at=created_at,
            persisted=False,
            escalation_id=None,
        )
