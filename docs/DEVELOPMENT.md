# Development Guide

Local setup, workflows, and navigation for engineers new to the repository.

## Five-minute orientation

```
HR Job Portal
├── apps/
│   ├── frontend/   React SPA (Vite) — what users see
│   ├── backend/    Flask API — business logic + PostgreSQL
│   └── desktop/    Electron shell — native folder dialogs only
├── ai/             AI platform — runtime, capabilities, dataset, TOON
├── docs/           HRMS documentation
├── scripts/        Dev utilities (db-preflight, DB tests)
├── tests/          Test index (tests live with their owners)
├── packages/       Cross-app shims
└── infrastructure/ Docker + CI templates
```

**Start here:** [README.md](README.md)

## Prerequisites

| Tool | Version | Check |
|------|---------|--------|
| Node.js | 16+ | `node --version` |
| Python | 3.10+ required (backend); 3.11 recommended (matches CI); 3.11+ (ai) | `python --version` |
| PostgreSQL | 12+ | Local or cloud |

## Quick start (HRMS)

```bash
cp apps/backend/.env.example apps/backend/.env
# Edit apps/backend/.env — set DATABASE_URL or POSTGRES_*

# Local stack (backend + frontend; DB must already be reachable)
node start.js

# Full VM stack: wait/start DB (Hyper-V or Docker) + backend + frontend + Ollama
node start-vm.js
# or: npm run start:vm
```

Opens http://localhost:5173 (frontend) and http://localhost:3000 (backend).

`start.js` frees port **3000** before launching Flask (avoids a stale backend keeping old API code). After backend Python changes, restart with Ctrl+C then `node start.js` — Flask does not hot-reload by default (`FLASK_USE_RELOADER=false`).

Optional `start-vm.js` knobs (env or `apps/backend/.env`):

| Key | Purpose |
|-----|---------|
| `HCIP_VM_NAME` | Hyper-V VM name to `Start-VM` when DB is down |
| `HCIP_VM_PROVIDER` | `auto` (default), `hyperv`, or `docker` |
| `HCIP_START_DOCKER_DB` | Force `docker compose` Postgres |
| `HCIP_SKIP_OLLAMA` | Skip Ollama health-check (and local serve/pull when host is loopback) |
| `HCIP_OPEN_BROWSER` | Set `false` to skip opening the browser |

## Quick start (AI platform)

```bash
cd ai
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

Scanned PDF / image resumes need **RapidOCR** (`rapidocr-onnxruntime` in `requirements.txt`; Python **3.10–3.12** recommended). Without it, digital PDF/DOCX still parse; OCR pages fall back to Tesseract if installed, else thin-text skips.
## Common workflows

### Run frontend only

```bash
cd apps/frontend && npm install && npm run dev
```

### Run backend only

```bash
cd apps/backend && source venv/bin/activate && python wsgi.py
```

Production Python installs should use the tested pin set: `pip install -r requirements.lock.txt` (Python 3.10+ required, 3.11 recommended).

### Run Electron (bulk parser)

```bash
# Terminal 1: cd apps/frontend && npm run dev
# Terminal 2: npm run electron   (from repo root)
```

### Run AI runtime CLI

```bash
cd ai && source .venv/bin/activate
python -m runtime.cli.main --help
```

### Database diagnostics

```bash
node scripts/db-preflight.js
python scripts/database/test_db_connection.py
```

### Schema migrations (Alembic — sole source of truth)

Schema changes live only under `apps/backend/alembic/`. The squashed baseline is `20260810_s001` (SQL in `alembic/baseline/`).

```bash
cd apps/backend
alembic upgrade head
alembic current
alembic revision -m "describe_change"
```

Fresh local DB: create an empty Postgres database, then `alembic upgrade head`. Do **not** add parallel SQL schema trees. See `apps/backend/alembic/README.md`.

## Environment files

| File | Purpose |
|------|---------|
| `apps/backend/.env` | App, Postgres, JWT, mail, Ollama, ATS, parsing, integration secrets |
| `apps/frontend/.env` | Vite API URL / public origin (optional) |
| `ai/.env` | AI workspace overrides (optional) |

Copy from the matching `.env.example`, then fill secrets. Never commit `.env` files.

### Ollama host

Default endpoint is the central LAN server `http://192.168.1.200:11434`. Set `OLLAMA_HOST` (legacy alias `OLLAMA_BASE_URL`) in `apps/backend/.env` to override. `start.js` health-checks that URL; it starts a local `ollama serve` / pull only when the host is loopback (`127.0.0.1` or `localhost`). Existing `.env` files are not rewritten if those keys are already set — update them yourself when moving off a local daemon.

