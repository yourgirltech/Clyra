"""02-reasoning-agent — the first place an LLM enters the pipeline
(docs/agents/02-reasoning-agent.md).

Explains the Analyzer's deterministic findings in plain language, grounded
strictly in what it's given: the Issue list (issue_type, severity,
description, evidence), risk_score/risk_level, and minimal claim context
(payer, amount, status, claim age). No tool access, no DB queries, no ability
to invent facts or look anything up. It does not decide what should happen
next — that is 03-recommendation-agent's job, not built yet.

Treated with more scrutiny than 01-analyzer-agent because it's the first
agent whose output isn't fully deterministic: every LLM response is
validated against the exact Issue list it was given before being trusted,
and anything that doesn't pass is a structured failure, not a best guess.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional, Union

import anthropic
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.risk_rules import Issue

MODEL = "claude-opus-5"

SYSTEM_PROMPT = """You are the reasoning layer of Clyra, a healthcare claims operations \
assistant. You have been given the exact output of a deterministic rule engine for one \
insurance claim: a list of Issues (each with an issue_type, severity, description, and \
evidence), the claim's risk_score and risk_level, and minimal claim context.

Your only job is to explain what these findings mean in plain language for a human claims \
reviewer, using exactly the four output fields described below — one job per field, nothing \
shared or duplicated between them:

- issue_explanations: ONE entry per Issue you were given, and NOTHING ELSE. Each entry's \
  issue_type must be copied exactly, character-for-character, from the Issue list — never a \
  field name, a category label, or anything you invented. Cross-issue commentary, uncertainty \
  notes, and your summary each have their OWN dedicated field below — never create a fake \
  issue_explanations entry to hold that content instead.
- cross_issue_notes: a single string. How issues interact where relevant (e.g. two issues \
  compounding risk together, not just adding up independently). Leave it as an empty string \
  if there's nothing meaningful to add — do not put this content in issue_explanations.
- uncertainty_notes: a single string. Say plainly when something is uncertain or the evidence \
  you were given is incomplete. Do not fill a gap with a plausible-sounding guess. Leave it as \
  an empty string if nothing is uncertain — do not put this content in issue_explanations.
- summary: a single string. A short overall summary tying the above together.

You must NOT:
- Invent, rename, or add an issue that is not in the Issue list you were given — even if \
  something else looks concerning, you have no way to verify anything not in the data you \
  were handed.
