# AI Design

## Goal
Provide explainable claim recommendations using a human-in-the-loop workflow. The AI layer highlights likely issues, summarizes evidence, and flags uncertainty without making operational decisions without approval.

## Architecture: Commander-orchestrated agent system

The AI layer is not a single AI service call, and it is not a LangGraph node-graph. It is a **Commander pattern**: a pure decision node that routes claim events to numbered specialist agents, each of which does one job and returns control.

The full per-agent plan (role, triggers, inputs/outputs, failure handling) lives in [`docs/agents/`](./agents/): [00-commander](./agents/00-commander.md), [01-analyzer](./agents/01-analyzer-agent.md), [02-reasoning](./agents/02-reasoning-agent.md), [03-recommendation](./agents/03-recommendation-agent.md), [04-followup](./agents/04-followup-agent.md), [05-reminder](./agents/05-reminder-agent.md), [06-escalation](./agents/06-escalation-agent.md), [07-assistant](./agents/07-assistant-agent.md). This section is a summary of that roadmap, not the source of truth for it — if the two ever disagree, `docs/agents/` wins.

### 00-commander
A pure decision node — no tools, no content generation. It reads the claim's current state plus the triggering event and returns a routing decision by walking an **ordered rule table, terminal guards first**. Terminal guards (e.g. "claim already has a human-approved action pending," "claim is closed") are checked before any routing rule that would dispatch to a specialist agent, so Commander can short-circuit to "no action" without ever invoking a downstream agent. Because Commander does not generate content or call tools itself, its behavior is fully auditable from the rule table alone.

### Specialist agents (Commander-routed)
- **01-analyzer-agent** — reads a claim plus its evidence fields and calls the deterministic rule engine (see [`docs/architecture.md`](./architecture.md)) to produce the canonical list of `Issue`s and the `risk_score`/`risk_level`. Grounds everything downstream in deterministic output before any LLM reasoning happens.
- **02-reasoning-agent** — takes the Analyzer's issues and claim context and explains why each issue matters, how issues interact, and what's uncertain or missing evidence for.
- **03-recommendation-agent** — turns the Reasoning Agent's output into a small set of concrete next-step options with a stated rationale per option. Does not execute anything.
- **04-followup-agent** / **05-reminder-agent** — execute a human-approved follow-up or payer-reminder action. Implemented as plain Python functions, same pattern as the other agents — no n8n, no real external delivery. Synthetic-data demo: "executing" means simulating the action and creating a real, durable record (`FollowUp`/`PayerReminder` + `ActivityLog`), not contacting anyone. A small bounded retry with backoff handles simulated transient failures; a non-transient failure (missing fields, revoked approval) never retries and escalates immediately via rules 17/18.
- **06-escalation-agent** — the safety net for every failure/uncertainty path (deterministic engine error, an agent erroring out, a low-confidence recommendation, a failed follow-up/reminder execution, an unrecognized event). It's the target of most of Commander's non-happy-path rules from day one; rules 17/18 (a failed follow-up/reminder execution) only became genuinely reachable once 04/05 existed to actually emit those failures.
- **07-assistant-agent** — the tool-calling conversational agent exposed through the AI Assistant UI. Can call the same tools (rule engine, claim lookup, dashboard metrics) on demand to answer ad-hoc operator questions, under the same guardrails as the routed agents.

### Where the agents run
Whether these agents execute inside a Python orchestrator or as n8n workflow nodes is an open Phase 4 decision, not yet made. `langgraph`/`langchain-anthropic` are only installed if we choose the Python-orchestrator path — there is no LangGraph dependency in this design.

## Guardrails
- No real PHI or production data — synthetic-only reference data and sample claims.
- The deterministic rule engine is the source of truth for risk scoring; agents reason about and explain its output, they do not override or recompute it.
- Every agent output is a recommendation. Final actions require explicit human authorization — no agent, including Commander, is permitted to call an action-taking tool directly.
- Agent outputs must carry their evidence (which rule issues, which claim fields) so a reviewer can verify the recommendation without trusting the model.

## Status
Orchestration runtime: Python, `backend/app/agents/`. All seven agents are implemented and wired end to end via `dispatch.py`: 01-analyzer (deterministic, no LLM); 02-reasoning/03-recommendation (Claude API, structured output, grounded against their inputs); 04-followup/05-reminder (plain Python, simulated execution against real `FollowUp`/`PayerReminder` records, bounded transient-retry-with-backoff); 06-escalation (durable persistence, no LLM) is the real target of every non-happy-path rule, including a failed 04/05 execution (rules 17/18); 07-assistant is the tool-calling chat agent behind the AI Assistant UI, invoked directly by `POST /api/ai/assistant`, outside Commander's routing table by design. The AI Assistant chat UI and the full claim-lifecycle pipeline (analyze → reason → recommend → human approval → execute) are live end to end — no placeholders left. See each file in [`docs/agents/`](./agents/) for per-agent status.
