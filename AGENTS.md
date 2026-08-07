# Agent notes (HCIP)

## Documentation

- Product SoT: `docs/01-Product-Constitution.md` and `docs/01`–`10`.
- When changing APIs, schema, workflows, RBAC, or UI behavior, update matching docs (see `.cursor/rules/documentation-sync.mdc`).
- After route or `schema_pg` changes, run: `python scripts/sync_docs_from_code.py`
- Do not treat `docs/legacy/` as current product truth.
- Local setup: `docs/DEVELOPMENT.md`.
- Media + backups (commands): `docs/MEDIA_AND_BACKUPS.md`.
- Docs index: `docs/README.md`.

## Code

- Backend: `apps/backend/` — blueprints registered in `app/bootstrap/create_app.py`
- Frontend: `apps/frontend/`
- **UI theme (centralized):** `apps/frontend/src/core/theme/themeConfig.js` + `ThemeProvider` — do not add parallel theme state; landing dark-only is configured there
- Setup: `docs/DEVELOPMENT.md`
