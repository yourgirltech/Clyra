"""Tests for 06-escalation-agent (backend/app/agents/escalation.py) and its
wiring into Commander's dispatch (backend/app/agents/dispatch.py).

No LLM involved — 06 never calls one, per spec. What's under test instead:
a real Postgres write for every rule that routes here (1, 7, 9, 11, 13, 14,
15, 20), the durable-fallback-log path when that write itself fails, and one
full end-to-end printout of an actual persisted record.
"""

import logging

import pytest

from app.agents.commander import AGENT_ESCALATION, commander_route
from app.agents.dispatch import route_and_dispatch
from app.agents.escalation import EscalationResult, run_escalation


@pytest.fixture
def db_session():
    """Real DB session, with automatic cleanup of any Escalation rows this
    test creates — this is a demo/dev database, not a throwaway test DB, so
    we don't want every test run to leave junk rows behind."""
    from app import models
    from app.db.database import SessionLocal

    session = SessionLocal()
    created_ids: list[int] = []
    try:
        yield session, created_ids
    finally:
        for eid in created_ids:
            row = session.query(models.Escalation).filter(models.Escalation.id == eid).first()
            if row:
                session.delete(row)
        session.commit()
        session.close()


def _claim_state(**overrides):
    state = {
        "claim_id": "CL-1",
        "status": "Submitted",
        "risk_score": 50,
        "risk_level": "High",
        "latest_issues": [],
        "latest_recommendation": None,
        "agent_run_in_progress": False,
    }
    state.update(overrides)
    return state


def _make_trigger(type_):
    return {"type": type_, "payload": {}}


# ---------------------------------------------------------------------------
# One real escalation record per rule that routes to 06-escalation-agent in
# Phase 4: 1, 7, 9, 11, 13, 14, 15, 20. Each case confirms dispatch actually
# persisted a row with the right reason/rule, not just that it ran without
# error — queried back from the DB directly, not just read off the return
# value.
# ---------------------------------------------------------------------------

def test_rule01_invalid_trigger_creates_real_escalation(db_session):
    from app import models

    session, created_ids = db_session
    decision, result = route_and_dispatch(None, None, db=session)
    created_ids.append(result.escalation_id)

    assert decision.rule == 1
    assert isinstance(result, EscalationResult)
    assert result.persisted is True
    assert result.claim_id is None  # rule 1: the claim never resolved at all

    row = session.query(models.Escalation).filter(models.Escalation.id == result.escalation_id).first()
    assert row is not None
    assert row.reason_code == "invalid_trigger"
    assert row.rule == 1
    assert row.severity == "high"


def test_rule07_analyzer_error_creates_real_escalation(db_session):
    from app import models

    session, created_ids = db_session
    decision, result = route_and_dispatch(_claim_state(), _make_trigger("analyzer_failed"), db=session)
    created_ids.append(result.escalation_id)

    assert decision.rule == 7
    row = session.query(models.Escalation).filter(models.Escalation.id == result.escalation_id).first()
    assert row is not None
    assert row.reason_code == "analyzer_error"
    assert row.rule == 7
    assert row.originating_agent == "01-analyzer-agent"
    assert row.severity == "high"


def test_rule09_reasoning_error_creates_real_escalation(db_session):
    from app import models

    session, created_ids = db_session
    decision, result = route_and_dispatch(_claim_state(), _make_trigger("reasoning_failed"), db=session)
    created_ids.append(result.escalation_id)

    assert decision.rule == 9
    row = session.query(models.Escalation).filter(models.Escalation.id == result.escalation_id).first()
    assert row is not None
    assert row.reason_code == "reasoning_error"
    assert row.rule == 9
    assert row.originating_agent == "02-reasoning-agent"
    assert row.severity == "medium"


def test_rule11_recommendation_error_creates_real_escalation(db_session):
    from app import models

    session, created_ids = db_session
    decision, result = route_and_dispatch(_claim_state(), _make_trigger("recommendation_failed"), db=session)
    created_ids.append(result.escalation_id)

    assert decision.rule == 11
    row = session.query(models.Escalation).filter(models.Escalation.id == result.escalation_id).first()
    assert row is not None
    assert row.reason_code == "recommendation_error"
    assert row.rule == 11
    assert row.originating_agent == "03-recommendation-agent"
    assert row.severity == "medium"


def test_rule13_low_confidence_creates_real_escalation(db_session):
    from app import models

    session, created_ids = db_session
    claim_state = _claim_state(
        latest_recommendation={
            "action_type": "manual_review_needed",
            "low_confidence": True,
            "approval_status": "none",
        }
    )
    decision, result = route_and_dispatch(claim_state, _make_trigger("recommendation_completed"), db=session)
    created_ids.append(result.escalation_id)

    assert decision.rule == 13
    row = session.query(models.Escalation).filter(models.Escalation.id == result.escalation_id).first()
    assert row is not None
    assert row.reason_code == "low_confidence"
    assert row.rule == 13
    assert row.severity == "low"
    # The context chain includes what was known about the recommendation.
    assert "manual_review_needed" in row.context


