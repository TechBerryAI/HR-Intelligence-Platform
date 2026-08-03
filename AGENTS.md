# Agent notes (HCIP)

## Documentation

- Product SoT: `docs/01-Product-Constitution.md` and `docs/01`–`10`.
- When changing APIs, schema, workflows, RBAC, or UI behavior, update matching docs (see `.cursor/rules/documentation-sync.mdc`).
- After route or `schema_pg` changes, run: `python scripts/sync_docs_from_code.py`
- Do not treat `docs/legacy/` as current product truth.

## Code

- Backend: `apps/backend/` — blueprints registered in `app/bootstrap/create_app.py`
- Frontend: `apps/frontend/`
- Setup: `docs/DEVELOPMENT.md`
