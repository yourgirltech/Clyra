"""Seed script to populate clinics, payers, users, and synthetic claims.

Two phases:

1. **Create** base rows (clinic, payers, patients) and up to `TARGET` synthetic
   claims with realistic evidence fields. Deterministic (`random.seed(42)`) and
   idempotent — re-running never creates duplicates.

2. **Reconcile** EVERY claim in the DB through the real analyzer + Commander
   (`app.services.claim_status.reconcile_all_claims`): persist each claim's
   issues / risk_score / risk_level from the actual rule engine, then set its
   status so it can never silently disagree with that analysis. This phase runs
   on every invocation, so re-running the seed against an existing (e.g.
   production) database repairs any incoherent rows in place.

See docs/architecture.md, "Claim status and computed risk".
"""
from __future__ import annotations

import sys
import os

# Ensure backend package is importable when running this script directly
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from collections import Counter
from random import choice, randint, uniform, random
import random as _rnd
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.database import SessionLocal, engine
from app import models
from app.services import claim_status

TARGET = 80

# Lifecycle bucket mix for freshly created claims. Terminal buckets carry an
# outcome set outside our rule checks (see docs/architecture.md):
#   - "Paid"   claims are forced clean, so they stay internally coherent.
#   - "Denied" claims get normal random evidence; a Denied claim is ALLOWED to
#     diverge from our internal risk score, and this is where that shows up.
BUCKET_PAID = 0.08
BUCKET_DENIED = 0.12


def _clean_evidence(payer, created_at):
    """Evidence for a claim with no rule-engine issues."""
    last_followup_at = None
    if payer.follow_up_threshold_days and payer.follow_up_threshold_days > 0:
        delta = randint(0, max(0, payer.follow_up_threshold_days - 1))
        last_followup_at = created_at - timedelta(days=delta)
    return dict(
        authorization_present=1,
        documentation_present=1,
        coding_matches=1,
        last_followup_at=last_followup_at,
    )


def _random_evidence(payer, created_at):
    """Realistic spread of real, analyzable evidence: ~45% clean, ~30%
    single-issue, ~25% multi-issue. Multi-issue claims lean on
    missing_authorization (the only 'high'-severity check, 50 pts) so a
    meaningful share genuinely compute to High once the rule engine runs.
    """
    r = random()
    if r < 0.45:
        return _clean_evidence(payer, created_at)

    ev = dict(authorization_present=1, documentation_present=1, coding_matches=1, last_followup_at=None)

    def _make_overdue():
        if payer.follow_up_threshold_days and payer.follow_up_threshold_days > 0:
            return created_at - timedelta(days=payer.follow_up_threshold_days + randint(1, 45))
        return None

    if r < 0.75:
        # single issue, biased toward missing_authorization
        issue = choice(
            ["missing_authorization", "missing_authorization",
             "missing_documentation", "code_mismatch", "overdue_follow_up"]
        )
        if issue == "missing_authorization":
            ev["authorization_present"] = 0
        elif issue == "missing_documentation":
            ev["documentation_present"] = 0
        elif issue == "code_mismatch":
            ev["coding_matches"] = 0
        elif issue == "overdue_follow_up":
            ev["last_followup_at"] = _make_overdue()
        return ev

    # multi-issue — ~60% carry a missing authorization, pushing them to High
    ev["authorization_present"] = 0 if random() < 0.6 else 1
    ev["documentation_present"] = choice([0, 1])
    ev["coding_matches"] = choice([0, 1])
    if sum(1 for k in ("authorization_present", "documentation_present", "coding_matches") if ev[k] == 0) < 2:
        ev["coding_matches"] = 0
    ev["last_followup_at"] = _make_overdue()
    return ev