### Ollama model selection

Precedence (identical in `start.js`, `hardware.py`, and runtime YAML):

1. **Explicit `OLLAMA_MODEL`** — operator pin; never overridden
2. **`HCIP_HARDWARE_PROFILE`** — `gpu_high` | `gpu_mid` | `unknown` | `cpu`
3. **`HCIP_VRAM_MB`** — integer megabytes (0 is valid and means CPU)
4. **NVIDIA `nvidia-smi`** — automatic VRAM → high (≥20GB) / mid (≥6GB)
5. **GPU present but VRAM unknown** (NVIDIA device node / WSL `/dev/dxg` / `lspci` NVIDIA|AMD) → `unknown` (7B, concurrency 1). This is **not** treated as a weak CPU.
6. **Conservative fallback** — `cpu` / `qwen2.5:3b-instruct`

`start.js` does **not** write `OLLAMA_MODEL` into `.env` when it is unset. The Ollama pull helper forwards only `OLLAMA_MODEL`, `HCIP_HARDWARE_PROFILE`, and `HCIP_VRAM_MB` from `apps/backend/.env` when those keys are unset in the process environment (process env still wins). AMD, Apple, and Intel GPUs are not VRAM-measured; set `HCIP_HARDWARE_PROFILE` (and optionally `HCIP_VRAM_MB`).

Public resume stream fallback joins an in-process parse of the same file bytes. Production with `GUNICORN_WORKERS>1` requires `REDIS_URL` (startup fails if missing or unreachable). The owner renews a SET NX lease until the parse finishes so a 180s TTL cannot expire under a healthy ~320s Gunicorn request. `GUNICORN_WORKERS=1` does not require Redis.

Live Redis lease test (disposable instance, not production Redis):

```bash
TEST_REDIS_URL=redis://127.0.0.1:6379/15 python3 -m pytest tests/backend/test_parse_redis_lease.py -k live -q
```

AI performance harness (this machine only; do not treat numbers as SLAs):

```bash
PYTHONPATH=apps/backend python3 ai/eval/run_ai_performance_benchmark.py --limit 2
HCIP_HARDWARE_PROFILE=gpu_mid PYTHONPATH=apps/backend python3 ai/eval/run_ai_performance_benchmark.py --limit 2
HCIP_HARDWARE_PROFILE=cpu PYTHONPATH=apps/backend python3 ai/eval/run_ai_performance_benchmark.py --limit 2
```

Optional integration vars (see `apps/backend/.env.example`):

- `INTEGRATION_SECRETS_KEY` — Fernet key (or any secret string) for encrypting job-board / OAuth credentials (required in production; do not rely on plaintext fallback)
- `INTEGRATION_MAX_RETRIES` — default `3`
- `INTEGRATION_RETRY_BASE_SECONDS` — default `1.0`
- `INTEGRATION_WORKER_MAX_WORKERS` — default `4`
- `INTEGRATION_AUTO_SYNC_INTERVAL_SECONDS` — default `900` (min 60)
- `RUN_INTEGRATION_AUTO_SYNC` — set `1` only in the dedicated scheduler process (not in Gunicorn web workers)
- `REDIS_URL` — **required in production when `GUNICORN_WORKERS>1`** (cross-worker parse join; Gunicorn default is 4). Set `GUNICORN_WORKERS=1` for single-process production without Redis. JWT/OTP/outbox do not need Redis. Dev (`FLASK_DEBUG=true`) does not require Redis. If `REDIS_URL` is set and workers>1 but Redis becomes unreachable at runtime, parse requests fail closed (`Redis parse coordination unavailable`) instead of silently duplicating work per worker. Use `redis://:URL_ENCODED_PASSWORD@host:6379/0` when Redis has a password (`/` in the password must be `%2F`).
- `TRUST_PROXY_HEADERS` — set `true` behind nginx/Caddy so public parse rate limits use `X-Forwarded-For`. Unset (default) uses `request.remote_addr` only.

