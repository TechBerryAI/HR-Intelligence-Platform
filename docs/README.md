# Documentation

End-user manuals and local engineering notes for the HR Intelligence Platform.

---

## Where to start

| If you are… | Read this |
|-------------|-----------|
| **End user / trainer** | [user-manual/HR_Intelligence_Platform_User_Manual.docx](user-manual/HR_Intelligence_Platform_User_Manual.docx) / [PDF](user-manual/HR_Intelligence_Platform_User_Manual.pdf) |
| **Engineer (local setup)** | [DEVELOPMENT.md](DEVELOPMENT.md) · root [README.md](../README.md) |
| **Deep architecture (archive)** | [ARCHITECTURE.md](ARCHITECTURE.md) · [ENGINEERING.md](ENGINEERING.md) |
| **Sprint / migration history** | [HISTORY.md](HISTORY.md) |
| **Document intelligence notes** | [document_intelligence/](document_intelligence/) |

---

## Layout

```text
docs/
  README.md                 ← you are here
  DEVELOPMENT.md            ← local setup
  user-manual/              ← screenshot manuals (Word + PDF)
  ARCHITECTURE.md           ← historical deep dive (optional)
  ENGINEERING.md            ← historical API/module narrative (optional)
  HISTORY.md                ← sprint / migration notes (optional)
  document_intelligence/    ← parsing / DI notes
```

---

## User manual (primary)

| Format | File |
|--------|------|
| **Word** | [user-manual/HR_Intelligence_Platform_User_Manual.docx](user-manual/HR_Intelligence_Platform_User_Manual.docx) |
| **PDF** | [user-manual/HR_Intelligence_Platform_User_Manual.pdf](user-manual/HR_Intelligence_Platform_User_Manual.pdf) |

Regenerate: [user-manual/README.md](user-manual/README.md).

---

## Runtime source of truth

For APIs, schema, and behavior, prefer the live code:

1. `apps/backend/app/bootstrap/create_app.py` and domain routes  
2. `apps/backend/schema_pg/`  
3. `apps/frontend/src/`  

Narrative archives under `ARCHITECTURE.md` / `ENGINEERING.md` are optional reading when they disagree with code.
