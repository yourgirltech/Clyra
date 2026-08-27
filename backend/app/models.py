from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric,
    DateTime,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class Clinic(Base):
    __tablename__ = "clinics"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    email = Column(String(256), nullable=False, unique=True)
    name = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    clinic = relationship("Clinic")


class Payer(Base):
    __tablename__ = "payers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Payer-specific deterministic rule configuration
    authorization_required = Column(Integer, nullable=False, default=0)  # 0/1 as boolean
    documentation_required = Column(Integer, nullable=False, default=0)
    follow_up_threshold_days = Column(Integer, nullable=False, default=30)


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic")


class Claim(Base):
    __tablename__ = "claims"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(String(64), nullable=False, unique=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    payer_id = Column(Integer, ForeignKey("payers.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    risk_level = Column(String(16), nullable=False, index=True)
    risk_score = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Evidence fields for deterministic rule engine
    authorization_present = Column(Integer, nullable=False, default=0)
    documentation_present = Column(Integer, nullable=False, default=0)
    coding_matches = Column(Integer, nullable=False, default=1)
    last_followup_at = Column(DateTime, nullable=True)

    clinic = relationship("Clinic")
    payer = relationship("Payer")
    patient = relationship("Patient")


class ClaimIssue(Base):
    __tablename__ = "claim_issues"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    issue_type = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False)
    description = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # 03-recommendation-agent output (docs/agents/03-recommendation-agent.md)
    action_type = Column(String(32), nullable=True, index=True)
    confidence = Column(String(16), nullable=True)  # "High" | "Medium" | "Low"
    low_confidence = Column(Integer, nullable=False, default=0)  # 0/1 as boolean
    cited_issue_types = Column(Text, nullable=True)  # JSON-encoded list[str]
    secondary_options = Column(Text, nullable=True)  # JSON-encoded list[dict]
    raw_model_response = Column(Text, nullable=True)
    # Human-review lifecycle. "pending" awaits an approve/decline decision;
    # "escalated" means 03 itself reported low_confidence, so this was never
    # offered to a human as a one-click approval (rule 13) — approve/decline
    # only ever apply to a "pending" row.
    approval_status = Column(String(16), nullable=False, default="pending", index=True)
    decided_at = Column(DateTime, nullable=True)


class FollowUp(Base):
    __tablename__ = "follow_ups"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    note = Column(Text, nullable=False)
    due_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PayerReminder(Base):
    """A payer-reminder action executed by 05-reminder-agent
    (docs/agents/05-reminder-agent.md). Synthetic-data demo: "sent" means
    simulated and durably recorded here, not actually delivered anywhere."""

    __tablename__ = "payer_reminders"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    target = Column(String(128), nullable=False)  # payer/system the reminder targets
    content = Column(Text, nullable=False)
    reference_number = Column(String(64), nullable=True)
    sent_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(128), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Escalation(Base):
    __tablename__ = "escalations"
    id = Column(Integer, primary_key=True, index=True)
    # No FK: 06-escalation-agent must be able to flag a claim_id that never
    # resolved to a real claim (rule 1) — the whole point of that rule.
    claim_id = Column(String(64), nullable=True, index=True)
    reason_code = Column(String(64), nullable=False, index=True)
    rule = Column(Integer, nullable=False)
    originating_agent = Column(String(128), nullable=False)
    severity = Column(String(16), nullable=False, index=True)
    context = Column(Text, nullable=False)  # JSON-serialized context chain
    created_at = Column(DateTime, default=datetime.utcnow)
