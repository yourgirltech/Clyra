"""Seed script to populate clinics, payers, users, and synthetic claims."""
from __future__ import annotations

import sys
import os

# Ensure backend package is importable when running this script directly
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from random import choice, randint, uniform, random, choices
import random as _rnd
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine
from app import models
from app.services import risk_engine


def create_schema():
    models.Base = getattr(models, "Base", None)


def seed():
    db: Session = SessionLocal()
    try:
        # make seeded data reproducible
        _rnd.seed(42)
        # Create base tables if not present
        from app.db.database import Base

        Base.metadata.create_all(bind=engine)

        # Clinics
        clinic = db.query(models.Clinic).filter_by(name="Example Clinic").first()
        if not clinic:
            clinic = models.Clinic(name="Example Clinic")
            db.add(clinic)
            db.commit()
            db.refresh(clinic)

        # Payers
        payer_names = ["Example Health", "HealthPlus", "MediCare Plus", "SafeCare"]
        payers = []
        for name in payer_names:
            p = db.query(models.Payer).filter_by(name=name).first()
            if not p:
                # randomize payer rule requirements so seeded data produces a spread
                auth_req = 1 if random() < 0.5 else 0
                doc_req = 1 if random() < 0.5 else 0
                follow_days = choice([0, 14, 30])
                p = models.Payer(name=name, authorization_required=auth_req, documentation_required=doc_req, follow_up_threshold_days=follow_days)
                db.add(p)
                db.commit()
                db.refresh(p)
            else:
                # ensure some payers have non-default configs
                if p.follow_up_threshold_days is None:
                    p.follow_up_threshold_days = 30
                db.add(p); db.commit(); db.refresh(p)
            payers.append(p)

        statuses = ["Draft", "Submitted", "Processing", "At Risk", "Denied", "Paid", "Needs Review"]
        risks = [("Low", 10), ("Medium", 50), ("High", 90)]

        # Patients (synthetic)
        patient_names = [
            ("Ava", "Johnson"),
            ("Liam", "Smith"),
            ("Olivia", "Brown"),
            ("Noah", "Davis"),
            ("Emma", "Miller"),
            ("Oliver", "Wilson"),
            ("Sophia", "Moore"),
            ("Elijah", "Taylor"),
            ("Isabella", "Anderson"),
            ("Lucas", "Thomas"),
            ("Mia", "Jackson"),
            ("Mason", "White"),
            ("Amelia", "Harris"),
            ("Logan", "Martin"),
            ("Harper", "Thompson"),
            ("Ethan", "Garcia"),
        ]
        patients = []
        for first, last in patient_names:
            p = db.query(models.Patient).filter_by(first_name=first, last_name=last, clinic_id=clinic.id).first()
            if not p:
                p = models.Patient(first_name=first, last_name=last, clinic_id=clinic.id)
                db.add(p)
                db.commit()
                db.refresh(p)
            patients.append(p)

        # create 80 claims
        existing = db.query(models.Claim).count()
        target = 80
        if existing < target:
            for i in range(existing + 1, target + 1):
                payer = choice(payers)
                status = choice(statuses)
                risk_level, base_score = choice(risks)
                risk_score = max(1, min(100, base_score + randint(-15, 15)))
                amount = round(uniform(50.0, 5000.0), 2)
                created_at = datetime.utcnow() - timedelta(days=randint(0, 120))
                # decide issue bucket probabilistically to produce realistic spread
                r = random()
                # ~65% clean, ~25% single-issue, ~10% multi-issue
                if r < 0.65:
                    # clean claim
                    authorization_present = 1
                    documentation_present = 1
                    coding_matches = 1
                    # set a recent follow-up so not overdue when payer expects one
                    if payer.follow_up_threshold_days and payer.follow_up_threshold_days > 0:
                        delta = randint(0, max(0, payer.follow_up_threshold_days - 1))
                        last_followup_at = created_at - timedelta(days=delta)
                    else:
                        last_followup_at = None
                elif r < 0.9:
                    # single issue
                    issue = choice(['missing_authorization', 'missing_documentation', 'code_mismatch', 'overdue_follow_up'])
                    authorization_present = 1
                    documentation_present = 1
                    coding_matches = 1
                    last_followup_at = None
                    if issue == 'missing_authorization':
                        authorization_present = 0
                    elif issue == 'missing_documentation':
                        documentation_present = 0
                    elif issue == 'code_mismatch':
                        coding_matches = 0
                    elif issue == 'overdue_follow_up':
                        # force an old follow-up so it's overdue if payer has a threshold
                        if payer.follow_up_threshold_days and payer.follow_up_threshold_days > 0:
                            last_followup_at = created_at - timedelta(days=payer.follow_up_threshold_days + randint(1, 30))
                        else:
                            last_followup_at = None
                else:
                    # multiple issues (High)
                    authorization_present = choice([0, 1])
                    documentation_present = choice([0, 1])
                    coding_matches = choice([0, 1])
                    # ensure at least two issues
                    issues_now = 0
                    if authorization_present == 0:
                        issues_now += 1
                    if documentation_present == 0:
                        issues_now += 1
                    if coding_matches == 0:
                        issues_now += 1
                    if issues_now < 2:
                        # force an extra issue
                        documentation_present = 0
                    if payer.follow_up_threshold_days and payer.follow_up_threshold_days > 0:
                        # make follow-up overdue
                        last_followup_at = created_at - timedelta(days=payer.follow_up_threshold_days + randint(1, 60))
                    else:
                        last_followup_at = None

                claim = models.Claim(
                    claim_id=f"CL-{10000 + i}",
                    clinic_id=clinic.id,
                    payer_id=payer.id,
                    patient_id=choice(patients).id,
                    amount=amount,
                    status=status,
                    risk_level=risk_level,
                    risk_score=risk_score,
                    created_at=created_at,
                    authorization_present=authorization_present,
                    documentation_present=documentation_present,
                    coding_matches=coding_matches,
                    last_followup_at=last_followup_at,
                )
                db.add(claim)
            db.commit()

        # Ensure existing claims have a patient assigned (if missing)
        claims_without_patient = db.query(models.Claim).filter(models.Claim.clinic_id == clinic.id, models.Claim.patient_id == None).all()
        if claims_without_patient:
            for c in claims_without_patient:
                c.patient_id = choice(patients).id
                db.add(c)
            db.commit()

        print("Seeding complete")
        # Run deterministic analysis over seeded claims
        analyzed = risk_engine.analyze_all_claims(db)
        print(f"Analyzed {analyzed} claims with deterministic rules")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
