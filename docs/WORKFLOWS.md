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

## Media storage

Hero video and resume/JD blobs:

→ **[MEDIA_AND_BACKUPS.md](MEDIA_AND_BACKUPS.md)**

```bash
python scripts/ensure_media_assets.py
# overwrite DB hero from disk:
python scripts/ensure_media_assets.py --force
```

Landing video is streamed from `MEDIA_ROOT` (catalog in Postgres `site_assets`) via `GET /api/media/public/hero-video`. Seed file is in-repo at `apps/frontend/public/videos/website-hero.mp4` (optional `VITE_HERO_VIDEO_URL` CDN override).

---

## Schema / database

- Source of truth: Alembic (`apps/backend/alembic/`)
- Apply: `alembic upgrade head` (from `apps/backend`)
- New changes: `alembic revision` only — do not add parallel SQL schema trees

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

Schema: `interviews`, `interview_slots` (see Alembic baseline / live DB).

---

## AI platform (dataset / train / eval)

→ **[AI_WORKFLOW.md](AI_WORKFLOW.md)** · **[AI_DATA_PIPELINE.md](AI_DATA_PIPELINE.md)** · **[ADRS.md](ADRS.md)**

---

## User manuals

Screenshot manuals (Word/PDF): [user-manual/](user-manual/README.md)
