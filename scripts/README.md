# Scripts

Operational utilities for development and database diagnostics.

## What is this?

Root-level scripts that support local development, CI preflight, and database connectivity checks.

## Scripts

| Script | Purpose |
|--------|---------|
| `db-preflight.js` | PostgreSQL connectivity diagnostics (reads `apps/backend/.env`, WSL-aware) |
| `database/test_db_connection.py` | Python DB connection test |

## What belongs here?

- Cross-cutting dev utilities used from repo root
- Database and environment diagnostics

## What should never be placed here?

- AI platform CLIs → `ai/runtime/cli/`, `ai/dataset/*/cli/`
- Backend one-offs tied to Flask → prefer `apps/backend/` or document here explicitly
- Production deployment scripts → CI workflows under `infrastructure/`

## Quick start

```bash
# Database preflight (Node)
node scripts/db-preflight.js

# Database test (Python)
cd apps/backend && source venv/bin/activate
python ../../scripts/database/test_db_connection.py
```

## Resume parsing smoke test (Ollama)

Baseline end-to-end test for Milestone 1 AI pipeline:

```bash
# Prerequisites
ollama pull qwen2.5:7b-instruct
ollama serve   # if not already running

# Install backend + AI runtime deps
cd apps/backend && source venv/bin/activate
pip install -r requirements.txt

# Run integration smoke test (requires Ollama)
pytest tests/test_resume_ollama_smoke.py -v -m integration

# Full app manual test
node start.js
# Open Jobs → Apply → upload resume (public form autofills via Ollama) → submit
```

## Related documentation

- [Development guide](../docs/DEVELOPMENT.md)
- [Backend README](../apps/backend/README.md)
