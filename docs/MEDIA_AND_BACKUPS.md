# Media storage

Reference for durable file storage (resumes, JDs, hero video).
**You do not need to manage paths day to day** — defaults keep data outside the project folder.

Postgres backups are owned by the **database team** — this app does not dump or archive the DB.

**Operator runbook:** concrete `pg_dump` + `MEDIA_ROOT` rsync and restore steps → [BACKUP_RUNBOOK.md](BACKUP_RUNBOOK.md).

---

## Mental model (read this once)

| Layer | What it holds | Survives deleting the project folder? |
|-------|----------------|----------------------------------------|
| **Postgres** | Catalog: ids, filenames, SHA-256 hashes, `storage_url` keys | Yes (if DB host is separate / backed up by DB team) |
| **`HCIP_DATA_HOME/media`** | Actual PDF/DOCX/video **bytes** | Yes — this folder is **outside** the repo |

Deleting `HR-Intelligence-Platform/` does **not** delete `hcip-data/`.  
Losing **both** `hcip-data` and the database without a restore path = data loss.

---

## Default layout on this machine

Repo at `D:/Projects/HR-Intelligence-Platform` (WSL: `/mnt/d/Projects/HR-Intelligence-Platform`):

```text
D:/Projects/HR-Intelligence-Platform/     ← git / code (safe to delete/reclone)
D:/Projects/hcip-data/                    ← durable data (KEEP)
  media/                                  ← MEDIA_ROOT (resumes, JDs, hero, …)
    uploads/
    feedback/
    bulk_uploads/
    bulk_exports/
    public/
```

Override root with env `HCIP_DATA_HOME` if you want another drive.

---

## Env keys (`apps/backend/.env`)

| Key | Default | Purpose |
|-----|---------|---------|
| `HCIP_DATA_HOME` | `<parent-of-repo>/hcip-data` | Durable root |
| `MEDIA_ROOT` | `$HCIP_DATA_HOME/media` | File bytes |

Example (already in `.env.example`):

```bash
# HCIP_DATA_HOME=/mnt/d/Projects/hcip-data
```

---

## Commands cheat sheet

All commands from **`apps/backend`** unless noted. Load `.env` is automatic for these modules.

### 1) Media volume: seed / ensure dirs

```bash
# From repo root
python scripts/ensure_media_assets.py
python scripts/ensure_media_assets.py --force   # re-seed hero from disk
```

### 2) Offload legacy Postgres BYTEA → media (one-time / ongoing)

New uploads already write to media. Use this for old rows still holding `file_data` / profile `resume` BYTEA:

```bash
cd apps/backend

# Copy BYTEA → MEDIA_ROOT (keep BYTEA for safety)
python -m app.database.scripts.offload_blobs --limit 500

# Rewrite old file:// Windows paths → media: keys
python -m app.database.scripts.offload_blobs --normalize-keys --limit 500

# Audit: catalog hash vs on-disk file
python -m app.database.scripts.offload_blobs --verify-only --limit 500

# After verify is clean — NULL out BYTEA (shrinks DB / faster dumps)
python -m app.database.scripts.offload_blobs --clear-pg --limit 500
```

### 3) Alembic (schema), including media catalog columns

```bash
cd apps/backend
alembic upgrade head
alembic current
```

Schema includes `site_assets.content_sha256` (media-volume verification) in the squashed baseline `20260810_s001`.

---

## Landing hero video (VM / fresh clone)

The seed MP4 is **committed** at `apps/frontend/public/videos/website-hero.mp4`.
On boot (and on `/api/media/public/hero-video` / health), the app copies it to
`$MEDIA_ROOT/public/website-hero.mp4` and upserts the Postgres `site_assets`
catalog row (`landing.hero_video`). Runtime bytes stay on `MEDIA_ROOT`; the
catalog holds metadata + SHA-256 (not BYTEA).

**Resolve order:**

1. `$MEDIA_ROOT/public/website-hero.mp4` (canonical runtime file)
2. Else copy from `apps/frontend/public/videos/website-hero.mp4` (in-repo seed)
3. Upsert `site_assets` so `storage_url` points at that canonical file

**On a VM after `git pull`:**

```bash
# Pull includes the seed; start the backend (auto-seeds) or run:
cd /path/to/HR-Intelligence-Platform
python scripts/ensure_media_assets.py

curl -s http://localhost:<backend-port>/api/media/health
# expect heroVideoDisk / heroVideoDb true
```

Optional: `python scripts/ensure_media_assets.py --force` rewrites the catalog
from the current disk/seed file.

---

## What is safe to delete?

| Path | Safe to delete? |
|------|-----------------|
| `HR-Intelligence-Platform/` (the repo) | Yes for **media** — it lives in `hcip-data` |
| `HR-Intelligence-Platform/.media` | Yes after migration (see `MOVED.txt` inside) — already copied to `hcip-data/media` |
| `hcip-data/media` | **No** — live files |
| Entire `hcip-data/` | **No** unless you have an off-machine copy of media |

---

## Related code

| Module | Role |
|--------|------|
| `app/core/data_home.py` | Resolves `HCIP_DATA_HOME` |
| `app/core/media_storage.py` | Put/get + SHA-256 verify; migrates legacy `.media` once |
| `app/database/scripts/offload_blobs.py` | BYTEA → media + verify |
| `scripts/ensure_media_assets.py` | Seed hero / dirs |

---

## See also

- [DEVELOPMENT.md](DEVELOPMENT.md) — full local setup  
- [Backend README](../apps/backend/README.md)  
- [Alembic README](../apps/backend/alembic/README.md) — schema migrations  
- [Scripts README](../scripts/README.md)  
