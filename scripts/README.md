# Scripts

Operational utilities for development and database diagnostics.

## What is this?

Root-level scripts that support local development, CI preflight, and database connectivity checks.

## Scripts

| Script | Purpose |
|--------|---------|
| `db-preflight.js` | PostgreSQL connectivity diagnostics (reads `backend/.env`, WSL-aware) |
| `database/test_db_connection.py` | Python DB connection test |

## What belongs here?

- Cross-cutting dev utilities used from repo root
- Database and environment diagnostics

## What should never be placed here?

- AI platform CLIs → `ai/runtime/cli/`, `ai/dataset/*/cli/`
- Backend one-offs tied to Flask → prefer `backend/` or document here explicitly
- Production deployment scripts → future `tools/` or CI workflows

## Quick start

```bash
# Database preflight (Node)
node scripts/db-preflight.js

# Database test (Python)
cd backend && source venv/bin/activate
python ../scripts/database/test_db_connection.py
```

## Related documentation

- [Development guide](../docs/DEVELOPMENT.md)
- [Backend README](../backend/README.md)
