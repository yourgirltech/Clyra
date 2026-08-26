"""07-assistant-agent — the tool-calling conversational agent behind the AI
Assistant chat UI (docs/agents/07-assistant-agent.md).

Sits OUTSIDE Commander's rule table on purpose: it isn't reacting to a claim
lifecycle event, it's reacting to a human typing a question, and a single
session may span multiple claims or none at all. It is invoked directly by
the chat endpoint, never via `app.agents.dispatch.route_and_dispatch` — this
module has no dependency on commander.py, dispatch.py, or escalation.py.

Guardrails, enforced structurally rather than by prompt alone:
- No tool defined here can write anything. There is no "send", "approve", or
  "execute" tool at all — an agent literally cannot take an action it has no
  tool for, regardless of how the user phrases the request.
- Every claim_id-shaped token in the final answer must have actually come
  back from a tool call made during this turn; anything else is treated as
  ungrounded output and rejected, the same discipline 02/03 apply to their
  own structured output.
- A tool-call/API failure or a "here's what I don't know" answer is reported
  directly in the chat text — this agent never calls 06-escalation-agent.
  Escalation is for claim-lifecycle automation failures; a person asking a
  question that can't be answered isn't one of those.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional, Union

import anthropic

from app import models
from app.agents.analyzer import run_analyzer
from app.core.config import get_settings

MODEL = "claude-opus-5"
MAX_TOOL_ITERATIONS = 6

_CLAIM_ID_PATTERN = re.compile(r"\bCL-\d+\b")

SYSTEM_PROMPT = """You are the Clyra AI Assistant, answering a claims operations user's \
questions about their clinic's insurance claims.

You have exactly five read-only tools. You have NO way to change, approve, send, or execute \
anything — there is no tool for that, on purpose. If the user asks you to take an action \
("go ahead and send it", "approve this", "mark it reviewed", "create the follow-up"), you must \
explain that you can't do that and point them to the claim detail page, where a human approves \
the action — you never pretend to have done it, and you never treat the phrasing as a reason to \
guess at what a tool might do.

Ground every factual claim in an actual tool call you made this turn. Never state a claim_id, \
status, amount, or risk figure you did not just look up. If you don't have enough information to \
answer — a tool didn't return what you needed, or the question is outside what your tools can \
see — say so plainly. Do not fill the gap with a plausible-sounding guess, and do not treat \
"I don't know" as a failure that needs escalating anywhere; just answer honestly in the chat.

Claim lookups (get_claim, analyze_claim) work on any claim regardless of its status, including \
terminal claims like Paid or Denied — read-only lookup is fine there even though no automated \
action would ever run against them.

