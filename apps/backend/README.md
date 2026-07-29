# Backend

Flask REST API for the HR Job Portal application.

## What is this?

The backend provides authentication, job management, applications, resume/JD parsing, ATS matching, admin tools, and Head of HR APIs. It uses PostgreSQL via a connection pool and raw SQL helpers.

## Why does it exist?

All HRMS business logic and data persistence live here. The frontend and Electron shell are presentation layers only.

## What belongs here?

| Path | Purpose |
|------|---------|
| `app.py` | Application entry, CORS, blueprint registration |
| `auth.py`, `candidate.py`, `jobs.py`, … | Route blueprints |
| `db.py` | PostgreSQL pool and query helpers |
| `toon.py` | TOON serialize/parse (production wire format) |
| `llm_service.py` | HRMS LLM parsing prompts |
| `parsing_utils.py` | TOON validation and persistence |
| `schema_pg/` | PostgreSQL DDL and seeds |
| `services/` | ATS, bulk parsing, notifications |
| `helpers/` | Email templates and OTP |

## What should never be placed here?

- React components → `frontend/`
- AI runtime / capabilities → `ai/`
- Desktop shell logic → `electron/`

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
cd backend
cp .env.example .env   # configure DATABASE_URL
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py          # or: gunicorn -c gunicorn.conf.py app:app
```

Or from repo root: `node start.js`

## Related documentation

- [Backend documentation](../docs/BACKEND_DOCUMENTATION.md)
- [Technical documentation](../docs/TECHNICAL_DOCUMENTATION.md)
- [Database test script](../scripts/database/test_db_connection.py)
