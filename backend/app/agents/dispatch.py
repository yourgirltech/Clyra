"""Ties Commander's routing decision to real agent execution.

Commander (`app.agents.commander.commander_route`) only decides *whether* the
pipeline continues and *which* agent runs next — it never calls one. This
module is the thin seam that does: given a routing decision, either run a
real agent (01-analyzer-agent, 02-reasoning-agent, 03-recommendation-agent)
or fall back to `dispatch_stub` for every agent that isn't built yet.

Build step 4: 01, 02, and 03 are real. Extending this to 04+ is just adding
another `if decision.decision == AGENT_X` branch here — Commander and each
agent's own module stay untouched.
"""

from __future__ import annotations

import anthropic

from app.agents.analyzer import AnalyzerResult, run_analyzer
from app.agents.commander import (
    AGENT_ANALYZER,
    AGENT_REASONING,
    AGENT_RECOMMENDATION,
    NO_ACTION,
    CommanderDecision,
    commander_route,
    dispatch_stub,
)
from app.agents.reasoning import ReasoningFailure, ReasoningResult, run_reasoning
from app.agents.recommendation import (
    RecommendationFailure,
    RecommendationResult,
    run_recommendation,
)
from app.services.risk_rules import Issue


def route_and_dispatch(
    claim_state: dict | None,
    trigger: dict | None,
    *,
    claim_evidence: dict | None = None,
    payer_config: dict | None = None,
    follow_ups: list[dict] | None = None,
    reasoning_issues: list[Issue] | None = None,
    reasoning_risk_score: int | None = None,
    reasoning_risk_level: str | None = None,
    reasoning_claim_context: dict | None = None,
    recommendation_issues: list[Issue] | None = None,
    recommendation_risk_score: int | None = None,
    recommendation_risk_level: str | None = None,
    recommendation_reasoning: ReasoningResult | None = None,
    anthropic_client: anthropic.Anthropic | None = None,
) -> tuple[
    CommanderDecision,
    AnalyzerResult
    | ReasoningResult
    | ReasoningFailure
    | RecommendationResult
    | RecommendationFailure
    | str
    | None,
]:
    """Run Commander's routing, then actually execute it.

    Returns `(decision, result)`:
    - If Commander routes to 01-analyzer-agent (rule 6), `result` is a real
      `AnalyzerResult` computed from `claim_evidence`/`payer_config`/
      `follow_ups` (required in that case — raises if omitted).
    - If Commander routes to 02-reasoning-agent (rule 8), `result` is a real
      `ReasoningResult` or `ReasoningFailure` computed from
      `reasoning_issues`/`reasoning_risk_score`/`reasoning_risk_level`/
      `reasoning_claim_context` (required in that case — raises if omitted).
    - If Commander routes to 03-recommendation-agent (rule 10), `result` is a
      real `RecommendationResult` or `RecommendationFailure` computed from
      `recommendation_issues`/`recommendation_risk_score`/
      `recommendation_risk_level`/`recommendation_reasoning` — the last being
      a `ReasoningResult`, i.e. 02's own output (required in that case —
      raises if omitted).
      `anthropic_client` is passed through to whichever LLM agent runs, for
      injecting a test double; omit it to use the real Claude API.
    - If Commander routes to `no_action`, `result` is `None`.
    - For every other agent (04-06), `result` is still `dispatch_stub`'s
      placeholder string — those agents aren't built yet.
    """
    decision = commander_route(claim_state, trigger)
    claim_id = claim_state.get("claim_id") if claim_state else None

    if decision.decision == AGENT_ANALYZER:
        if claim_evidence is None or payer_config is None:
            raise ValueError(
                "claim_evidence and payer_config are required to run 01-analyzer-agent"
            )
        result = run_analyzer(claim_id, claim_evidence, payer_config, follow_ups or [])
        return decision, result

    if decision.decision == AGENT_REASONING:
        if (
            reasoning_issues is None
            or reasoning_risk_score is None
            or reasoning_risk_level is None
            or reasoning_claim_context is None
        ):
            raise ValueError(
                "reasoning_issues, reasoning_risk_score, reasoning_risk_level, and "
                "reasoning_claim_context are required to run 02-reasoning-agent"
            )
        result = run_reasoning(
            claim_id,
            reasoning_issues,
            reasoning_risk_score,
            reasoning_risk_level,
            reasoning_claim_context,
            client=anthropic_client,
        )
        return decision, result

    if decision.decision == AGENT_RECOMMENDATION:
        if (
            recommendation_issues is None
            or recommendation_risk_score is None
            or recommendation_risk_level is None
            or recommendation_reasoning is None
        ):
            raise ValueError(
                "recommendation_issues, recommendation_risk_score, recommendation_risk_level, "
                "and recommendation_reasoning are required to run 03-recommendation-agent"
            )
        result = run_recommendation(
            claim_id,
            recommendation_issues,
            recommendation_risk_score,
            recommendation_risk_level,
            recommendation_reasoning.issue_explanations,
            recommendation_reasoning.cross_issue_notes,
            recommendation_reasoning.uncertainty_notes,
            recommendation_reasoning.summary,
            client=anthropic_client,
        )
        return decision, result

    if decision.decision == NO_ACTION:
        return decision, None

    return decision, dispatch_stub(decision.decision)
