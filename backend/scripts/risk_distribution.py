"""Read-only report: the risk / status distribution of every claim currently in
the database, and any status<->analysis invariant violations.

Does NOT modify anything — safe to run against production. It reads the
persisted `claims` / `claim_issues` rows as they stand. To recompute and repair,
run `python scripts/seed_claims.py` instead.

Usage:  python scripts/risk_distribution.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from collections import Counter

from sqlalchemy import func

from app.db.database import SessionLocal
from app import models
from app.services.claim_status import (
    INTERNAL_JUDGMENT_STATUSES,
    STATUS_AT_RISK,
    STATUS_DRAFT,
    STATUS_NEEDS_REVIEW,
    STATUS_PAID,
    STATUS_PROCESSING,
    STATUS_SUBMITTED,
)

ACTIVE_CLEAN_STATUSES = {STATUS_DRAFT, STATUS_SUBMITTED, STATUS_PROCESSING}


def main() -> None:
    db = SessionLocal()
    try:
        claims = db.query(models.Claim).order_by(models.Claim.claim_id).all()
        issue_counts = dict(
            db.query(models.ClaimIssue.claim_id, func.count(models.ClaimIssue.id))
            .group_by(models.ClaimIssue.claim_id)
            .all()
        )

        total = len(claims)
        by_risk = Counter(c.risk_level for c in claims)
        by_status = Counter(c.status for c in claims)
        with_issues = sum(1 for c in claims if issue_counts.get(c.id, 0))

        print(f"Total claims: {total}")
        print(f"With >=1 open issue: {with_issues}   |   Clean: {total - with_issues}")

        print("\nRisk level:")
        for lvl in ("High", "Medium", "Low"):
            print(f"  {lvl:<7} {by_risk.get(lvl, 0):>3}")

        print("\nStatus:")
        for st, n in by_status.most_common():
            print(f"  {st:<14} {n:>3}")

        print("\nInternal-judgment statuses (At Risk / Needs Review) vs. persisted analysis:")
        for c in claims:
            if c.status in INTERNAL_JUDGMENT_STATUSES:
                n = issue_counts.get(c.id, 0)
                print(f"  {c.claim_id}  {c.status:<13} risk={c.risk_level:<7} score={c.risk_score:>3} issues={n}")

        violations = []
        for c in claims:
            n = issue_counts.get(c.id, 0)
            if c.status == STATUS_AT_RISK and c.risk_level != "High":
                violations.append(f"{c.claim_id}: 'At Risk' but risk_level={c.risk_level}")
            if c.status == STATUS_NEEDS_REVIEW and n == 0:
                violations.append(f"{c.claim_id}: 'Needs Review' but 0 issues persisted")
            if c.status in ACTIVE_CLEAN_STATUSES and n:
                violations.append(f"{c.claim_id}: active status '{c.status}' but {n} issue(s) persisted")
            if c.status == STATUS_PAID and n:
                violations.append(f"{c.claim_id}: 'Paid' but {n} issue(s) persisted")

        if violations:
            print(f"\n{len(violations)} INVARIANT VIOLATION(S) — run seed_claims.py to repair:")
            for v in violations:
                print(f"  - {v}")
            sys.exit(1)
        print("\nAll status/risk invariants hold.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