- Recommend an action or next step — that is a different system's job, not yours.
- Recompute or second-guess the risk_score or risk_level — treat them as given facts.
- Reference any information source other than what appears in this prompt."""


class IssueExplanation(BaseModel):
    issue_type: str = Field(
        description=(
            "Copied exactly, character-for-character, from an issue_type in the Issue list "
            "you were given. Never a field name like 'cross_issue_notes' or 'summary', never "
            "a category label, never anything not in that list."
        )
    )
    explanation: str = Field(description="What this one issue means in practice, and why it matters for this claim.")


class ReasoningOutput(BaseModel):
    issue_explanations: List[IssueExplanation] = Field(
        description=(
            "One entry per Issue in the Issue list you were given — nothing else. Cross-issue "
            "commentary, uncertainty notes, and the summary each belong in their own field "
            "below, never as an extra entry here."
        )
    )
    cross_issue_notes: str = Field(
        description=(
            "How the issues interact with each other, if at all. The only place this content "
            "belongs — never as an entry in issue_explanations. Empty string if nothing to add."
        )
    )
    uncertainty_notes: str = Field(
        description=(
            "What's uncertain or missing from the evidence you were given, if anything. Empty "
            "string if nothing is uncertain."
        )
    )
    summary: str = Field(description="A short overall summary tying the above together.")


@dataclass(frozen=True)
class ReasoningResult:
    claim_id: str
    issue_explanations: dict  # issue_type -> explanation text
    cross_issue_notes: str
    uncertainty_notes: str
    summary: str
    raw_model_response: str  # full structured-output JSON, for audit/display


@dataclass(frozen=True)
class ReasoningFailure:
    claim_id: Optional[str]
    reason: str  # "malformed_input" | "ungrounded_output" | "llm_call_failed"
    detail: str
    raw_model_response: str = ""  # populated for "ungrounded_output" — the exact response that failed


_REQUIRED_CLAIM_CONTEXT_FIELDS = ("payer", "amount", "status", "claim_age_days")


def _validate_input(claim_id, issues, risk_score, risk_level, claim_context) -> Optional[str]:
    """Return an error message if the input is malformed/inconsistent, else None."""
    if not isinstance(claim_id, str) or not claim_id:
        return "claim_id is missing or invalid"
    if not isinstance(issues, list):
        return "issues must be a list"
    for issue in issues:
        issue_type = getattr(issue, "issue_type", None)
        severity = getattr(issue, "severity", None)
        description = getattr(issue, "description", None)
        evidence = getattr(issue, "evidence", None)
        if not issue_type or not severity or not description:
            return f"issue is missing issue_type/severity/description: {issue!r}"
        if not isinstance(evidence, dict) or not evidence:
            return f"issue '{issue_type}' has no evidence attached"
    if not isinstance(risk_score, int) or isinstance(risk_score, bool) or not (0 <= risk_score <= 100):
        return f"risk_score is missing or out of range: {risk_score!r}"
    if risk_level not in ("Low", "Medium", "High"):
        return f"risk_level is missing or invalid: {risk_level!r}"
    if not isinstance(claim_context, dict):
        return "claim_context must be a dict"
    missing = [k for k in _REQUIRED_CLAIM_CONTEXT_FIELDS if k not in claim_context]
    if missing:
        return f"claim_context is missing required fields: {missing}"
    return None


def _default_client() -> anthropic.Anthropic:
    settings = get_settings()
    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return anthropic.Anthropic()  # falls back to the SDK's own env resolution


def run_reasoning(
    claim_id: str,
    issues: List[Issue],
    risk_score: int,
    risk_level: str,
    claim_context: dict,
    *,
    client: Optional[anthropic.Anthropic] = None,
) -> Union[ReasoningResult, ReasoningFailure]:
    """Explain one claim's deterministic findings in plain language.

    `issues` is the Analyzer's exact Issue list. `claim_context` must contain
    at least `payer`, `amount`, `status`, and `claim_age_days`. If the Issue
    list is empty, returns a trivial "no issues to explain" result without
    calling the model at all. If the input is malformed/inconsistent, or the
    model's response references an issue_type outside what it was given,
    returns a ReasoningFailure instead of raising — the caller (Commander,
    via a `reasoning_failed` trigger) routes that to escalation, per rule 9.
    """
    error = _validate_input(claim_id, issues, risk_score, risk_level, claim_context)
    if error:
        return ReasoningFailure(
            claim_id=claim_id if isinstance(claim_id, str) else None,
            reason="malformed_input",
            detail=error,
        )

    if not issues:
        return ReasoningResult(
            claim_id=claim_id,
            issue_explanations={},
            cross_issue_notes="",
            uncertainty_notes="",
            summary="No issues to explain.",
            raw_model_response="",
        )

    issue_payload = [
        {
            "issue_type": issue.issue_type,
            "severity": issue.severity,
            "description": issue.description,
            "evidence": issue.evidence,
        }
        for issue in issues
    ]
    user_content = (
        "Claim context:\n"
        f"{json.dumps(claim_context, default=str, indent=2)}\n\n"
        f"risk_score: {risk_score}\n"
        f"risk_level: {risk_level}\n\n"
        "Issues (deterministic rule engine output — the only issues that exist for this claim):\n"
        f"{json.dumps(issue_payload, default=str, indent=2)}"
    )

    active_client = client or _default_client()

    try:
        response = active_client.messages.parse(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            output_format=ReasoningOutput,
        )
    except Exception as exc:  # anthropic.APIError and friends — never crash the pipeline
        return ReasoningFailure(claim_id=claim_id, reason="llm_call_failed", detail=str(exc))

    parsed = response.parsed_output
    if parsed is None:
        return ReasoningFailure(
            claim_id=claim_id, reason="llm_call_failed", detail="model did not return parseable output"
        )

    given_issue_types = {issue.issue_type for issue in issues}
    returned_issue_types = {e.issue_type for e in parsed.issue_explanations}
    ungrounded = returned_issue_types - given_issue_types
    if ungrounded:
        return ReasoningFailure(
            claim_id=claim_id,
            reason="ungrounded_output",
            detail=f"model referenced issue_type(s) not in the input: {sorted(ungrounded)}",
            raw_model_response=parsed.model_dump_json(indent=2),
        )

    return ReasoningResult(
        claim_id=claim_id,
        issue_explanations={e.issue_type: e.explanation for e in parsed.issue_explanations},
        cross_issue_notes=parsed.cross_issue_notes,
        uncertainty_notes=parsed.uncertainty_notes,
        summary=parsed.summary,
        raw_model_response=parsed.model_dump_json(indent=2),
    )
