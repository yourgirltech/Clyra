"""03-recommendation-agent — turns 02's explanation into a concrete,
actionable recommendation (docs/agents/03-recommendation-agent.md).

Last stop before a human is asked to approve or decline something — it
proposes, it never executes. Receives 02-reasoning-agent's explanation
output plus the underlying Issue list/risk_score/risk_level (passed through
for traceability, not recomputed). Calls the Claude API once to produce a
primary action_type, a rationale that cites specific issues, optional
secondary options, and a confidence band.

Treated with the same scrutiny as 02: the model's rationale is checked for
invented issue citations the same way 02's explanations are, and — the one
rule this agent must never be allowed to break — a Low-confidence result is
never silently upgraded. This module always reports the confidence the model
actually gave; whether a Low result gets shown to a human as an approval
card or routed to escalation is Commander's decision (rules 12/13), not
this agent's.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Literal, Optional, Union

import anthropic
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.risk_rules import Issue

MODEL = "claude-opus-5"

ACTION_TYPES = ("follow_up", "payer_reminder", "manual_review_needed", "no_action_needed")
CONFIDENCE_BANDS = ("High", "Medium", "Low")

INSUFFICIENT_BASIS_RATIONALE = "insufficient basis for a recommendation"

SYSTEM_PROMPT = """You are the recommendation layer of Clyra, a healthcare claims operations \
assistant. You have been given 02-reasoning-agent's plain-language explanation of one claim's \
deterministic rule-engine findings: per-issue explanations, cross-issue notes, uncertainty \
notes, and a summary — plus the underlying Issue list, risk_score, and risk_level.

Your only job is to turn that explanation into ONE concrete primary recommendation (optionally \
with secondary options), each with an action_type, a rationale, and a confidence band. You do \
not execute anything, contact anyone, or change any claim status — you only propose.

action_type must be exactly one of these four values, nothing else:
- "follow_up" — an internal follow-up task is warranted.
- "payer_reminder" — a reminder/inquiry to the payer is warranted.
- "manual_review_needed" — a human needs to look at this claim directly; none of the other \
  categories fit cleanly.
- "no_action_needed" — nothing further is warranted right now (e.g. no issues were found).

Every rationale must cite the specific issue_type(s) that drove it — copied exactly from the \
Issue list you were given, in the cited_issue_types field. If there are no issues (a clean \
claim), cited_issue_types may be empty and action_type should normally be "no_action_needed".

confidence is your honest assessment, as High, Medium, or Low:
- Use High or Medium whenever you can form an actual recommendation from what you were given.
- Use Low when the explanation is too thin, contradictory, or ambiguous to responsibly commit \
  to a specific action. When you do this, set rationale to exactly the string \
  "insufficient basis for a recommendation" — do not dress up a guess as a confident answer. \
  You are explicitly allowed to say you're not sure; a Low-confidence recommendation is never \
  shown to a human as a one-click approval, so there is no cost to being honest about doubt.

