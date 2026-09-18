# Agent notes

## Documentation

- **Index:** `docs/README.md` — flat markdown under `docs/` (only subfolder: `user-manual/`).
- **App guide:** `docs/GUIDE.md` (architecture, flows, API, data model, integrations)
- **Setup / workflows / production:** `docs/DEVELOPMENT.md`
- **Media storage & backups:** `docs/OPERATIONS.md`
- **AI / document intelligence:** `docs/AI.md`
- **End-user manuals:** `docs/user-manual/`

## Code

- Backend: `apps/backend/` — blueprints registered in `app/bootstrap/create_app.py`
- Frontend: `apps/frontend/`
- **UI theme (centralized):** `apps/frontend/src/core/theme/themeConfig.js` + `ThemeProvider` — do not add parallel theme state; landing dark-only is configured there
- Setup: `docs/DEVELOPMENT.md`
- **Clear caches:** when the user asks to clear cache, run `npm run clear-cache` (logic in `scripts/clear-cache.js`). Do not hand-delete `__pycache__` trees ad hoc.

## Shared Postgres (LAN)

- Permanent databases for this deployment: **`hrms` only** (plus system `postgres`). Do not leave disposable DBs on the shared/LAN host.
- Scratch migration, schema-squash, or isolation work must use **local Docker Postgres** (`infrastructure/docker/docker-compose.yml`) or a throwaway container — not ad-hoc `CREATE DATABASE` / `createdb` on the shared host unless the user explicitly opts in.
- If a disposable DB is created anywhere, **`DROP DATABASE` it before finishing** (use a `finally` / teardown path). Never leave names like `hcip_schema_*` or `task02_isolation_*` behind.
- Refuse ad-hoc `CREATE DATABASE` / migrate / wipe targets against `{hrms}` (and any other production-like DB the user has not named for throwaway use) unless the user explicitly opts in.
