# Repository Migration Tracker

Incremental migration to a domain-driven modular monolith layout.

## Status: Complete

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Scaffold `apps/backend/app/` + `create_app` factory | Complete |
| 1 | Foundation (db, config, core auth, rbac) | Complete |
| 2 | Identity domain | Complete |
| 3 | Candidate domain | Complete |
| 4 | Recruitment domain | Complete |
| 5 | Administration domain | Complete |
| 6 | Support + employee + email integrations | Complete |
| 7 | Backend tests → `tests/backend/` | Complete |
| 8 | Frontend feature-sliced restructure | Complete |
| 9 | Relocate to `apps/` | Complete |
| 10 | `packages/` shims for `ai/` | Complete |
| 11 | Docs + infrastructure scaffolding | Complete |

## Layout

```
apps/
  backend/     Flask modular monolith (app/domains/*)
  frontend/    React SPA (src/features/*, src/core/*)
  desktop/     Electron shell
packages/
  ontology/    shim → ai/contracts, ai/schemas, ai/toon
  knowledge/   shim → ai/knowledge
  ai-runtime/  shim → ai/runtime
  shared/      cross-app constants
ai/            AI platform (unchanged source of truth)
tests/
  backend/     Python unit tests
infrastructure/
  docker/      docker-compose for PostgreSQL
  ci/          GitHub Actions workflow template
docs/
  adr/         Architecture decision records
```

## Entry points

| Command | Location |
|---------|----------|
| `node start.js` | Repo root — starts backend + frontend |
| `python wsgi.py` | `apps/backend/` — Flask dev server |
| `gunicorn wsgi:app` | `apps/backend/` — production WSGI |
| `npm run dev` | `apps/frontend/` — Vite dev server |
| `npm run electron` | Repo root — desktop app |

## Compatibility

Use `apps/backend`, `apps/frontend`, and `apps/desktop` as the only app locations.
Root-level `backend` / `frontend` / `electron` symlinks were removed to avoid duplicate folders in the IDE.
Legacy `apps/backend/*.py` shims re-export from `app.*` package modules.