def test_rule14_follow_up_carve_out_creates_real_escalation(db_session):
    from app import models

    session, created_ids = db_session
    claim_state = _claim_state(
        latest_recommendation={
            "action_type": "follow_up",
            "low_confidence": False,
            "approval_status": "pending",
        }
    )
    decision, result = route_and_dispatch(claim_state, _make_trigger("human_approved"), db=session)
    created_ids.append(result.escalation_id)

    assert decision.rule == 14
    row = session.query(models.Escalation).filter(models.Escalation.id == result.escalation_id).first()
    assert row is not None
    assert row.reason_code == "agent_not_yet_implemented"
    assert row.rule == 14
    assert "04-followup-agent" in row.originating_agent
    assert row.severity == "high"  # already approved, just can't execute yet


def test_rule15_payer_reminder_carve_out_creates_real_escalation(db_session):
    from app import models

    session, created_ids = db_session
    claim_state = _claim_state(
        latest_recommendation={
            "action_type": "payer_reminder",
            "low_confidence": False,
            "approval_status": "pending",
        }
    )
    decision, result = route_and_dispatch(claim_state, _make_trigger("human_approved"), db=session)
    created_ids.append(result.escalation_id)

    assert decision.rule == 15
    row = session.query(models.Escalation).filter(models.Escalation.id == result.escalation_id).first()
    assert row is not None
    assert row.reason_code == "agent_not_yet_implemented"
    assert row.rule == 15
    assert "05-reminder-agent" in row.originating_agent
    assert row.severity == "high"


def test_rule20_unclassified_trigger_creates_real_escalation(db_session):
    from app import models

    session, created_ids = db_session
    decision, result = route_and_dispatch(
        _claim_state(), _make_trigger("some_event_commander_has_never_seen"), db=session
    )
    created_ids.append(result.escalation_id)

    assert decision.rule == 20
    row = session.query(models.Escalation).filter(models.Escalation.id == result.escalation_id).first()
    assert row is not None
    assert row.reason_code == "unclassified_trigger"
    assert row.rule == 20
    assert row.severity == "medium"


# ---------------------------------------------------------------------------
# The durability requirement: if the primary write fails, a fallback durable
# log entry must fire — an escalation is never silently lost.
# ---------------------------------------------------------------------------

class _ExplodingDB:
    def add(self, obj):
        pass

    def commit(self):
        raise RuntimeError("database is unreachable")

    def refresh(self, obj):
        pass

    def rollback(self):
        pass


def test_escalation_write_failure_falls_back_to_durable_log(caplog):
    with caplog.at_level(logging.CRITICAL, logger="clyra.escalations"):
        result = run_escalation(
            _ExplodingDB(),
            claim_id="CL-1",
            reason_code="analyzer_error",
            rule=7,
            context={"note": "primary write is down"},
        )

    assert result.persisted is False
    assert result.escalation_id is None
    # Nothing about the escalation itself is lost even though persistence failed.
    assert result.reason_code == "analyzer_error"
    assert result.severity == "high"

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.CRITICAL
    assert "ESCALATION WRITE FAILED" in record.message
    assert "CL-1" in record.message
    assert "analyzer_error" in record.message


def test_escalation_write_failure_rollback_itself_failing_does_not_hide_the_log(caplog):
    class _DoublyBrokenDB(_ExplodingDB):
        def rollback(self):
            raise RuntimeError("rollback is broken too")

    with caplog.at_level(logging.CRITICAL, logger="clyra.escalations"):
        result = run_escalation(
            _DoublyBrokenDB(), claim_id="CL-1", reason_code="unclassified_trigger", rule=20, context={}
        )

    assert result.persisted is False
    assert len(caplog.records) == 1


# ---------------------------------------------------------------------------
# Show one real escalation record, end to end.
# ---------------------------------------------------------------------------

def test_end_to_end_escalation_record_is_readable(db_session, capsys):
    from app import models

    session, created_ids = db_session
    claim_state = _claim_state(
        claim_id="CL-10002",
        status="At Risk",
        risk_score=100,
        risk_level="High",
        latest_issues=[{"issue_type": "missing_authorization", "severity": "high"}],
        latest_recommendation={
            "action_type": "manual_review_needed",
            "low_confidence": True,
            "approval_status": "none",
        },
    )
    decision, result = route_and_dispatch(
        claim_state,
        _make_trigger("recommendation_completed"),
        db=session,
        escalation_extra_context={
            "recommendation_rationale": "insufficient basis for a recommendation",
        },
    )
    created_ids.append(result.escalation_id)

    row = session.query(models.Escalation).filter(models.Escalation.id == result.escalation_id).first()

    with capsys.disabled():
        print("\n" + "=" * 78)
        print("06-escalation-agent — real persisted record")
        print("=" * 78)
        print(f"id:                {row.id}")
        print(f"claim_id:          {row.claim_id}")
        print(f"reason_code:       {row.reason_code}")
        print(f"rule:              {row.rule}")
        print(f"originating_agent: {row.originating_agent}")
        print(f"severity:          {row.severity}")
        print(f"created_at:        {row.created_at}")
        print(f"context:\n{row.context}")
        print("=" * 78)

    assert decision.rule == 13
    assert decision.decision == AGENT_ESCALATION
    assert row.claim_id == "CL-10002"
    assert row.reason_code == "low_confidence"
    assert "insufficient basis for a recommendation" in row.context
    assert "missing_authorization" in row.context
