# Documentation

Single entry point for HR Intelligence Platform docs. Prefer live code when docs disagree.

---

## Where to start

| If you are… | Read this |
|-------------|-----------|
| **End user / trainer** | [user-manual/](user-manual/README.md) (Word/PDF) |
| **Engineer (local setup)** | [DEVELOPMENT.md](DEVELOPMENT.md) · root [README.md](../README.md) |
| **Production release** | [PRODUCTION_RELEASE.md](PRODUCTION_RELEASE.md) |
| **Workflows** | [WORKFLOWS.md](WORKFLOWS.md) |
| **Media storage** | [MEDIA_AND_BACKUPS.md](MEDIA_AND_BACKUPS.md) · [BACKUP_RUNBOOK.md](BACKUP_RUNBOOK.md) |
| **Document intelligence** | [DOCUMENT_INTELLIGENCE.md](DOCUMENT_INTELLIGENCE.md) |
| **AI workflows** | [AI_WORKFLOW.md](AI_WORKFLOW.md) · [AI_DATA_PIPELINE.md](AI_DATA_PIPELINE.md) · [ADRS.md](ADRS.md) |

---

## Layout

```text
docs/
  README.md
  WORKFLOWS.md
  DEVELOPMENT.md
  PRODUCTION_RELEASE.md
  MEDIA_AND_BACKUPS.md
  BACKUP_RUNBOOK.md
  DOCUMENT_INTELLIGENCE.md
  AI_WORKFLOW.md
  AI_DATA_PIPELINE.md
  ADRS.md
  user-manual/          ← only subfolder (Word/PDF + screenshots + build scripts)
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
