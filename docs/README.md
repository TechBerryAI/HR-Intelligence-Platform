# Documentation

Single entry point for HR Intelligence Platform docs. Prefer live code when docs disagree.

---

## Where to start

| If you are… | Read this |
|-------------|-----------|
| **External team / career page integration** | [external/HR_Intelligence_Platform_Partner_Guide.pdf](external/HR_Intelligence_Platform_Partner_Guide.pdf) · [GUIDE.md](GUIDE.md#career-page-integration) |
| **Engineer onboarding (full app map)** | [GUIDE.md](GUIDE.md) |
| **Engineer (local setup + production)** | [DEVELOPMENT.md](DEVELOPMENT.md) · root [README.md](../README.md) |
| **End user / trainer** | [user-manual/](user-manual/README.md) (Word/PDF) |
| **Media storage & backups** | [OPERATIONS.md](OPERATIONS.md) |
| **AI / document intelligence** | [AI.md](AI.md) |

---

## Layout

```text
docs/
  README.md           ← you are here
  GUIDE.md            ← app architecture, flows, API, data model, integrations
  DEVELOPMENT.md      ← setup, workflows, production release, troubleshooting
  OPERATIONS.md       ← media storage + backup/restore
  AI.md               ← document intelligence, AI features, pipeline, ADRs
  external/           ← partner PDF for other teams
  user-manual/        ← only subfolder (Word/PDF + screenshots + build scripts)
```

---

## User manual

| Format | File |
|--------|------|
| **Word** | [user-manual/HR_Intelligence_Platform_User_Manual.docx](user-manual/HR_Intelligence_Platform_User_Manual.docx) |
| **PDF** | [user-manual/HR_Intelligence_Platform_User_Manual.pdf](user-manual/HR_Intelligence_Platform_User_Manual.pdf) |

Regenerate: [user-manual/README.md](user-manual/README.md).

---

## Runtime source of truth

1. `apps/backend/app/bootstrap/create_app.py` and domain routes  
2. `apps/backend/alembic/` (schema migrations)  
3. `apps/frontend/src/`
