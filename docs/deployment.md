# Deployment

Clyra deploys as two independently hosted pieces:

| Piece      | Host    | Source dir        | Config file                |
| ---------- | ------- | ----------------- | -------------------------- |
| Frontend   | Netlify | `frontend/`       | `frontend/netlify.toml`    |
| Backend    | Render  | `backend/`        | `render.yaml` (repo root)  |
| Database   | Render  | —                 | `render.yaml` (`clyra-db`) |

Both hosts build from the `main` branch. This is a synthetic-data demo, so both
are provisioned on free tiers — see [Free-tier behavior](#free-tier-behavior)
for the trade-offs that come with that.

---

## Prerequisites

- The repo is pushed to GitHub with `main` as the default branch.
- A Render account and a Netlify account, each connected to the GitHub repo.
- An Anthropic API key for the live agents (reasoning, recommendation,
  assistant). Without it those agents return a "not configured" style failure;
  the deterministic risk engine and the rest of the app still work.

---

## Backend + database (Render)

### One-time setup

1. **New > Blueprint** in the Render dashboard, point it at this repo. Render
   reads [`render.yaml`](../render.yaml) and proposes:
   - `clyra-backend` — a free Python web service, root dir `backend/`.
   - `clyra-db` — a free PostgreSQL instance.
2. Apply the blueprint. `DATABASE_URL` is wired from `clyra-db` automatically.
3. Set the two `sync: false` env vars on `clyra-backend` (Environment tab):
   - `ANTHROPIC_API_KEY` — the Anthropic key.
   - `CORS_ORIGINS` — the Netlify site URL, no trailing slash, e.g.
     `https://clyra.netlify.app`. Add more as a comma-separated list (custom
     domain, Netlify deploy-preview pattern) if needed.
4. Trigger a deploy. On boot the start command runs `alembic upgrade head`
   before starting uvicorn, so the schema is created on the first deploy.
5. **Seed synthetic data**: open the `clyra-backend` **Shell** in the Render
   dashboard and run `python scripts/seed_claims.py`. The seed is deterministic
   (`random.seed(42)`) and safe to re-run: it creates claims only if fewer than
   80 exist, then reconciles **every** claim through the real analyzer +
   Commander and prints the resulting risk/status distribution, exiting
   non-zero if any status/risk invariant is violated
   (see [`architecture.md`](./architecture.md#claim-status-and-computed-risk)).
   Re-run it after the free Postgres instance lapses and is re-provisioned, or
   any time `python scripts/risk_distribution.py` (read-only) reports a
   violation.

### Key configuration details

- **Start command:** `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`
  Render injects `$PORT`; binding to it is required or the deploy is marked
  unhealthy. Migrations run every boot — a fast no-op once the schema is
  current. Move them to a paid pre-deploy command if boot latency matters.
- **Health check path:** `/api/health` (set in `render.yaml`). It returns
  `{"status": "ok", "service": "clyra-backend"}`. Render polls this after each
  deploy and periodically after; a non-200 blocks the release. Note the `/api`
  prefix — the bare `/` root route also responds but is not the configured
  check.
- **Python version:** pinned to `3.13.5` via `PYTHON_VERSION` in `render.yaml`.
  Do not let it float to 3.14 — Pydantic's native deps have a known build
  failure there (see the root `README.md`).
- **Database URL scheme:** Render hands out `postgresql://…`. `app/core/config.py`
  normalizes any `postgres://` / `postgresql://` value to the
  `postgresql+psycopg://` driver scheme SQLAlchemy needs, so the dashboard value
  is used verbatim — no manual editing.
- **Connection resilience:** the engine uses `pool_pre_ping=True`, which
  transparently recycles connections Render's database drops while the service
  is idle.

### Free-tier database expiry

Render's free PostgreSQL instance is **deleted 30 days after creation**. When it
lapses: provision a new `clyra-db`, re-link `DATABASE_URL`, redeploy (runs
migrations), and re-run the seed script.

---

## Frontend (Netlify)

### One-time setup

1. **Add new site > Import an existing project**, pick this repo.
2. Set the **base directory** to `frontend`. With that set, the settings in
   [`frontend/netlify.toml`](../frontend/netlify.toml) apply as-is:
   - Build command: `npm run build` (runs `tsc -b && vite build`).
   - Publish directory: `dist`.
   - Node version: 22.
3. Add the environment variable **`VITE_API_BASE`** = the Render backend URL,
   no trailing slash, e.g. `https://clyra-backend.onrender.com`. It is read at
   build time, so changing it requires a redeploy.
4. Deploy. Note the resulting site URL and put it in the backend's
   `CORS_ORIGINS` (above).

### Key configuration details

- **SPA fallback:** `netlify.toml` redirects `/* → /index.html` with status
  `200`. Without it, a hard refresh on any route other than `/` returns a 404,
  because React Router owns routing client-side.
- **API base URL:** the three service modules in `frontend/src/services/` read
  `import.meta.env.VITE_API_BASE` and fall back to `http://127.0.0.1:8000` for
  local dev. In production the env var must be set or the deployed site calls
  localhost and every request fails.

---

## Free-tier behavior

### Backend cold starts (why the first load is slow)

Render **spins down a free web service after ~15 minutes of no inbound
traffic**. The next request has to wait for the container to cold-start —
roughly **30–60 seconds** — before it is served. Because the start command runs
`alembic upgrade head` first, add a few seconds on top of that.

What this looks like in the app: after a quiet period, the first page load
(dashboard, claims list) hangs for up to a minute, then everything is fast
again until the next idle spin-down. This is expected free-tier behavior, not a
bug in the app or the queries.

Options if it becomes annoying for a demo:

- Hit `https://<backend>/api/health` a minute or two before showing the demo to
  warm the service.
- Add an external uptime pinger (e.g. a 10-minute cron) against `/api/health`
  to keep it warm — this trades free-tier compute minutes for availability.
- Upgrade the Render service to a paid instance type (no spin-down).

### Frontend

Netlify does not cold-start — the built static site is served from CDN. Only the
backend has the spin-down behavior.

---

## Deployment checklist

### Pre-deploy (once, before the first deploy)

- [ ] Repo pushed to GitHub, `main` is the default branch.
- [ ] `render.yaml` present at repo root; `frontend/netlify.toml` present.
- [ ] Anthropic API key available.
- [ ] Local `npm run build` in `frontend/` succeeds.
- [ ] Local `alembic upgrade head` in `backend/` succeeds against a clean DB.
- [ ] Backend test suite passes (`pytest` in `backend/`).

### Render (backend + DB)

- [ ] Blueprint applied; `clyra-backend` and `clyra-db` created.
- [ ] `DATABASE_URL` linked from `clyra-db` (auto).
- [ ] `ANTHROPIC_API_KEY` set (Environment tab).
- [ ] `CORS_ORIGINS` set to the Netlify site URL (no trailing slash).
- [ ] `PYTHON_VERSION` = `3.13.5` (from `render.yaml`).
- [ ] Deploy succeeds; health check at `/api/health` is green.
- [ ] `python scripts/seed_claims.py` run once in the Render shell.
- [ ] `GET https://<backend>/api/claims` returns seeded claims.

### Netlify (frontend)

- [ ] Site imported; base directory = `frontend`.
- [ ] `VITE_API_BASE` set to the Render backend URL (no trailing slash).
- [ ] Deploy succeeds.
- [ ] Deep-linking works: loading `https://<site>/claims` directly renders the
      app (SPA fallback), not a 404.

### End-to-end verification

- [ ] Dashboard loads live metrics from the backend (allow for a cold start).
- [ ] Claims list and a claim detail page load.
- [ ] Claim analysis / risk score renders.
- [ ] AI Assistant chat returns a grounded reply (requires `ANTHROPIC_API_KEY`).
- [ ] No CORS errors in the browser console — if there are, `CORS_ORIGINS` on
      Render does not exactly match the site origin.

### Post-deploy housekeeping

- [ ] Calendar reminder for the free `clyra-db` 30-day expiry.
- [ ] If cold starts hurt the demo, warm `/api/health` beforehand or add a
      pinger.