Keep answers concise and cite what you found (e.g. "CL-10002 is High risk, $3,826.33, missing \
authorization") rather than vague summaries."""


TOOL_DEFS = [
    {
        "name": "get_claim",
        "description": (
            "Look up one claim by its claim_id. Works for any claim including terminal "
            "statuses (Paid, Denied, Rejected, Withdrawn, Closed) — read-only lookup only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "description": "The claim's claim_id, e.g. 'CL-10002'."},
            },
            "required": ["claim_id"],
        },
    },
    {
        "name": "get_claims_by_risk",
        "description": "List claims at a given risk level, highest risk_score first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["Low", "Medium", "High"]},
            },
            "required": ["level"],
        },
    },
    {
        "name": "get_overdue_claims",
        "description": (
            "List claims the deterministic rule engine has flagged as overdue for follow-up."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_claims_by_payer",
        "description": "List claims for a payer, matched by name (case-insensitive, partial match OK).",
        "input_schema": {
            "type": "object",
            "properties": {
                "payer": {"type": "string", "description": "Payer name or partial name, e.g. 'Example Health'."},
            },
            "required": ["payer"],
        },
    },
    {
        "name": "analyze_claim",
        "description": (
            "Run the deterministic rule engine for one claim and return its issues, risk_score, "
            "and risk_level. Read-only — does not persist anything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "description": "The claim's claim_id, e.g. 'CL-10002'."},
            },
            "required": ["claim_id"],
        },
    },
]


@dataclass(frozen=True)
class AssistantTurn:
    reply: str
    tool_calls: List[dict]  # [{"tool": name, "input": {...}, "result": {...}}, ...]


@dataclass(frozen=True)
class AssistantFailure:
    reason: str  # "ungrounded_output" | "llm_call_failed"
    detail: str


def _claim_brief(claim: models.Claim) -> dict:
    return {
        "claim_id": claim.claim_id,
        "status": claim.status,
        "risk_level": claim.risk_level,
        "risk_score": claim.risk_score,
        "amount": float(claim.amount),
        "payer": getattr(claim.payer, "name", None),
    }


def _execute_tool(db, clinic_id: int, name: str, tool_input: dict, call_log: list, seen_claim_ids: set) -> dict:
    if name == "get_claim":
        claim_id = tool_input.get("claim_id", "")
        # A looked-up-but-not-found claim_id still counts as grounded — the
        # model asked about it and got a real answer ("doesn't exist"), it
        # didn't invent it.
        seen_claim_ids.add(claim_id)
        claim = (
            db.query(models.Claim)
            .filter(models.Claim.claim_id == claim_id, models.Claim.clinic_id == clinic_id)
            .first()
        )
        if not claim:
            result = {"found": False, "claim_id": claim_id}
        else:
            result = {
                "found": True,
                **_claim_brief(claim),
                "patient": (
                    f"{getattr(claim.patient, 'first_name', '')} {getattr(claim.patient, 'last_name', '')}".strip()
                    or None
                ),
                "created_at": str(claim.created_at),
            }

    elif name == "get_claims_by_risk":
        level = tool_input.get("level", "")
        claims = (
            db.query(models.Claim)
            .filter(models.Claim.clinic_id == clinic_id, models.Claim.risk_level == level)
            .order_by(models.Claim.risk_score.desc())
            .limit(25)
            .all()
        )
        for c in claims:
            seen_claim_ids.add(c.claim_id)
        result = {"level": level, "count": len(claims), "claims": [_claim_brief(c) for c in claims]}

    elif name == "get_overdue_claims":
        claims = (
            db.query(models.Claim)
            .join(models.ClaimIssue, models.ClaimIssue.claim_id == models.Claim.id)
            .filter(models.Claim.clinic_id == clinic_id, models.ClaimIssue.issue_type == "overdue_follow_up")
            .distinct()
            .limit(25)
            .all()
        )
        for c in claims:
            seen_claim_ids.add(c.claim_id)
        result = {"count": len(claims), "claims": [_claim_brief(c) for c in claims]}

    elif name == "get_claims_by_payer":
        payer_query = tool_input.get("payer", "")
        claims = (
            db.query(models.Claim)
            .join(models.Payer, models.Payer.id == models.Claim.payer_id)
            .filter(models.Claim.clinic_id == clinic_id, models.Payer.name.ilike(f"%{payer_query}%"))
            .limit(25)
            .all()
        )
        for c in claims:
            seen_claim_ids.add(c.claim_id)
        result = {"payer_query": payer_query, "count": len(claims), "claims": [_claim_brief(c) for c in claims]}

    elif name == "analyze_claim":
        claim_id = tool_input.get("claim_id", "")
        seen_claim_ids.add(claim_id)
        claim = (
            db.query(models.Claim)
            .filter(models.Claim.claim_id == claim_id, models.Claim.clinic_id == clinic_id)
            .first()
        )
        if not claim:
            result = {"found": False, "claim_id": claim_id}
        else:
            payer = claim.payer
            follow_ups = db.query(models.FollowUp).filter(models.FollowUp.claim_id == claim.id).all()
            claim_evidence = {
                "authorization_present": int(claim.authorization_present),
                "documentation_present": int(claim.documentation_present),
                "coding_matches": int(claim.coding_matches),
                "last_followup_at": claim.last_followup_at,
            }
            payer_config = {
                "authorization_required": int(getattr(payer, "authorization_required", 0)),
                "documentation_required": int(getattr(payer, "documentation_required", 0)),
                "follow_up_threshold_days": int(getattr(payer, "follow_up_threshold_days", 30)),
            }
            analysis = run_analyzer(
                claim.claim_id, claim_evidence, payer_config, [{"due_at": f.due_at} for f in follow_ups]
            )
            result = {
                "found": True,
                "claim_id": analysis.claim_id,
                "risk_score": analysis.risk_score,
                "risk_level": analysis.risk_level,
                "issues": [
                    {"issue_type": i.issue_type, "severity": i.severity, "description": i.description}
                    for i in analysis.issues
                ],
            }

    else:
        result = {"error": f"unknown tool '{name}'"}

    call_log.append({"tool": name, "input": tool_input, "result": result})
    return result


def _default_client() -> anthropic.Anthropic:
    settings = get_settings()
    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return anthropic.Anthropic()


def run_assistant(
    db,
    clinic_id: int,
    message: str,
    history: Optional[List[dict]] = None,
    *,
    client: Optional[anthropic.Anthropic] = None,
) -> Union[AssistantTurn, AssistantFailure]:
    """Answer one chat message, calling tools as needed. Stateless: the full
    conversation history is passed in and returned to the caller to persist
    (this module holds no session state of its own).

    Never raises for a normal LLM/tool-use failure — reports back an
    `AssistantFailure` instead, which the API layer surfaces as a plain chat
    message, not an escalation.
    """
    messages = list(history or []) + [{"role": "user", "content": message}]
    call_log: list = []
    seen_claim_ids: set = set()
    active_client = client or _default_client()

    response = None
    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            response = active_client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFS,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                break

            tool_use_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in tool_use_blocks:
                result = _execute_tool(db, clinic_id, block.name, block.input, call_log, seen_claim_ids)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, default=str)}
                )
            messages.append({"role": "user", "content": tool_results})
        else:
            return AssistantFailure(
                reason="llm_call_failed",
                detail=f"exceeded {MAX_TOOL_ITERATIONS} tool-call iterations without a final answer",
            )
    except Exception as exc:  # anthropic.APIError and friends — never crash the chat endpoint
        return AssistantFailure(reason="llm_call_failed", detail=str(exc))

    if response is None:
        return AssistantFailure(reason="llm_call_failed", detail="model returned no response")

    reply_text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()
    if not reply_text:
        return AssistantFailure(reason="llm_call_failed", detail="model returned no text content")

    mentioned = set(_CLAIM_ID_PATTERN.findall(reply_text))
    ungrounded = mentioned - seen_claim_ids
    if ungrounded:
        return AssistantFailure(
            reason="ungrounded_output",
            detail=f"response mentions claim_id(s) never looked up via a tool call this turn: {sorted(ungrounded)}",
        )

    return AssistantTurn(reply=reply_text, tool_calls=call_log)
