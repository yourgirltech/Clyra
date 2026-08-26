"""Ties Commander's routing decision to real agent execution.

Commander (`app.agents.commander.commander_route`) only decides *whether* the
pipeline continues and *which* agent runs next — it never calls one. This
module is the thin seam that does: given a routing decision, either run the
one real agent that exists (01-analyzer-agent) or fall back to
`dispatch_stub` for every agent that isn't built yet.

Build step 2: only 01-analyzer-agent is real. Extending this to 02+ is just
adding another `if decision.decision == AGENT_X` branch here — Commander and
each agent's own module stay untouched.
"""

from __future__ import annotations

from typing import Any

from app.agents.analyzer import AnalyzerResult, run_analyzer
from app.agents.commander import (
    AGENT_ANALYZER,
    NO_ACTION,
    CommanderDecision,
    commander_route,
    dispatch_stub,
)


def route_and_dispatch(
    claim_state: dict | None,
    trigger: dict | None,
    *,
    claim_evidence: dict | None = None,
    payer_config: dict | None = None,
    follow_ups: list[dict] | None = None,
) -> tuple[CommanderDecision, AnalyzerResult | str | None]:
    """Run Commander's routing, then actually execute it.

    Returns `(decision, result)`:
    - If Commander routes to 01-analyzer-agent, `result` is a real
      `AnalyzerResult` computed from `claim_evidence`/`payer_config`/
      `follow_ups` (required in that case — raises if omitted).
    - If Commander routes to `no_action`, `result` is `None`.
    - For every other agent (02-06), `result` is still `dispatch_stub`'s
      placeholder string — those agents aren't built yet.
    """
    decision = commander_route(claim_state, trigger)

    if decision.decision == AGENT_ANALYZER:
        if claim_evidence is None or payer_config is None:
            raise ValueError(
                "claim_evidence and payer_config are required to run 01-analyzer-agent"
            )
        claim_id = claim_state.get("claim_id") if claim_state else None
        result = run_analyzer(claim_id, claim_evidence, payer_config, follow_ups or [])
        return decision, result

    if decision.decision == NO_ACTION:
        return decision, None

    return decision, dispatch_stub(decision.decision)
