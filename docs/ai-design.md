# AI Design

## Goal
Provide explainable claim recommendations using a human-in-the-loop workflow. The AI layer highlights likely issues, summarizes evidence, and flags uncertainty without making operational decisions without approval.

## Architecture: LangGraph multi-agent pipeline

The AI layer is a LangGraph graph of cooperating agents, not a single AI service call. Each agent has a narrow responsibility and hands structured state to the next node in the graph.

- **Analyzer Agent** — reads a claim plus its evidence fields and calls the deterministic rule engine (see [`docs/architecture.md`](./architecture.md)) as a tool to produce the canonical list of `Issue`s and the `risk_score`/`risk_level`. This agent does not invent findings; it grounds the graph in deterministic output before any LLM reasoning happens.
- **Reasoning Agent** — takes the Analyzer's issues and claim context and produces an explanation: why each issue matters, how issues interact (e.g. missing authorization *and* an overdue follow-up compounding risk), and what's uncertain or missing evidence for.
- **Recommendation Agent** — turns the Reasoning Agent's output into a small set of concrete next-step options (e.g. "request documentation from provider," "escalate to payer follow-up," "flag for manual review") with a stated rationale per option. It does not execute anything.
- **Assistant Agent** — a tool-calling conversational agent exposed through the AI Assistant UI. It can call the same tools (rule engine, claim lookup, dashboard metrics) on demand to answer ad-hoc operator questions, but shares the same guardrails as the pipeline above.

## Guardrails
- No real PHI or production data — synthetic-only reference data and sample claims.
- The deterministic rule engine is the source of truth for risk scoring; LLM agents reason about and explain its output, they do not override or recompute it.
- Every agent output is a recommendation. Final actions require explicit human authorization — no agent in this graph is permitted to call an action-taking tool (e.g. downstream automations) directly.
- Agent outputs must carry their evidence (which rule issues, which claim fields) so a reviewer can verify the recommendation without trusting the model.

## Status
This graph is the Phase 4 build target. As of this document's last update, `/api/ai` and the AI Assistant UI are placeholders — no agents are wired up yet.
