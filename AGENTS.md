# Agent notes

## Documentation

- **Index:** `docs/README.md` — flat markdown under `docs/` (only subfolder: `user-manual/`).
- **Workflows:** `docs/WORKFLOWS.md`
- **Setup:** `docs/DEVELOPMENT.md`
- **Media storage:** `docs/MEDIA_AND_BACKUPS.md`
- **Document intelligence:** `docs/DOCUMENT_INTELLIGENCE.md`
- **AI:** `docs/AI_WORKFLOW.md`, `docs/AI_DATA_PIPELINE.md`, `docs/ADRS.md`
- **End-user manuals:** `docs/user-manual/`

## Code

- Backend: `apps/backend/` — blueprints registered in `app/bootstrap/create_app.py`
- Frontend: `apps/frontend/`
- **UI theme (centralized):** `apps/frontend/src/core/theme/themeConfig.js` + `ThemeProvider` — do not add parallel theme state; landing dark-only is configured there
- Setup: `docs/DEVELOPMENT.md`
