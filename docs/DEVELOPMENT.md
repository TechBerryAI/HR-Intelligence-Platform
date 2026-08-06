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
| Python | 3.8+ (backend), 3.11+ (ai) | `python --version` |
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
| `HCIP_SKIP_OLLAMA` | Skip Ollama serve/pull |
| `HCIP_OPEN_BROWSER` | Set `false` to skip opening the browser |

## Quick start (AI platform)

```bash
cd ai
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

## Common workflows

### Run frontend only

```bash
cd apps/frontend && npm install && npm run dev
```

### Run backend only

```bash
cd apps/backend && source venv/bin/activate && python wsgi.py
```

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

## Environment files

| File | Purpose |
|------|---------|
| `apps/backend/.env` | App, Postgres, JWT, mail, Ollama, ATS, parsing, integration secrets |
| `apps/frontend/.env` | Vite API URL / public origin (optional) |
| `ai/.env` | AI workspace overrides (optional) |

Copy from the matching `.env.example`, then fill secrets. Never commit `.env` files.

Optional integration vars (see `apps/backend/.env.example`):

- `INTEGRATION_SECRETS_KEY` — Fernet key (or any secret string) for encrypting job-board credentials
- `INTEGRATION_MAX_RETRIES` — default `3`
- `INTEGRATION_RETRY_BASE_SECONDS` — default `1.0`
- `INTEGRATION_WORKER_MAX_WORKERS` — default `4`

### Media volume (`MEDIA_ROOT`)

Durable product files (parse uploads, feedback screenshots, bulk staging, landing hero MP4) live **outside the git tree**:

| Key | Purpose |
|-----|---------|
| `MEDIA_ROOT` | Absolute path to media volume (prod). Default when unset: `<repo>/.media` (gitignored) |
| `VITE_HERO_VIDEO_URL` | Optional CDN/HTTPS override for landing video; else `/api/media/public/hero-video` |

```bash
# Seed hero video from a one-time copy (or place website-hero.mp4 under MEDIA_ROOT/public/)
python scripts/ensure_media_assets.py
```

- Apply resumes remain Postgres `BYTEA` (`candidate_profiles.resume`).
- Head HR PDF reports stay client-side downloads (not stored on the server).
- `raw_files.storage_url` uses opaque keys `media:uploads/...` (not `file://` absolute paths).

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
| User manuals (screenshots) | [user-manual/README.md](user-manual/README.md) |
| Architecture / engineering archive (optional) | [ARCHITECTURE.md](ARCHITECTURE.md) · [ENGINEERING.md](ENGINEERING.md) |
| AI platform overview | [ai/README.md](../ai/README.md) |
| TOON ontology | [ai/toon/README.md](../ai/toon/README.md) |
| Data pipeline | [ai/docs/DATA_PIPELINE.md](../ai/docs/DATA_PIPELINE.md) |
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
