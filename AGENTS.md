# Agent notes

## Documentation

- End-user manuals: `docs/user-manual/` (Word/PDF with live screenshots).
- Local setup: `docs/DEVELOPMENT.md`.
- Media + backups (commands): `docs/MEDIA_AND_BACKUPS.md`.
- Docs index: `docs/README.md`.
- Prefer live code over `docs/ARCHITECTURE.md` / `docs/ENGINEERING.md` when they disagree.

## Code

- Backend: `apps/backend/` — blueprints registered in `app/bootstrap/create_app.py`
- Frontend: `apps/frontend/`
- **UI theme (centralized):** `apps/frontend/src/core/theme/themeConfig.js` + `ThemeProvider` — do not add parallel theme state; landing dark-only is configured there
- Setup: `docs/DEVELOPMENT.md`
