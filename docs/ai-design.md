# AI Design

## Goal
Provide explainable claim recommendations using a human-in-the-loop workflow. The AI layer highlights likely issues, summarizes evidence, and flags uncertainty without making operational decisions without approval.

## Architecture: Commander-orchestrated agent system

The AI layer is not a single AI service call, and it is not a LangGraph node-graph. It is a **Commander pattern**: a pure decision node that routes claim events to numbered specialist agents, each of which does one job and returns control.

### 00-commander
A pure decision node — no tools, no content generation. It reads the claim's current state plus the triggering event and returns a routing decision by walking an **ordered rule table, terminal guards first**. Terminal guards (e.g. "claim already has a human-approved action pending," "claim is closed") are checked before any routing rule that would dispatch to a specialist agent, so Commander can short-circuit to "no action" without ever invoking a downstream agent. Because Commander does not generate content or call tools itself, its behavior is fully auditable from the rule table alone.

### Specialist agents (Commander-routed)
- **01-analyzer-agent** — reads a claim plus its evidence fields and calls the deterministic rule engine (see [`docs/architecture.md`](./architecture.md)) to produce the canonical list of `Issue`s and the `risk_score`/`risk_level`. Grounds everything downstream in deterministic output before any LLM reasoning happens.
- **02-reasoning-agent** — takes the Analyzer's issues and claim context and explains why each issue matters, how issues interact, and what's uncertain or missing evidence for.
- **03-recommendation-agent** — turns the Reasoning Agent's output into a small set of concrete next-step options with a stated rationale per option. Does not execute anything.
- **04–06** — reserved for Phase 6. Not built yet; Commander's rule table has no routes to these numbers until then.
- **07-assistant-agent** — the tool-calling conversational agent exposed through the AI Assistant UI. Can call the same tools (rule engine, claim lookup, dashboard metrics) on demand to answer ad-hoc operator questions, under the same guardrails as the routed agents.

### Where the agents run
Whether these agents execute inside a Python orchestrator or as n8n workflow nodes is an open Phase 4 decision, not yet made. `langgraph`/`langchain-anthropic` are only installed if we choose the Python-orchestrator path — there is no LangGraph dependency in this design.

## Guardrails
- No real PHI or production data — synthetic-only reference data and sample claims.
- The deterministic rule engine is the source of truth for risk scoring; agents reason about and explain its output, they do not override or recompute it.
- Every agent output is a recommendation. Final actions require explicit human authorization — no agent, including Commander, is permitted to call an action-taking tool directly.
- Agent outputs must carry their evidence (which rule issues, which claim fields) so a reviewer can verify the recommendation without trusting the model.

## Status
This is the Phase 4 build target. As of this document's last update, `/api/ai` and the AI Assistant UI are placeholders — Commander and the specialist agents are not wired up yet, and the orchestration runtime (Python vs. n8n) has not been decided.
