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

PDF digital text uses **PyMuPDF as the primary extractor**. **pdfplumber** is an automatic secondary engine used only when PyMuPDF output is unusable (thin, garbage, broken layout, or table-like). There is no env flag to enable or disable it. See [DOCUMENT_INTELLIGENCE.md](DOCUMENT_INTELLIGENCE.md#pdf-text-extraction).
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

### Clear local caches

Removes Python `__pycache__` / `.pyc`, `.pytest_cache`, and Vite `node_modules/.vite` (never touches `venv/`, full `node_modules/`, `.git/`, media, or `.env`).

```bash
npm run clear-cache
# Preview: npm run clear-cache:dry
# Also remove apps/frontend/dist: node scripts/clear-cache.js --dist
```

After clearing, restart the stack (`node start.js`) so Flask and Vite rebuild fresh.

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

Default endpoint is the central LAN server `http://192.168.1.200:11434`. Set `OLLAMA_HOST` (legacy alias `OLLAMA_BASE_URL`) in `apps/backend/.env` to override. JD parse, resume parse, and bulk parse all use this host via the AI gateway. `start.js` health-checks that URL and pulls the selected model onto it (local `ollama serve` only when the host is loopback). Existing `.env` files are not rewritten if those keys are already set — update them yourself when moving off a local daemon.

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

Full sequenced release (stop stale writers, migrate once, Gunicorn **with** `-c`, one scheduler, optional outbox): see [Production release](#production-release) below.

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

→ **[OPERATIONS.md](OPERATIONS.md)**

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

## Operational workflows

<a id="operational-workflows"></a>

Quick reference for day-to-day operations. Prefer live code when behavior differs.

| Workflow | Command / location |
|----------|-------------------|
| **Local app** | `node start.js` from repo root |
| **Media seed** | `python scripts/ensure_media_assets.py` — see [OPERATIONS.md](OPERATIONS.md) |
| **Schema** | Alembic sole source of truth — `cd apps/backend && alembic upgrade head`; new changes via `alembic revision` only |
| **DB preflight** | `node scripts/db-preflight.js` |
| **Resume/JD parse** | `run_document_intelligence` in `app.ai.document_intelligence.pipeline` — APIs in `domains/recruitment/api/parsing.py`; FE uses Form DTOs only — see [AI.md](AI.md#document-intelligence) |
| **Interview scheduling** | Recruiter Google OAuth → Shortlisted triggers slots + booking email → candidate books at `/book/<token>` |
| **AI platform** | Dataset / train / eval — see [AI.md](AI.md) |
| **User manuals** | [user-manual/](user-manual/README.md) |

Landing hero video streams from `MEDIA_ROOT` via `GET /api/media/public/hero-video`. Seed: `apps/frontend/public/videos/website-hero.mp4`.

## Documentation

| Topic | Document |
|-------|----------|
| Docs index | [README.md](README.md) |
| App architecture / API / flows | [GUIDE.md](GUIDE.md) |
| Operations (media, backups) | [OPERATIONS.md](OPERATIONS.md) |
| User manuals (screenshots) | [user-manual/README.md](user-manual/README.md) |
| AI platform | [AI.md](AI.md) |
| AI workspace overview | [ai/README.md](../ai/README.md) |
| Contributing | [CONTRIBUTING.md](../CONTRIBUTING.md) |

---

## Production release

<a id="production-release"></a>

Repeatable host-process release for the HR Intelligence Platform. Does **not** require Docker, Kubernetes, or systemd — use those if you already operate them, or run the same commands under any supervisor.

Local development remains `node start.js` (Flask). That is **not** the production starter.

Related: [DEVELOPMENT.md](DEVELOPMENT.md) · [DEVELOPMENT.md](DEVELOPMENT.md#operational-workflows) · [OPERATIONS.md](OPERATIONS.md#backup--restore-runbook)

Helper (no secrets): `scripts/release-verify.sh pre-deploy` / `post-start` / `db-sessions`.

---

## Roles

| Role | Command (from `apps/backend`) | Migrations |
|------|-------------------------------|------------|
| Migrate | `HCIP_PROCESS_ROLE=migrate alembic upgrade head` **once** | The only production mutator |
| Web | `MIGRATIONS_ALREADY_APPLIED=true gunicorn -c gunicorn.conf.py wsgi:app` | Verify `current == head` only |
| Scheduler | `RUN_INTEGRATION_AUTO_SYNC=1 python -m app.domains.integrations.scheduler` | None |
| Outbox | `python -m app.domains.integrations.worker` (optional dedicated drain) | None |

Web workers also drain the durable outbox via `FOR UPDATE SKIP LOCKED` + leases. A dedicated outbox process is extra capacity, not a second schema manager.

Production web processes **never** run `alembic upgrade head`. `python wsgi.py` is refused when `FLASK_DEBUG` is off. Starting Gunicorn without `-c gunicorn.conf.py` in production fails closed unless `MIGRATIONS_ALREADY_APPLIED=true` (still verify-only; do not use that as a substitute for `-c`).

Do **not** run `scripts/ensure_media_assets.py` or `scripts/backfill_raw_file_blobs.py` against a live release database concurrently with Gunicorn (they call `init_db()`).

---

## Environment (no secrets in this doc)

Production-like = `FLASK_DEBUG=false` and `ALLOW_INSECURE_JWT` off. Gunicorn and production refuse to start otherwise.

Required:

- `FLASK_DEBUG=false`
- `DEVELOPER_MODE=false`
- Unique `JWT_SECRET` (≥32 chars, not the `.env.example` placeholder)
- `INTEGRATION_SECRETS_KEY` (not `dev-integration-secrets`)
- Postgres (`DATABASE_URL` or `POSTGRES_*`)
- `MIGRATIONS_ALREADY_APPLIED=true` on the web process after migrate+verify

Recommended (not a startup hard-fail): `FRONTEND_URL` / `FRONTEND_URLS` for CORS and booking links.

When `GUNICORN_WORKERS>1` in production, `REDIS_URL` is required and must ping (cross-worker parse join; Gunicorn default is 4). Set `GUNICORN_WORKERS=1` if you are not running Redis. If `REDIS_URL` is set, ping must succeed (no silent in-memory fallback). Use `redis://:URL_ENCODED_PASSWORD@host:6379/0` — percent-encode special characters in the password (`/` → `%2F`). The application also canonicalizes unencoded passwords; do not log the URL. The parse owner renews its SET NX lease until completion so a healthy request is not stolen at 180s. Behind nginx/Caddy set `TRUST_PROXY_HEADERS=true`. `GET /ready` includes Redis when `REDIS_URL` is set.

AI parse: leave `OLLAMA_MODEL` unset for hardware-adaptive selection, or pin it explicitly. Runtime YAML: `AI_RUNTIME_CONFIG=ai/runtime/config/runtime.production.yaml`. Ollama is reached at `OLLAMA_HOST` (default `http://192.168.1.200:11434`; env wins). Residual fill timeout: `DOCUMENT_INTELLIGENCE_SEMANTIC_TIMEOUT_SEC` (default 90).

Optional labels for `pg_stat_activity`:

- `HCIP_PROCESS_ROLE` — `web` / `scheduler` / `outbox` / `migrate` (each entrypoint **forces** its role so a leftover `HCIP_PROCESS_ROLE=migrate` in the same shell cannot relabel web/scheduler/outbox)
- `HCIP_RELEASE_ID` — short release id (appears in `application_name`)

Copy knobs from `apps/backend/.env.example`. Never commit `.env`.

Python **3.10+** is required; **3.11** is recommended (CI). Production installs should use the tested pin set:

```bash
cd apps/backend
pip install -r requirements.lock.txt
```

Do not `pip install -r requirements.txt` on a production host if the lockfile is present — open `>=` constraints can resolve newer packages than those tested.

---

## Sequence

### PRE-DEPLOY

#### 1. Identify current release processes

```bash
ss -ltnp | grep -E ':3000|:5173' || true
pgrep -a -f 'gunicorn|integrations.scheduler|integrations.worker|wsgi.py' || true
```

`node start.js` only SIGTERMs port 3000 and does not wait. That is insufficient for production.

#### 2. Stop the old web service

SIGTERM Gunicorn. Wait until it is gone.

#### 3. Stop the old scheduler

SIGTERM `python -m app.domains.integrations.scheduler`.

#### 4. Stop the old dedicated outbox worker

SIGTERM `python -m app.domains.integrations.worker` if it was started.

#### 5. Confirm processes terminated and inspect database connections

```bash
scripts/release-verify.sh pre-deploy
scripts/release-verify.sh db-sessions
```

`pre-deploy` confirms this host has no leftover gunicorn / scheduler / outbox / `wsgi.py` and that `alembic current == heads`.

`db-sessions` is read-only. It reports `application_name`, `client_addr`, backend PID, truncated query, long-running transactions, and locks. It never terminates backends and never prints secrets. Unknown (non-`hcip-*`) client sessions fail the check (use `--report-only` to print without failing).

This release sets `application_name` to `hcip-<role>[-<HCIP_RELEASE_ID>]`. Sessions with empty `application_name` or a foreign `client_addr` are **other processes**. **Stop. Do not continue the deploy** until those processes are stopped on their hosts. This tree cannot SIGTERM remote PIDs and will not rewrite `alembic_version` for an unknown revision in production.

Manual equivalent (SELECT only):

```sql
SELECT pid, client_addr, application_name, usename, backend_start, state,
       left(query, 80) AS query
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY backend_start;
```

### DEPLOY

#### 6. Deploy this application revision

Replace the code tree (rsync, package, or git checkout). Keep the production env file out of the repo.

Take a pre-migration backup before step 8. Procedure: [OPERATIONS.md](OPERATIONS.md#backup--restore-runbook). Schema changes are forward-only; the backup is the only supported way to restore a previous schema.

#### 7. Validate required production environment variables

```bash
cd apps/backend
# FLASK_DEBUG=false DEVELOPER_MODE=false … as in the production env
python -c "from app.config.env_validator import EnvValidator; raise SystemExit(0 if EnvValidator.print_report() else 1)"
```

#### 8. Run database migrations ONCE

```bash
cd apps/backend
export HCIP_PROCESS_ROLE=migrate
alembic upgrade head
```

Do not `alembic stamp head`. Do not `alembic downgrade` as part of release. Concurrent `upgrade head` is serialized with a Postgres advisory lock (`872014002`). Do not add a second lock.

#### 9. Verify revision

```bash
cd apps/backend
alembic current
alembic heads
```

`current` must equal `heads` (today: `20260814_cid_pad3`). `scripts/release-verify.sh pre-deploy` also checks this.

### START

Export `MIGRATIONS_ALREADY_APPLIED=true` (or set it in the production env).

#### 10. Start the web service

```bash
cd apps/backend
export FLASK_DEBUG=false DEVELOPER_MODE=false
export MIGRATIONS_ALREADY_APPLIED=true
export GUNICORN_WORKERS=2   # or 4
gunicorn -c gunicorn.conf.py wsgi:app
```

The master validates env and **verifies** schema at head. Workers do not migrate. Logs must not contain `[DB] Alembic upgrade head complete` from web processes.

#### 11. Start exactly one scheduler

```bash
cd apps/backend
RUN_INTEGRATION_AUTO_SYNC=1 python -m app.domains.integrations.scheduler
```

Do **not** set `RUN_INTEGRATION_AUTO_SYNC` on Gunicorn workers. A second scheduler is idle (advisory lock); still run only one.

#### 12. Start the outbox worker role (optional dedicated)

```bash
cd apps/backend
python -m app.domains.integrations.worker
```

Safe with in-worker drain (SKIP LOCKED + `leased_until`).

#### 13. Verify health

```bash
scripts/release-verify.sh post-start
# or:
curl -sS http://127.0.0.1:3000/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/ready
```

`/ready` must be 200 when Postgres answers `SELECT 1`, and Redis is `ok` when `REDIS_URL` is set. `/health` is liveness (always 200 plus checks).

### POST-DEPLOY

#### 14. Verify expected database connections

```bash
scripts/release-verify.sh db-sessions --report-only
```

Expect `hcip-web` (one per worker), `hcip-scheduler`, and optional `hcip-outbox`. No leftover writers from the previous release on this host. Unknown `client_addr` / empty `application_name` remain an operational stop — do not hide them.

#### 15. Production smoke

- Login / JWT (not Redis-dependent)
- `/health` pid diversity with `GUNICORN_WORKERS=2`
- Resume parse against Ollama `qwen2.5:14b-instruct` (if AI enabled)

#### 16. Verify migration revision remains unchanged

```bash
cd apps/backend
alembic current
alembic heads
```

SIGTERM Gunicorn (graceful). Start it again with the same `MIGRATIONS_ALREADY_APPLIED=true`. Confirm `alembic current` still equals head. Repeat once more.

---

## Stale-writer cleanup (when `pg_stat_activity` shows foreign clients)

1. Run `scripts/release-verify.sh db-sessions --report-only`. Note `client_addr`, `pid`, `application_name`, `backend_start`.
2. On that host: stop Gunicorn / Flask / `start.js` / scheduler / outbox / leftover `python wsgi.py`.
3. Re-query until only this release’s `hcip-*` sessions remain (`scripts/release-verify.sh db-sessions` must pass).
4. `alembic current` / `alembic heads` — must match.
5. `alembic upgrade head` (idempotent; migrate role only).
6. Start this release with `MIGRATIONS_ALREADY_APPLIED=true`; verify; SIGTERM; start again; verify again.

Do not invent an in-app workaround that hides foreign writers. An unknown process on a remote host is an operational ownership problem, not an application code defect.

---

## ROLLBACK

There is **no automatic rollback**. Do not `alembic downgrade` in production. Reverse migrations are not a supported recovery path (data loss / untested reverse DDL).

### Migration fails (`alembic upgrade head` errors)

- Do **not** start web, scheduler, or outbox.
- Do **not** `alembic stamp head`.
- Do **not** `alembic downgrade`.
- Inspect the error, `alembic current`, and `scripts/release-verify.sh db-sessions --report-only`.
- Preferred: fix-forward (correct the migration / environment) and retry `HCIP_PROCESS_ROLE=migrate alembic upgrade head`.
- If the database was partially changed and cannot be repaired: restore the pre-migration backup ([OPERATIONS.md](OPERATIONS.md#backup--restore-runbook)), then retry migrate from the restored schema.

### Application fails after a successful migration

- The schema is already at the new head.
- Preferred: fix-forward (code hotfix) and restart with `MIGRATIONS_ALREADY_APPLIED=true`. Do not migrate again unless a new revision exists.
- Do not start the previous application version against the upgraded schema.

### Previous application version is incompatible with the new schema

- Do **not** start the old release against the upgraded database.
- Restore the pre-migration database backup first, then start the previous code.
- Treat this as restore + previous-code restart, not an Alembic downgrade.

---

## LinkedIn / Naukri

Out of scope for internal production readiness. Adapters stay fail-closed until provider access exists.

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
