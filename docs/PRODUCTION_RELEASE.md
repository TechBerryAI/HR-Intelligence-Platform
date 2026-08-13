# Production release procedure

Repeatable host-process release for the HR Intelligence Platform. Does **not** require Docker, Kubernetes, or systemd — use those if you already operate them, or run the same commands under any supervisor.

Local development remains `node start.js` (Flask). That is **not** the production starter.

Related: [DEVELOPMENT.md](DEVELOPMENT.md) · [WORKFLOWS.md](WORKFLOWS.md) · [BACKUP_RUNBOOK.md](BACKUP_RUNBOOK.md)

---

## Roles

| Role | Command (from `apps/backend`) | Migrations |
|------|-------------------------------|------------|
| Migrate | `alembic upgrade head` **once**, or Gunicorn master `on_starting` | Once |
| Web | `gunicorn -c gunicorn.conf.py wsgi:app` | Workers skip (`HCIP_MIGRATIONS_DONE=1`) |
| Scheduler | `RUN_INTEGRATION_AUTO_SYNC=1 python -m app.domains.integrations.scheduler` | None |
| Outbox | `python -m app.domains.integrations.worker` (optional dedicated drain) | None |

Web workers also drain the durable outbox via `FOR UPDATE SKIP LOCKED` + leases. A dedicated outbox process is extra capacity, not a second schema manager.

**Never** start Gunicorn without `-c gunicorn.conf.py`. Without the config, every worker runs `init_db()` and can race DDL.

---

## Environment (no secrets in this doc)

Production-like = `FLASK_DEBUG=false` and `ALLOW_INSECURE_JWT` off. Gunicorn and production refuse to start otherwise.

Required:

- `FLASK_DEBUG=false`
- `DEVELOPER_MODE=false`
- Unique `JWT_SECRET` (≥32 chars, not the `.env.example` placeholder)
- `INTEGRATION_SECRETS_KEY` (not `dev-integration-secrets`)
- Postgres (`DATABASE_URL` or `POSTGRES_*`)

Recommended (not a startup hard-fail): `FRONTEND_URL` / `FRONTEND_URLS` for CORS and booking links.

When `GUNICORN_WORKERS>1` **and** Google Calendar OAuth is configured, `REDIS_URL` is required and must ping. If `REDIS_URL` is set in production, ping must succeed (no silent in-memory fallback).

AI parse: `OLLAMA_MODEL=qwen2.5:14b-instruct`, `AI_RUNTIME_CONFIG=ai/runtime/config/runtime.production.yaml`, Ollama reachable at `OLLAMA_HOST`.

Optional labels for `pg_stat_activity`:

- `HCIP_PROCESS_ROLE` — `web` / `scheduler` / `outbox` / `migrate` (set automatically by the entrypoints above)
- `HCIP_RELEASE_ID` — short release id (appears in `application_name`)

Do not run `scripts/ensure_media_assets.py` or `scripts/backfill_raw_file_blobs.py` against a live release database concurrently with Gunicorn (they call `init_db()`).

Copy knobs from `apps/backend/.env.example`. Never commit `.env`.

---

## Sequence

### 1. Stop the previous release cleanly

Stop Gunicorn, the scheduler, and any dedicated outbox process (SIGTERM). Wait until they are gone:

```bash
ss -ltnp | grep -E ':3000|:5173' || true
pgrep -a -f 'gunicorn|integrations.scheduler|integrations.worker|wsgi.py' || true
```

`node start.js` only SIGTERMs port 3000 and does not wait. That is insufficient for production.

### 2. Verify no stale application process remains

On the database:

```sql
SELECT pid, client_addr, application_name, usename, backend_start, state,
       left(query, 80) AS query
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY backend_start;
```

This release sets `application_name` to `hcip-<role>[-<HCIP_RELEASE_ID>]`. Sessions with empty `application_name` or a foreign `client_addr` are **other processes**. Stop them on those hosts before continuing. This tree will not rewrite `alembic_version` for an unknown revision in production; an old checkout with `FLASK_DEBUG=true` still can.

### 3. Deploy this application revision

Replace the code tree (rsync, package, or git checkout). Keep the production env file out of the repo.

### 4. Validate required production environment variables

```bash
cd apps/backend
# FLASK_DEBUG=false DEVELOPER_MODE=false … as in the production env
python -c "from app.config.env_validator import EnvValidator; raise SystemExit(0 if EnvValidator.print_report() else 1)"
```

### 5. Run database migrations ONCE

```bash
cd apps/backend
export HCIP_PROCESS_ROLE=migrate
alembic upgrade head
```

Do not `alembic stamp head`. Do not `alembic downgrade` as part of release. Concurrent `upgrade head` is serialized with a Postgres advisory lock.

### 6. Verify revision

```bash
cd apps/backend
alembic current
alembic heads
```

`current` must equal `heads` (today: `20260812_ext_outbox`).

### 7. Start dependencies

- PostgreSQL (required)
- Redis — when required by the rules above
- Ollama — when AI parse is enabled (`ollama serve`; model `qwen2.5:14b-instruct`)

### 8. Start the web service

```bash
cd apps/backend
export FLASK_DEBUG=false DEVELOPER_MODE=false
export GUNICORN_WORKERS=2   # or 4
gunicorn -c gunicorn.conf.py wsgi:app
```

The master validates env and runs `upgrade head` once. Workers do not migrate.

### 9. Start exactly one scheduler

```bash
cd apps/backend
RUN_INTEGRATION_AUTO_SYNC=1 python -m app.domains.integrations.scheduler
```

Do **not** set `RUN_INTEGRATION_AUTO_SYNC` on Gunicorn workers. A second scheduler is idle (advisory lock); still run only one.

### 10. Start the outbox worker role (optional dedicated)

```bash
cd apps/backend
python -m app.domains.integrations.worker
```

Safe with in-worker drain (SKIP LOCKED + `leased_until`).

### 11. Verify health

```bash
curl -sS http://127.0.0.1:3000/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/ready
```

`/ready` must be 200 only when Postgres answers `SELECT 1`. `/health` reports postgres/redis/ollama checks and worker `pid`.

### 12. Production smoke

- Login / JWT (not Redis-dependent)
- `/health` pid diversity with `GUNICORN_WORKERS=2`
- Resume parse against Ollama 14b (if AI enabled)
- Confirm `alembic current` still equals head after a SIGTERM restart

---

## Stale-writer cleanup (when `pg_stat_activity` shows foreign clients)

1. Note `client_addr`, `pid`, `application_name`, `backend_start`.
2. On that host: stop Gunicorn / Flask / `start.js` / scheduler / outbox / leftover `python wsgi.py`.
3. Re-query `pg_stat_activity` until only this release’s `hcip-*` sessions remain.
4. `alembic current` / `alembic heads` — must match.
5. `alembic upgrade head` (idempotent).
6. Start this release; verify; SIGTERM; start again; verify again.

This WSL host cannot stop processes on other LAN IPs. Do not invent an in-app workaround that hides foreign writers.

---

## LinkedIn / Naukri

Out of scope for internal production readiness. Adapters stay fail-closed until provider access exists.
