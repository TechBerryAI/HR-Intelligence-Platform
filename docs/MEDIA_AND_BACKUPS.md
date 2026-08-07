# Media storage

Reference for durable file storage (resumes, JDs, hero video).
**You do not need to manage paths day to day** — defaults keep data outside the project folder.

Postgres backups are owned by the **database team** — this app does not dump or archive the DB.

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

Related revision: `20260807_0012` — `site_assets.content_sha256`.

---

## Landing hero video (VM / fresh clone)

Hero is **not** in Git by default. Bytes live under `MEDIA_ROOT` (and a `site_assets` catalog row).

**Seed path the app looks for:**

1. `$MEDIA_ROOT/public/website-hero.mp4`
2. Else once from `apps/frontend/public/videos/website-hero.mp4` (if present)

**On a VM after `git pull`:**

```bash
# 1) Copy the MP4 onto the VM (scp / shared drive / etc.)
mkdir -p "$HCIP_DATA_HOME/media/public"   # or rely on default …/hcip-data/media
cp website-hero.mp4 "$HCIP_DATA_HOME/media/public/website-hero.mp4"

# 2) Seed catalog + verify
cd /path/to/HR-Intelligence-Platform
python scripts/ensure_media_assets.py --force

# 3) Health check
curl -s http://localhost:<backend-port>/api/media/health
# expect heroVideoDisk / heroVideoDb true
```

Alternatively commit `apps/frontend/public/videos/website-hero.mp4` so every clone can auto-seed on app boot.

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
