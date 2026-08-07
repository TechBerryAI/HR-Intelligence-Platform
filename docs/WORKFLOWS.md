# Unique workflows

Current operational workflows for the HR Intelligence Platform. Prefer live code when behavior differs.

Related: [DEVELOPMENT.md](DEVELOPMENT.md) · [MEDIA_AND_BACKUPS.md](MEDIA_AND_BACKUPS.md) · [DOCUMENT_INTELLIGENCE.md](DOCUMENT_INTELLIGENCE.md) · [AI_WORKFLOW.md](AI_WORKFLOW.md)

---

## Local app (dev)

```bash
# From repo root — installs deps, starts Flask :3000 + Vite :5173
node start.js
```

Details: [DEVELOPMENT.md](DEVELOPMENT.md).

---

## Media & backups

Hero video, resume/JD blobs, and volume backups:

→ **[MEDIA_AND_BACKUPS.md](MEDIA_AND_BACKUPS.md)**

```bash
python scripts/ensure_media_assets.py
# overwrite DB hero from disk:
python scripts/ensure_media_assets.py --force
```

Landing video is served from Postgres `site_assets` via `GET /api/media/public/hero-video` (optional `VITE_HERO_VIDEO_URL` CDN override).

---

## Schema / database

- Canonical SQL: `apps/backend/schema_pg/` (`01_core` … `04_seeds`)
- Apply via Alembic: `alembic upgrade head` (from `apps/backend`)
- New changes: `alembic revision` only — do not add numbered SQL files

Preflight: `node scripts/db-preflight.js`

---

## Resume / JD parse (Document Intelligence)

Pipeline:

```
Document → Extraction → Layout → Sections → Parsers
  → Canonical → Knowledge → Validation → Form DTO → Frontend
  → Canonical→TOON → DB/ATS
```

- Entry: `app.ai.document_intelligence.pipeline.run_document_intelligence`
- APIs: `domains/recruitment/api/parsing.py`
- Frontend: Form DTOs only (`takeResumeFormDTO` / `takeJDFormDTO`)

Full notes + eval commands: [DOCUMENT_INTELLIGENCE.md](DOCUMENT_INTELLIGENCE.md)

---

## Interview scheduling (Google Calendar)

1. Recruiter connects Google OAuth (`oauth_tokens.hrid`)
2. On Shortlisted → `InterviewSchedulingService` creates slots + booking email
3. Candidate books via public `GET/POST /api/interviews/book/<token>`
4. Application status → `Interview`

Schema: `interviews`, `interview_slots` (see `schema_pg/`).

---

## AI platform (dataset / train / eval)

→ **[AI_WORKFLOW.md](AI_WORKFLOW.md)** · **[AI_DATA_PIPELINE.md](AI_DATA_PIPELINE.md)** · **[ADRS.md](ADRS.md)**

---

## User manuals

Screenshot manuals (Word/PDF): [user-manual/](user-manual/README.md)
