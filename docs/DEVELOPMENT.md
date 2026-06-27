# Development Guide

Local setup, workflows, and navigation for engineers new to the repository.

## Five-minute orientation

```
HR Job Portal
├── frontend/     React SPA (Vite) — what users see
├── backend/      Flask API — business logic + PostgreSQL
├── electron/     Desktop shell — native folder dialogs only
├── ai/           AI platform — runtime, capabilities, dataset, TOON
├── docs/         HRMS documentation
├── scripts/      Dev utilities (db-preflight, DB tests)
├── tests/        Test index (tests live with their owners)
└── tools/        CLI entry-point index
```

**Start here:** [DOCUMENTATION_MAP.md](DOCUMENTATION_MAP.md)

## Prerequisites

| Tool | Version | Check |
|------|---------|--------|
| Node.js | 16+ | `node --version` |
| Python | 3.8+ (backend), 3.11+ (ai) | `python --version` |
| PostgreSQL | 12+ | Local or cloud |

## Quick start (HRMS)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — set DATABASE_URL or POSTGRES_*

node start.js
```

Opens http://localhost:5173 (frontend) and http://localhost:3000 (backend).

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
cd frontend && npm install && npm run dev
```

### Run backend only

```bash
cd backend && source venv/bin/activate && python app.py
```

### Run Electron (bulk parser)

```bash
# Terminal 1: cd frontend && npm run dev
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
| `backend/.env` | Database, JWT, mail, LLM keys |
| `frontend/.env` | Vite API URL (optional) |
| `ai/.env` | AI runtime overrides (optional) |

Never commit `.env` files. Use `.env.example` as reference.

## Where to put new code

| I am building… | Put it in… |
|----------------|------------|
| A new HR page or component | `frontend/src/` |
| A new API endpoint | `backend/` (blueprint) |
| A native desktop feature | `electron/` (IPC only) |
| A new AI task | `ai/capabilities/<name>/` |
| A new LLM provider | `ai/providers/` |
| A dataset pipeline stage | `ai/dataset/` |
| TOON field or mapping | `ai/toon/v1/` |
| HR domain contract | `ai/contracts/` |

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
| Full HRMS architecture | [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) |
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
