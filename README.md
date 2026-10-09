# Clyra

**An AI claims-operations assistant for U.S. healthcare billing teams.** Clyra finds the insurance claims that need attention, explains why, and recommends the next action. A human approves before anything is executed.

> **In production for a client.** The live system runs on the client's own domain and isn't linked here. This repository is the build record: the full source, with client data, credentials and URLs removed.
> Data in this repo is synthetic; no real PHI is included.

Billing staff at small and mid-sized clinics spend hours on delayed, denied and incomplete claims. They inspect records by hand, work out what went wrong and chase payers. Clyra answers three questions for every claim: **What needs my attention? Why? What should I do next?**

## How it works

```
claim event
  → 00 Commander: a pure rule table, terminal guards first, with no LLM and no tools
      → 01 Analyzer: deterministic rule engine → issues + risk_score / risk_level
      → 02 Reasoning (Claude): why each issue matters, how issues interact, what evidence is missing
      → 03 Recommendation (Claude): one primary action + optional alternatives, each with rationale and confidence
      → human review: approve / decline in the UI
      → 04 Follow-up / 05 Reminder: run only the approved action (bounded retry, durable records)
      → 06 Escalation: the safety net for every failure, low-confidence or unknown path
  07 Assistant: a tool-calling chat agent that answers ad-hoc questions with the same tools and guardrails
```

| Agent | Kind | Job |
|---|---|---|
| 00 Commander | deterministic | Routes events through an ordered, auditable rule table |
| 01 Analyzer | deterministic | Rule engine computes issues and risk, the single source of truth |
| 02 Reasoning | LLM (structured output) | Explains the analyzer's issues and never recomputes risk |
| 03 Recommendation | LLM (structured output) | Proposes actions with confidence and executes nothing |
| 04 Follow-up / 05 Reminder | deterministic | Runs human-approved actions only; non-transient failures never retry |
| 06 Escalation | deterministic | Catches engine errors, agent errors, low confidence and failed executions |
| 07 Assistant | LLM + tools | Conversational access to claims, rules and metrics |

## Guardrails

- **Deterministic first.** Risk scoring is plain code, and the LLM agents explain its output without overriding it.
- **Model output is validated.** Explanations and rationales may cite only issues the analyzer actually produced. Anything else is rejected as a failure and escalated.
- **Confidence drives routing.** Low-confidence recommendations go to escalation and are never quietly passed through.
- **No autonomous actions.** No agent, the Commander included, can call an action-taking tool. Execution happens only after explicit human approval, and a revoked approval stops it.
- **Failures escalate and are never swallowed.** Engine errors, model errors and failed executions all route to the escalation agent and the activity log.

## Testing

- **162 offline backend tests**: rule engine, Commander rule table, every agent, human review, retries and escalation paths.
- **Deterministic LLM tests**: `app/testing/fake_anthropic.py` stands in for Claude, so agent tests run offline and give the same result every time. Opt-in `*_live.py` tests run the real two-call Claude chain.
- **Playwright end-to-end tests** (`frontend/e2e/`): the full human-review journey, and re-analysis after a claim is resolved.

```bash
cd backend && pytest -q --ignore-glob="*_live.py"
```

## Stack

FastAPI · SQLAlchemy + Alembic · PostgreSQL · Anthropic Claude · React + TypeScript + Vite + Tailwind · Playwright. Deployed with Render (backend + database, `render.yaml`) and Netlify (frontend).

## Run locally

Use **Python 3.13** (on Windows, Python 3.14 can fail to compile Pydantic dependencies).

```bash
docker compose up -d                       # Postgres 16
cd backend && python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt && alembic upgrade head
uvicorn main:app --reload --host 0.0.0.0 --port 8000

cd frontend && npm install && npm run dev  # http://localhost:5173
```

Put `ANTHROPIC_API_KEY` in `backend/.env` (gitignored).

## Documentation

- [`docs/product-requirements.md`](docs/product-requirements.md): product principles
- [`docs/architecture.md`](docs/architecture.md): system architecture and deterministic risk scoring
- [`docs/ai-design.md`](docs/ai-design.md): the Commander-orchestrated agent system
- [`docs/agents/`](docs/agents/): one spec per agent (role, triggers, inputs and outputs, failure handling)
- [`docs/api.md`](docs/api.md) · [`docs/deployment.md`](docs/deployment.md)

## Troubleshooting: port 8000 already in use (Windows)

`WinError 10048` means something is already listening on port 8000, usually a leftover `python.exe` from an earlier run. Find it with `netstat -ano | findstr :8000` and stop it with `Stop-Process -Id <PID> -Force`. Start the backend with `uvicorn ... --reload` rather than `python main.py`, so Ctrl+C actually stops it.
