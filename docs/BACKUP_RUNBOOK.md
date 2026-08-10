# Backup & restore runbook

Concrete steps for Postgres dumps and `MEDIA_ROOT` file copies. Media layout and env keys: [MEDIA_AND_BACKUPS.md](MEDIA_AND_BACKUPS.md).

Defaults assume WSL/Linux and durable data at `/mnt/d/Projects/hcip-data` (override with `HCIP_DATA_HOME` / `MEDIA_ROOT`).

---

## Prerequisites

- Load DB credentials from `apps/backend/.env` (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, or `PG*` equivalents).
- Resolve media root: `$MEDIA_ROOT` or `$HCIP_DATA_HOME/media`.

```bash
# Example env for this session
export PGHOST="${POSTGRES_HOST:-localhost}"
export PGPORT="${POSTGRES_PORT:-5432}"
export PGDATABASE="${POSTGRES_DB:-postgres}"
export PGUSER="${POSTGRES_USER:-postgres}"
# export PGPASSWORD=...   # or use .pgpass
export MEDIA_ROOT="${MEDIA_ROOT:-/mnt/d/Projects/hcip-data/media}"
export BACKUP_DIR="${BACKUP_DIR:-/mnt/d/Projects/hcip-backups/$(date +%Y%m%d)}"
mkdir -p "$BACKUP_DIR"
```

---

## 1) Postgres dump

```bash
pg_dump -Fc -f "$BACKUP_DIR/hcip.dump" "$PGDATABASE"
# Plain SQL alternative:
# pg_dump -f "$BACKUP_DIR/hcip.sql" "$PGDATABASE"
```

Verify:

```bash
pg_restore -l "$BACKUP_DIR/hcip.dump" | head
```

---

## 2) MEDIA_ROOT rsync

```bash
rsync -aH --info=stats2 "$MEDIA_ROOT/" "$BACKUP_DIR/media/"
```

Optional dry-run first: `rsync -aHn …`.

---

## 3) Restore notes

**Order:** restore Postgres, then media (or media first if the DB is still live and you only need files). Catalog rows (`storage_url`, hashes) must match files under `MEDIA_ROOT`.

### Postgres

```bash
# Custom-format dump
pg_restore --clean --if-exists -d "$PGDATABASE" "$BACKUP_DIR/hcip.dump"
# Or for plain SQL:
# psql -d "$PGDATABASE" -f "$BACKUP_DIR/hcip.sql"
```

Schema-only upgrades after restore: `cd apps/backend && alembic upgrade head`.

### Media

```bash
# Stop writers (Flask) if possible, then:
rsync -aH "$BACKUP_DIR/media/" "$MEDIA_ROOT/"
```

Spot-check:

```bash
curl -s http://localhost:<backend-port>/api/media/health
# expect hero / disk flags healthy when applicable
```

### Consistency

- Prefer dumps taken while uploads are quiet, or accept that in-flight uploads may be missing from either DB or disk.
- After BYTEA offload (`offload_blobs`), DB size shrinks; **media backup becomes mandatory** for file recovery.
- Losing `hcip-data` without this rsync copy = irreversible file loss even if Postgres is fine.

---

## See also

- [MEDIA_AND_BACKUPS.md](MEDIA_AND_BACKUPS.md) — layout, offload, hero seed  
- [DEVELOPMENT.md](DEVELOPMENT.md) — local env  