### Production processes (Gunicorn + scheduler)

Full sequenced release (stop stale writers, migrate once, Gunicorn **with** `-c`, one scheduler, optional outbox): **[PRODUCTION_RELEASE.md](PRODUCTION_RELEASE.md)**.

Gunicorn runs multiple web workers. Integration **auto-sync** is singleton work and must not start inside every worker. **Never** omit `-c gunicorn.conf.py`. Production web processes require `MIGRATIONS_ALREADY_APPLIED=true` and verify `alembic current == head`; they never run migrations. Without `-c` and without the flag, production startup fails closed.

```bash
# Web API (from apps/backend)
gunicorn -c gunicorn.conf.py wsgi:app

# Dedicated auto-sync (separate process)
RUN_INTEGRATION_AUTO_SYNC=1 python -m app.domains.integrations.scheduler

# Optional dedicated outbox drain (web workers already drain via SKIP LOCKED)
python -m app.domains.integrations.worker
```

Web workers still start the in-memory integration task queue (request-path publish). Only the auto-sync loop is gated.

### Google Calendar interview scheduling (Current)

After an application becomes **Shortlisted** (manual or ATS), if the assigned recruiter has connected Google Calendar, the backend generates FreeBusy-aware slots, stores an `Invited` interview + `interview_slots`, and emails a secure booking link (`FRONTEND_URL/book/<token>`). Booking creates a Google Calendar event with Meet and sets `applications.status` to **Interview**. Interview lifecycle detail lives on `interviews.status` (`Invited` → `Scheduled` → …).

| Env | Purpose |
|-----|---------|
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client |
| `GOOGLE_OAUTH_REDIRECT_URI` | e.g. `http://localhost:3000/api/integrations/google/callback` |
| `INTERVIEW_DURATION_MINUTES` | default `30` |
| `INTERVIEW_LOOKAHEAD_DAYS` | business days to offer (default `5`) |
| `INTERVIEW_TZ` | default `Asia/Kolkata` |
| `INTERVIEW_INVITE_TTL_HOURS` | booking link TTL (default `72`) |

Recruiter connect UI: **Settings → Integrations → Google Calendar**.

**Future:** interview reminder workers (hooks stubbed as `on_invite_sent` / `on_interview_scheduled`).

### External job boards (LinkedIn / Naukri / custom HTTP)

PostgreSQL `external_jobs` is the durable outbox. Do not add Celery/RabbitMQ/Kafka for this.

- **LinkedIn:** official Job Posting API adapter (`POST /rest/simpleJobPostings`, operations CREATE/UPDATE/CLOSE/RENEW, correlation id `externalJobPostingId`). Live publish requires LinkedIn Talent Solutions partner access. Until then the UI shows **Provider access required**, never Published.
- **Naukri:** no public posting API in this repo. Same access-required status.
- **Custom HTTP:** real outbound HTTP using company `baseUrl` + endpoints. CREATE is at-least-once if the remote response is lost.

### Media storage

Durable files live **outside** the project (`…/hcip-data/`). Postgres backups are owned by the DB team. Full command reference (seed, offload, env keys):

→ **[MEDIA_AND_BACKUPS.md](MEDIA_AND_BACKUPS.md)**

```bash
# From repo root — seed hero / ensure media dirs
python scripts/ensure_media_assets.py --force
```

## Where to put new code