def seed():
    db: Session = SessionLocal()
    try:
        _rnd.seed(42)
        from app.db.database import Base

        Base.metadata.create_all(bind=engine)

        # Clinics
        clinic = db.query(models.Clinic).filter_by(name="Example Clinic").first()
        if not clinic:
            clinic = models.Clinic(name="Example Clinic")
            db.add(clinic)
            db.commit()
            db.refresh(clinic)

        # Payers — an explicit spread of rule requirements so a fresh analysis
        # exercises every deterministic check across the claim set.
        payer_configs = [
            ("Example Health", dict(authorization_required=1, documentation_required=1, follow_up_threshold_days=30)),
            ("HealthPlus", dict(authorization_required=1, documentation_required=0, follow_up_threshold_days=14)),
            ("MediCare Plus", dict(authorization_required=0, documentation_required=1, follow_up_threshold_days=30)),
            ("SafeCare", dict(authorization_required=0, documentation_required=0, follow_up_threshold_days=0)),
        ]
        payers = []
        for name, cfg in payer_configs:
            p = db.query(models.Payer).filter_by(name=name).first()
            if not p:
                p = models.Payer(name=name, **cfg)
                db.add(p)
                db.commit()
                db.refresh(p)
            elif p.follow_up_threshold_days is None:
                p.follow_up_threshold_days = 30
                db.add(p)
                db.commit()
                db.refresh(p)
            payers.append(p)

        # Patients (synthetic)
        patient_names = [
            ("Ava", "Johnson"), ("Liam", "Smith"), ("Olivia", "Brown"), ("Noah", "Davis"),
            ("Emma", "Miller"), ("Oliver", "Wilson"), ("Sophia", "Moore"), ("Elijah", "Taylor"),
            ("Isabella", "Anderson"), ("Lucas", "Thomas"), ("Mia", "Jackson"), ("Mason", "White"),
            ("Amelia", "Harris"), ("Logan", "Martin"), ("Harper", "Thompson"), ("Ethan", "Garcia"),
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

        # ---- Phase 1: create claims (base fields only; status/risk are set in phase 2) ----
        existing = db.query(models.Claim).count()
        if existing < TARGET:
            for i in range(existing + 1, TARGET + 1):
                payer = choice(payers)
                created_at = datetime.utcnow() - timedelta(days=randint(0, 120))

                bucket_roll = random()
                if bucket_roll < BUCKET_PAID:
                    seed_status = "Paid"
                    evidence = _clean_evidence(payer, created_at)
                elif bucket_roll < BUCKET_PAID + BUCKET_DENIED:
                    seed_status = "Denied"
                    evidence = _random_evidence(payer, created_at)
                else:
                    seed_status = "Draft"  # placeholder — phase 2 derives the real active status
                    evidence = _random_evidence(payer, created_at)

                db.add(models.Claim(
                    claim_id=f"CL-{10000 + i}",
                    clinic_id=clinic.id,
                    payer_id=payer.id,
                    patient_id=choice(patients).id,
                    amount=round(uniform(50.0, 5000.0), 2),
                    status=seed_status,
                    risk_level="Low",
                    risk_score=0,
                    created_at=created_at,
                    **evidence,
                ))
            db.commit()

        # Backfill any claim missing a patient
        for c in db.query(models.Claim).filter(
            models.Claim.clinic_id == clinic.id, models.Claim.patient_id.is_(None)
        ).all():
            c.patient_id = choice(patients).id
            db.add(c)
        db.commit()

        print(f"Phase 1: {db.query(models.Claim).count()} claims present.")

        # ---- Phase 2: reconcile every claim through the real analyzer + Commander ----
        results = claim_status.reconcile_all_claims(db)
        print(f"Phase 2: reconciled {len(results)} claims through the real analyzer + Commander.\n")

        print_distribution(results)

        violations = claim_status.check_invariants(results)
        if violations:
            print("\nINVARIANT VIOLATIONS:")
            for v in violations:
                print(f"  - {v}")
            sys.exit(1)
        print("\nAll status/risk invariants hold.")
    finally:
        db.close()


def print_distribution(results: list[claim_status.ReconcileResult]) -> None:
    total = len(results)
    by_risk = Counter(r.risk_level for r in results)
    by_status = Counter(r.status_after for r in results)
    with_issues = sum(1 for r in results if r.issue_count)
    repaired = [r for r in results if r.repaired]

    print(f"Total claims: {total}")
    print(f"With >=1 open issue: {with_issues}   |   Clean: {total - with_issues}")

    print("\nRisk level:")
    for lvl in ("High", "Medium", "Low"):
        print(f"  {lvl:<7} {by_risk.get(lvl, 0):>3}")

    print("\nStatus:")
    for st, n in by_status.most_common():
        print(f"  {st:<14} {n:>3}")

    print("\nInternal-judgment statuses vs. analysis (must all match):")
    for r in results:
        if r.status_after in claim_status.INTERNAL_JUDGMENT_STATUSES:
            print(
                f"  {r.claim_id}  {r.status_after:<13} "
                f"risk={r.risk_level:<7} score={r.risk_score:>3} issues={r.issue_count}"
            )

    denied = [r for r in results if r.status_after == "Denied"]
    paid = [r for r in results if r.status_after == "Paid"]
    print(f"\nTerminal claims — Denied: {len(denied)}, Paid: {len(paid)}")
    for r in denied:
        note = r.documented_divergence or "matches internal risk"
        print(
            f"  {r.claim_id}  Denied  risk={r.risk_level:<7} score={r.risk_score:>3} "
            f"issues={r.issue_count}  ({note})"
        )
    for r in paid:
        print(f"  {r.claim_id}  Paid    risk={r.risk_level:<7} score={r.risk_score:>3} issues={r.issue_count}")

    if repaired:
        print(f"\nRepaired {len(repaired)} incoherent row(s) this run:")
        for r in repaired:
            print(f"  {r.claim_id}: {r.status_before!r} -> {r.status_after!r} "
                  f"(risk={r.risk_level}, issues={r.issue_count})")


if __name__ == "__main__":
    seed()