Never invent an issue_type that was not in the Issue list you were given. Never invent an \
action_type outside the four listed above — if nothing else fits, use "manual_review_needed" \
or "no_action_needed" rather than stretching a category to fit."""


class RecommendationOption(BaseModel):
    action_type: Literal["follow_up", "payer_reminder", "manual_review_needed", "no_action_needed"]
    rationale: str
    cited_issue_types: List[str] = Field(default_factory=list)
    confidence: Literal["High", "Medium", "Low"]


class RecommendationOutput(BaseModel):
    primary: RecommendationOption
    secondary_options: List[RecommendationOption] = Field(default_factory=list)


@dataclass(frozen=True)
class RecommendationResult:
    claim_id: str
    action_type: str
    rationale: str
    cited_issue_types: List[str]
    confidence: str  # "High" | "Medium" | "Low"
    low_confidence: bool
    secondary_options: List[dict]
    raw_model_response: str  # full structured output, for audit/display


@dataclass(frozen=True)
class RecommendationFailure:
    claim_id: Optional[str]
    reason: str  # "malformed_input" | "ungrounded_output" | "llm_call_failed"
    detail: str


def _validate_input(
    claim_id, issues, risk_score, risk_level,
    reasoning_issue_explanations, reasoning_summary,
) -> Optional[str]:
    """Return an error message if the input is malformed/inconsistent, else None."""
    if not isinstance(claim_id, str) or not claim_id:
        return "claim_id is missing or invalid"
    if not isinstance(issues, list):
        return "issues must be a list"
    for issue in issues:
        if not getattr(issue, "issue_type", None):
            return f"issue is missing issue_type: {issue!r}"
    if not isinstance(risk_score, int) or isinstance(risk_score, bool) or not (0 <= risk_score <= 100):
        return f"risk_score is missing or out of range: {risk_score!r}"
    if risk_level not in ("Low", "Medium", "High"):
        return f"risk_level is missing or invalid: {risk_level!r}"
    if not isinstance(reasoning_issue_explanations, dict):
        return "reasoning_issue_explanations must be a dict"
    if not isinstance(reasoning_summary, str) or not reasoning_summary.strip():
        return "reasoning_summary is missing or empty"
    return None


def _default_client() -> anthropic.Anthropic:
    settings = get_settings()
    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return anthropic.Anthropic()  # falls back to the SDK's own env resolution


def _to_result(claim_id: str, parsed: RecommendationOutput) -> RecommendationResult:
    primary = parsed.primary
    return RecommendationResult(
        claim_id=claim_id,
        action_type=primary.action_type,
        rationale=primary.rationale,
        cited_issue_types=list(primary.cited_issue_types),
        confidence=primary.confidence,
        low_confidence=(primary.confidence == "Low"),
        secondary_options=[opt.model_dump() for opt in parsed.secondary_options],
        raw_model_response=parsed.model_dump_json(indent=2),
    )


def run_recommendation(
    claim_id: str,
    issues: List[Issue],
    risk_score: int,
    risk_level: str,
    reasoning_issue_explanations: dict,
    reasoning_cross_issue_notes: str,
    reasoning_uncertainty_notes: str,
    reasoning_summary: str,
    *,
    client: Optional[anthropic.Anthropic] = None,
) -> Union[RecommendationResult, RecommendationFailure]:
    """Produce one primary recommendation (+ optional secondary options) from
    02-reasoning-agent's output.

    A recommendation the model isn't confident in is still a *success* —
    `low_confidence=True` with rationale "insufficient basis for a
    recommendation" — never a `RecommendationFailure`. This function never
    overrides or upgrades the confidence the model reports; the low/high
    routing gate lives entirely in Commander (rules 12/13), not here.

    Malformed/inconsistent input, or a model response that cites an
    issue_type outside what it was given, returns a `RecommendationFailure`
    instead of raising — the caller (Commander, via a `recommendation_failed`
    trigger) routes that to escalation, per rule 11.
    """
    error = _validate_input(
        claim_id, issues, risk_score, risk_level,
        reasoning_issue_explanations, reasoning_summary,
    )
    if error:
        return RecommendationFailure(
            claim_id=claim_id if isinstance(claim_id, str) else None,
            reason="malformed_input",
            detail=error,
        )

    issue_payload = [
        {"issue_type": issue.issue_type, "severity": issue.severity, "description": issue.description}
        for issue in issues
    ]
    user_content = (
        f"risk_score: {risk_score}\n"
        f"risk_level: {risk_level}\n\n"
        "Issues (deterministic rule engine output — the only issues that exist for this claim):\n"
        f"{json.dumps(issue_payload, default=str, indent=2)}\n\n"
        "02-reasoning-agent's explanation:\n"
        f"per-issue explanations: {json.dumps(reasoning_issue_explanations, default=str, indent=2)}\n"
        f"cross-issue notes: {reasoning_cross_issue_notes or '(none)'}\n"
        f"uncertainty notes: {reasoning_uncertainty_notes or '(none)'}\n"
        f"summary: {reasoning_summary}"
    )

    active_client = client or _default_client()

    try:
        response = active_client.messages.parse(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            output_format=RecommendationOutput,
        )
    except Exception as exc:  # anthropic.APIError and friends — never crash the pipeline
        return RecommendationFailure(claim_id=claim_id, reason="llm_call_failed", detail=str(exc))

    parsed = response.parsed_output
    if parsed is None:
        return RecommendationFailure(
            claim_id=claim_id, reason="llm_call_failed", detail="model did not return parseable output"
        )

    given_issue_types = {issue.issue_type for issue in issues}
    all_options = [parsed.primary, *parsed.secondary_options]
    ungrounded = {t for opt in all_options for t in opt.cited_issue_types} - given_issue_types
    if ungrounded:
        return RecommendationFailure(
            claim_id=claim_id,
            reason="ungrounded_output",
            detail=f"model cited issue_type(s) not in the input: {sorted(ungrounded)}",
        )

    return _to_result(claim_id, parsed)
