"""Claim status <-> computed risk coherence.

Clyra owns two kinds of claim status:

* **Internal-judgment statuses** ("At Risk", "Needs Review") are produced BY our
  own rule engine / analyzer. They must never disagree with a fresh analysis:
  if a claim is "At Risk" it has to genuinely carry High computed risk, and if
  it is "Needs Review" it has to carry at least one open issue. A divergence
  here is always a bug, not a business fact.

* **Terminal statuses** ("Paid", "Denied") record an outcome that came from
  outside our four rule checks — a payer decision, an external review. "Denied"
  is therefore ALLOWED to diverge from our internal risk score (a claim can be
  denied for a reason we never measured, so `risk_score == 0` on a Denied claim
  is legitimate). "Paid" is held to a stricter bar in our synthetic dataset: a
  Paid claim must be internally coherent (no open issues), so a Paid row that
  analysis finds issues on is repaired back to an active status.

See docs/architecture.md, "Claim status and computed risk" for the rule this
module enforces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app import models
from app.agents.commander import commander_route
from app.services import risk_engine

# Active pipeline statuses that carry NO internal judgment — safe defaults for a
# clean, low-risk claim. Ordered by how far along the claim is.
STATUS_DRAFT = "Draft"
STATUS_SUBMITTED = "Submitted"
STATUS_PROCESSING = "Processing"

# Statuses that ARE our rule engine's judgment. Must match a fresh analysis.
STATUS_AT_RISK = "At Risk"
STATUS_NEEDS_REVIEW = "Needs Review"
INTERNAL_JUDGMENT_STATUSES = frozenset({STATUS_AT_RISK, STATUS_NEEDS_REVIEW})

# Terminal statuses — outcome set outside our rule checks.
STATUS_PAID = "Paid"
STATUS_DENIED = "Denied"
TERMINAL_STATUSES = frozenset({STATUS_PAID, STATUS_DENIED})


def derive_active_status(claim: models.Claim, *, has_issues: bool, risk_level: str) -> str:
    """The status a non-terminal claim MUST have, given a fresh analysis.

    High computed risk -> "At Risk". Any open issue -> at least "Needs Review".
    Genuinely clean and low-risk -> an active pipeline status chosen by age,
    never an internal-judgment one.
    """
    if risk_level == "High":
        return STATUS_AT_RISK
    if has_issues or risk_level == "Medium":
        return STATUS_NEEDS_REVIEW

    age_days = (datetime.utcnow() - claim.created_at).days if claim.created_at else 0
    if age_days > 45:
        return STATUS_PROCESSING
    if age_days > 10:
        return STATUS_SUBMITTED
    return STATUS_DRAFT


@dataclass
class ReconcileResult:
    claim_id: str
    status_before: str
    status_after: str
    risk_level: str
    risk_score: int
    issue_count: int
    # True when this row's status was changed to restore coherence.
    repaired: bool
    # Set for Denied claims whose status legitimately diverges from internal risk.
    documented_divergence: str | None
    # Commander's routing decision for a `claim_evidence_updated` trigger — a
    # cross-check that the real pipeline agrees with the derived status.
    commander_decision: str


def reconcile_claim(db: Session, claim: models.Claim) -> ReconcileResult:
    """Run the real analyzer over one claim, persist its issues/risk, then make
    the claim's status coherent with that result.

    - Non-terminal claim: status is overwritten with `derive_active_status`.
    - "Denied": left as-is; divergence from internal risk is expected and
      recorded in the result for the audit report.
    - "Paid": left as-is only if analysis is clean; a Paid row with open issues
      is incoherent in our synthetic model and is repaired to an active status.
    """
    status_before = claim.status

    issues = risk_engine.analyze_and_persist(db, claim)
    has_issues = len(issues) > 0

    documented_divergence: str | None = None

    if status_before == STATUS_DENIED:
        status_after = STATUS_DENIED
        if claim.risk_score == 0:
            documented_divergence = "denied_no_internal_risk"
        elif has_issues:
            documented_divergence = "denied_with_open_issues"
    elif status_before == STATUS_PAID and not has_issues:
        status_after = STATUS_PAID
    else:
        # Active claim, or an incoherent "Paid" row we are repairing.
        status_after = derive_active_status(
            claim, has_issues=has_issues, risk_level=claim.risk_level
        )

    repaired = status_after != status_before
    if repaired:
        claim.status = status_after
        db.add(claim)
        db.commit()

    claim_state = {
        "claim_id": claim.claim_id,
        "status": claim.status,
        "risk_score": claim.risk_score,
        "risk_level": claim.risk_level,
        "latest_issues": [{"issue_type": i.issue_type} for i in issues],
        "latest_recommendation": None,
        "agent_run_in_progress": False,
    }
    decision = commander_route(claim_state, {"type": "claim_evidence_updated", "payload": {}})

    return ReconcileResult(
        claim_id=claim.claim_id,
        status_before=status_before,
        status_after=claim.status,
        risk_level=claim.risk_level,
        risk_score=claim.risk_score,
        issue_count=len(issues),
        repaired=repaired,
        documented_divergence=documented_divergence,
        commander_decision=decision.decision,
    )


def reconcile_all_claims(db: Session) -> list[ReconcileResult]:
    """Reconcile every claim in the database. Safe to re-run — it is a pure
    function of each claim's evidence fields and payer config."""
    results = []
    for claim in db.query(models.Claim).order_by(models.Claim.claim_id).all():
        results.append(reconcile_claim(db, claim))
    return results


def check_invariants(results: list[ReconcileResult]) -> list[str]:
    """Return a list of invariant violations. Empty list == data is coherent."""
    violations: list[str] = []
    for r in results:
        if r.status_after == STATUS_AT_RISK and r.risk_level != "High":
            violations.append(
                f"{r.claim_id}: status 'At Risk' but risk_level={r.risk_level} (expected High)"
            )
        if r.status_after == STATUS_NEEDS_REVIEW and r.issue_count == 0:
            violations.append(
                f"{r.claim_id}: status 'Needs Review' but analysis found 0 issues"
            )
        if r.status_after in (STATUS_DRAFT, STATUS_SUBMITTED, STATUS_PROCESSING) and r.issue_count:
            violations.append(
                f"{r.claim_id}: active status '{r.status_after}' but analysis found "
                f"{r.issue_count} issue(s)"
            )
        if r.status_after == STATUS_PAID and r.issue_count:
            violations.append(
                f"{r.claim_id}: status 'Paid' but analysis found {r.issue_count} issue(s) "
                "(Paid must be internally coherent)"
            )
    return violations
