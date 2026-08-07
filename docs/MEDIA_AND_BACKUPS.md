# Media storage & automatic backups

Reference for durable file storage (resumes, JDs, hero video) and backups.
**You do not need to manage paths day to day** — defaults keep data outside the project folder.

---

## Mental model (read this once)

| Layer | What it holds | Survives deleting the project folder? |
|-------|----------------|----------------------------------------|
| **Postgres** | Catalog: ids, filenames, SHA-256 hashes, `storage_url` keys | Yes (if DB host is separate / backed up) |
| **`HCIP_DATA_HOME/media`** | Actual PDF/DOCX/video **bytes** | Yes — this folder is **outside** the repo |
| **`HCIP_DATA_HOME/backups`** | Automatic copies of DB + media | Yes |

Deleting `HR-Intelligence-Platform/` does **not** delete `hcip-data/`.  
Losing **both** `hcip-data` and the database **without** a backup = data loss.

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
  backups/
    20260807_070258/                      ← one backup run
      postgres.dump
      media.tar.gz                        ← present on full backups
      MANIFEST.json
    latest → 20260807_070258              ← pointer / symlink
    LAST_BACKUP
```

Override root with env `HCIP_DATA_HOME` if you want another drive.

---

## Env keys (`apps/backend/.env`)

| Key | Default | Purpose |
|-----|---------|---------|
| `HCIP_DATA_HOME` | `<parent-of-repo>/hcip-data` | Durable root |
| `MEDIA_ROOT` | `$HCIP_DATA_HOME/media` | File bytes |
| `BACKUP_DIR` | `$HCIP_DATA_HOME/backups` | Backup archives |
| `BACKUP_ENABLED` | `true` | App auto-backup scheduler |
| `BACKUP_INTERVAL_HOURS` | `24` | How often (while app is running) |
| `BACKUP_KEEP_DAYS` | `14` | Prune older backup folders |
| `BACKUP_STARTUP_DELAY_SECONDS` | `30` | Wait after boot before first check |
| `PG_DUMP_PATH` | (auto: newest `pg_dump` found) | Must match Postgres **server** major version |
| `BACKUP_PG_DOCKER_IMAGE` | `postgres:17` | Optional Docker fallback for `pg_dump` |

Example (already in `.env.example`):

```bash
# HCIP_DATA_HOME=/mnt/d/Projects/hcip-data
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
BACKUP_KEEP_DAYS=14
# PG_DUMP_PATH=/home/YOU/miniconda3/bin/pg_dump   # if apt pg_dump is too old
```

**Version tip:** server is Postgres 17 → client `pg_dump` must be 17+.  
If you see `server version mismatch`, install a matching client or set `PG_DUMP_PATH`.

---

## Commands cheat sheet

All commands from **`apps/backend`** unless noted. Load `.env` is automatic for these modules.

### 1) Automatic backups (normal use)

With the Flask app running (`node start.js` / `python wsgi.py`):

- Scheduler starts on boot when `BACKUP_ENABLED=true`
- Runs a full backup when the last one is older than `BACKUP_INTERVAL_HOURS`
- Writes under `$HCIP_DATA_HOME/backups/<timestamp>/`

Startup log lines look like:

```text
[MEDIA] DATA_HOME=... MEDIA_ROOT=... BACKUPS=...
[backup] scheduler started (every 24h, first check in 30s)
```

### 2) Manual backup (force now)

```bash
cd apps/backend

# Full: Postgres + media
python -m app.database.scripts.backup_hcip --force

# Database only
python -m app.database.scripts.backup_hcip --force --db-only

# Media volume only
python -m app.database.scripts.backup_hcip --force --media-only
```

### 3) Daily cron (if the app is not always running)

```bash
# From repo root — installs a 02:15 daily job
bash scripts/install_hcip_backup_cron.sh
```

Or add manually:

```cron
15 2 * * * cd /mnt/d/Projects/HR-Intelligence-Platform/apps/backend && python -m app.database.scripts.backup_hcip --force >> /mnt/d/Projects/hcip-data/backups/cron.log 2>&1
```

### 4) Media volume: seed / ensure dirs

```bash
# From repo root
python scripts/ensure_media_assets.py
python scripts/ensure_media_assets.py --force   # re-seed hero from disk
```

### 5) Offload legacy Postgres BYTEA → media (one-time / ongoing)

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

### 6) Alembic (schema), including media catalog columns

```bash
cd apps/backend
alembic upgrade head
alembic current
```

Related revision: `20260807_0012` — `site_assets.content_sha256`.

---

## Restore (disaster recovery)

1. **Restore Postgres** (custom format dump):

```bash
pg_restore --clean --if-exists -h HOST -p PORT -U USER -d hrms \
  /mnt/d/Projects/hcip-data/backups/latest/postgres.dump
```

(Use a matching Postgres 17+ client. Set `PGPASSWORD` or a `.pgpass` file.)

2. **Restore media bytes**:

```bash
# Extract into durable home (creates ./media under the extract dir)
cd /mnt/d/Projects/hcip-data
tar -xzf backups/latest/media.tar.gz
# Ensure apps/backend/.env points at this tree:
#   HCIP_DATA_HOME=/mnt/d/Projects/hcip-data
#   (MEDIA_ROOT defaults to $HCIP_DATA_HOME/media)
```

3. **Verify**:

```bash
cd apps/backend
python -m app.database.scripts.offload_blobs --verify-only --limit 200
```

4. Start the app and confirm resumes download / hero video loads.

---

## What is safe to delete?

| Path | Safe to delete? |
|------|-----------------|
| `HR-Intelligence-Platform/` (the repo) | Yes for **media/backups** — they live in `hcip-data` |
| `HR-Intelligence-Platform/.media` | Yes after migration (see `MOVED.txt` inside) — already copied to `hcip-data/media` |
| `hcip-data/media` | **No** — live files |
| `hcip-data/backups` | Only old dated folders after you confirm newer backups exist |
| Entire `hcip-data/` | **No** unless you have an off-machine copy |

---

## Related code

| Module | Role |
|--------|------|
| `app/core/data_home.py` | Resolves `HCIP_DATA_HOME` |
| `app/core/media_storage.py` | Put/get + SHA-256 verify; migrates legacy `.media` once |
| `app/core/backup_scheduler.py` | Background schedule on Flask boot |
| `app/database/scripts/backup_hcip.py` | Backup CLI |
| `app/database/scripts/offload_blobs.py` | BYTEA → media + verify |
| `scripts/ensure_media_assets.py` | Seed hero / dirs |
| `scripts/install_hcip_backup_cron.sh` | Cron installer |

---

## See also

- [DEVELOPMENT.md](DEVELOPMENT.md) — full local setup  
- [Backend README](../apps/backend/README.md)  
- [Alembic README](../apps/backend/alembic/README.md) — schema migrations  
- [Scripts README](../scripts/README.md)  
