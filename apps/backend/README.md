# Backend

Flask REST API for the HR Intelligence application.

Canonical location: `apps/backend/` (repository root).

## What is this?

The backend provides authentication, job management, applications, resume/JD parsing, ATS matching, admin tools, and Head of HR APIs. It uses PostgreSQL via a connection pool and raw SQL helpers.

## Why does it exist?

All HRMS business logic and data persistence live here. The frontend and Electron shell are presentation layers only.

## What belongs here?

| Path | Purpose |
|------|---------|
| `wsgi.py` / `app.py` | Application entry |
| `app/` | Modular monolith (`domains/*`, bootstrap, config) |
| `schema_pg/` | PostgreSQL DDL and seeds |
| Root `*.py` shims | Compatibility re-exports from `app.*` |

## What should never be placed here?

- React components → `apps/frontend/`
- AI runtime / capabilities → `ai/`
- Desktop shell logic → `apps/desktop/`

## Dependencies

| External | Purpose |
|----------|---------|
| PostgreSQL | Primary datastore |
| LLM API (X.AI / Grok) | Resume/JD parsing |
| SMTP | OTP and notifications |
| Optional: n8n, Bulk Parser API | ATS and bulk parsing |

## Consumers

| Consumer | Usage |
|----------|-------|
| Frontend SPA | REST API over HTTP |
| Electron | Same API; native dialogs only in Electron |

## Quick start

```bash
cd apps/backend
cp .env.example .env   # configure DATABASE_URL or POSTGRES_*
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python wsgi.py         # or: gunicorn -c gunicorn.conf.py wsgi:app
```

Or from repo root: `node start.js`

## Related documentation

- [Docs index](../../docs/README.md)
- [Engineering archive](../../docs/ENGINEERING.md#backend)
- [Database test script](../../scripts/database/test_db_connection.py)