| I am building… | Put it in… |
|----------------|------------|
| A new HR page or component | `frontend/src/` |
| Theme / Dark-Light behavior | `frontend/src/core/theme/themeConfig.js` (+ CSS tokens in `src/styles/index.css`) — do not fork theme logic |
| A new API endpoint | `backend/` (blueprint) |
| Job-board / ATS distribution provider | `backend/app/domains/integrations/` (provider + mapper + factory register) |
| A native desktop feature | `electron/` (IPC only) |
| A new AI task | `ai/capabilities/<name>/` |
| A new LLM provider | `ai/providers/` |
| A dataset pipeline stage | `ai/dataset/` |
| TOON field or mapping | `ai/toon/v1/` |
| HR domain contract | `ai/contracts/` |

### UI theme (centralized)

Anyone on this branch shares one theme system:

| Piece | Location |
|-------|----------|
| Config (storage key, defaults, dark-only routes, surface mapping) | `apps/frontend/src/core/theme/themeConfig.js` |
| React state | `ThemeProvider` / `useTheme()` — mounted in `main.jsx` |
| Toggle UI | `ThemeToggle`: Navbar chrome control (icon + Light/Dark); Head HR Overview between Home and Refresh (`org-btn-ghost`); mobile org header |
| Colors | `--ei-*` in `apps/frontend/src/styles/index.css` |
| FOUC bootstrap | `apps/frontend/public/theme-init.js` (key must match `THEME_STORAGE_KEY`) |

Landing `/` stays dark-only. Prefer `var(--ei-text-primary)` etc. over hard-coded zinc/hex. Head HR Match Analysis (and related `MatchExplanation` enterprise panels) use `--ei-*` / `--ei-tone-*` so they follow Light/Dark with the rest of the org shell.

## Testing strategy

Tests are **colocated** with their owner:

| Area | Location |
|------|----------|
| AI runtime | `ai/runtime/tests/` |
| AI providers | `ai/providers/ollama/tests/` |
| Capabilities | `ai/capabilities/*/tests/` |
| Dataset | `ai/dataset/*/tests/` |
| TOON | `ai/toon/v1/tests/` |

Run all AI tests: `cd ai && pytest`

## Documentation

| Topic | Document |
|-------|----------|
| Docs index | [README.md](README.md) |
| Unique workflows | [WORKFLOWS.md](WORKFLOWS.md) |
| User manuals (screenshots) | [user-manual/README.md](user-manual/README.md) |
| Document intelligence | [DOCUMENT_INTELLIGENCE.md](DOCUMENT_INTELLIGENCE.md) |
| AI workflows / ADRs | [AI_WORKFLOW.md](AI_WORKFLOW.md) · [AI_DATA_PIPELINE.md](AI_DATA_PIPELINE.md) · [ADRS.md](ADRS.md) |
| AI platform overview | [ai/README.md](../ai/README.md) |
| TOON ontology | [ai/toon/README.md](../ai/toon/README.md) |
| Contributing | [CONTRIBUTING.md](../CONTRIBUTING.md) |

## Troubleshooting

| Problem | Action |
|---------|--------|
| Env validation failed | `cd backend && python env_validator.py` |
| DB connection failed | Check `backend/.env`; run `node scripts/db-preflight.js` |
| Port in use | Stop process on 3000 or 5173 |
| AI tests need Ollama | Proposal tests use mock runtime; runtime tests mock Ollama HTTP |

More: [README.md](../README.md#troubleshooting)

### Developer Mode (Admin performance dashboard)

```bash
# apps/backend/.env — enables collector + Admin APIs (restart required)
DEVELOPER_MODE=true
# optional: DEVELOPER_MODE_MAX_SESSIONS=500
```

1. Restart the backend after setting the flag.
2. Log in as **Head of HR** → **Settings** → turn on **Developer Mode**.
3. Sidebar shows **Developer Mode** → Performance Dashboard.

Recruiters and CEO never see the toggle or nav. When `DEVELOPER_MODE=false`, the Settings toggle is disabled and APIs stay off (only `[TIMING]` INFO logs).
