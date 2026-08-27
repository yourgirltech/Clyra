# Clyra

Clyra is a U.S.-focused AI claims operations assistant for healthcare billing and revenue-cycle teams, designed to support claim review, AI-guided recommendations, and transparent human approval before any consequential action is taken. The MVP uses only synthetic healthcare claims data so the demo remains safe, privacy-compliant, and realistic without exposing real PHI.

Demo environment — uses synthetic healthcare claims data.

## Documentation

- [`docs/product-requirements.md`](docs/product-requirements.md) — core product principles
- [`docs/architecture.md`](docs/architecture.md) — system architecture and deterministic risk scoring
- [`docs/api.md`](docs/api.md) — API surface
- [`docs/ai-design.md`](docs/ai-design.md) — the Commander-orchestrated agent system overview
- [`docs/deployment.md`](docs/deployment.md) — deploying the frontend to Netlify and the backend + database to Render, plus a deployment checklist
- [`docs/agents/`](docs/agents/) — full agent-by-agent roadmap (planning docs, not implementation): [00-commander](docs/agents/00-commander.md), [01-analyzer](docs/agents/01-analyzer-agent.md), [02-reasoning](docs/agents/02-reasoning-agent.md), [03-recommendation](docs/agents/03-recommendation-agent.md), [04-followup](docs/agents/04-followup-agent.md), [05-reminder](docs/agents/05-reminder-agent.md), [06-escalation](docs/agents/06-escalation-agent.md), [07-assistant](docs/agents/07-assistant-agent.md). Runtime (Python vs. n8n vs. other) is an open decision these docs deliberately do not make.

To run the frontend locally, open a terminal in the `frontend` folder and run `npm install`, then `npm run dev`. To run the backend locally, open a terminal in the `backend` folder, create or activate a virtual environment, install dependencies from `requirements.txt`, and start the app with `uvicorn main:app --reload --host 0.0.0.0 --port 8000`.

Python runtime requirement: use Python 3.13.x for this project. Python 3.14 on Windows can fail while compiling Pydantic dependencies, which causes the backend setup to break before the app starts. This project is pinned to 3.13 to avoid that known compile issue on fresh clones.

## Checking for a stuck process on Windows before starting the backend

`uvicorn` fails to start with `WinError 10048` ("only one usage of each socket address is normally permitted") when something is already bound to port 8000. This is an environment issue, not a code bug — before starting the backend, check for and clear a stuck process:

```powershell
# Find what's listening on port 8000
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

# Or, using netstat
netstat -ano | findstr :8000
```

The last column is the PID. Look up and stop it:

```powershell
Get-Process -Id <PID>
Stop-Process -Id <PID> -Force
```

A leftover `python.exe` process from a previous `python main.py` or `uvicorn` run (e.g. one left running after a terminal was closed without Ctrl+C) is the most common cause. Always run the backend the documented way — `uvicorn main:app --reload --host 0.0.0.0 --port 8000` — rather than `python main.py`, so `--reload`'s process lifecycle is managed correctly and Ctrl+C actually stops it.
