# Production release procedure

Repeatable host-process release for the HR Intelligence Platform. Does **not** require Docker, Kubernetes, or systemd — use those if you already operate them, or run the same commands under any supervisor.

Local development remains `node start.js` (Flask). That is **not** the production starter.

Related: [DEVELOPMENT.md](DEVELOPMENT.md) · [WORKFLOWS.md](WORKFLOWS.md) · [BACKUP_RUNBOOK.md](BACKUP_RUNBOOK.md)

Helper (no secrets): `scripts/release-verify.sh pre-deploy` / `post-start` / `db-sessions`.

---

## Roles

| Role | Command (from `apps/backend`) | Migrations |
|------|-------------------------------|------------|
| Migrate | `HCIP_PROCESS_ROLE=migrate alembic upgrade head` **once** | The only production mutator |
| Web | `MIGRATIONS_ALREADY_APPLIED=true gunicorn -c gunicorn.conf.py wsgi:app` | Verify `current == head` only |
| Scheduler | `RUN_INTEGRATION_AUTO_SYNC=1 python -m app.domains.integrations.scheduler` | None |
| Outbox | `python -m app.domains.integrations.worker` (optional dedicated drain) | None |

Web workers also drain the durable outbox via `FOR UPDATE SKIP LOCKED` + leases. A dedicated outbox process is extra capacity, not a second schema manager.

Production web processes **never** run `alembic upgrade head`. `python wsgi.py` is refused when `FLASK_DEBUG` is off. Starting Gunicorn without `-c gunicorn.conf.py` in production fails closed unless `MIGRATIONS_ALREADY_APPLIED=true` (still verify-only; do not use that as a substitute for `-c`).

Do **not** run `scripts/ensure_media_assets.py` or `scripts/backfill_raw_file_blobs.py` against a live release database concurrently with Gunicorn (they call `init_db()`).

---

## Environment (no secrets in this doc)

Production-like = `FLASK_DEBUG=false` and `ALLOW_INSECURE_JWT` off. Gunicorn and production refuse to start otherwise.

Required:

- `FLASK_DEBUG=false`
- `DEVELOPER_MODE=false`
- Unique `JWT_SECRET` (≥32 chars, not the `.env.example` placeholder)
- `INTEGRATION_SECRETS_KEY` (not `dev-integration-secrets`)
- Postgres (`DATABASE_URL` or `POSTGRES_*`)
- `MIGRATIONS_ALREADY_APPLIED=true` on the web process after migrate+verify

Recommended (not a startup hard-fail): `FRONTEND_URL` / `FRONTEND_URLS` for CORS and booking links.

When `GUNICORN_WORKERS>1` in production, `REDIS_URL` is required and must ping (cross-worker parse join; Gunicorn default is 4). Set `GUNICORN_WORKERS=1` if you are not running Redis. If `REDIS_URL` is set, ping must succeed (no silent in-memory fallback). Use `redis://:URL_ENCODED_PASSWORD@host:6379/0` — percent-encode special characters in the password (`/` → `%2F`). The application also canonicalizes unencoded passwords; do not log the URL. The parse owner renews its SET NX lease until completion so a healthy request is not stolen at 180s. Behind nginx/Caddy set `TRUST_PROXY_HEADERS=true`. `GET /ready` includes Redis when `REDIS_URL` is set.

AI parse: leave `OLLAMA_MODEL` unset for hardware-adaptive selection, or pin it explicitly. Runtime YAML: `AI_RUNTIME_CONFIG=ai/runtime/config/runtime.production.yaml`. Ollama reachable at `OLLAMA_HOST`. Residual fill timeout: `DOCUMENT_INTELLIGENCE_SEMANTIC_TIMEOUT_SEC` (default 90).

Optional labels for `pg_stat_activity`:

- `HCIP_PROCESS_ROLE` — `web` / `scheduler` / `outbox` / `migrate` (each entrypoint **forces** its role so a leftover `HCIP_PROCESS_ROLE=migrate` in the same shell cannot relabel web/scheduler/outbox)
- `HCIP_RELEASE_ID` — short release id (appears in `application_name`)

Copy knobs from `apps/backend/.env.example`. Never commit `.env`.

Python **3.10+** is required; **3.11** is recommended (CI). Production installs should use the tested pin set:

```bash
cd apps/backend
pip install -r requirements.lock.txt
```

Do not `pip install -r requirements.txt` on a production host if the lockfile is present — open `>=` constraints can resolve newer packages than those tested.

---

## Sequence

### PRE-DEPLOY

#### 1. Identify current release processes

```bash
ss -ltnp | grep -E ':3000|:5173' || true
pgrep -a -f 'gunicorn|integrations.scheduler|integrations.worker|wsgi.py' || true
```

`node start.js` only SIGTERMs port 3000 and does not wait. That is insufficient for production.

#### 2. Stop the old web service

SIGTERM Gunicorn. Wait until it is gone.

#### 3. Stop the old scheduler

SIGTERM `python -m app.domains.integrations.scheduler`.

#### 4. Stop the old dedicated outbox worker

SIGTERM `python -m app.domains.integrations.worker` if it was started.

#### 5. Confirm processes terminated and inspect database connections

```bash
scripts/release-verify.sh pre-deploy
scripts/release-verify.sh db-sessions
```

`pre-deploy` confirms this host has no leftover gunicorn / scheduler / outbox / `wsgi.py` and that `alembic current == heads`.

`db-sessions` is read-only. It reports `application_name`, `client_addr`, backend PID, truncated query, long-running transactions, and locks. It never terminates backends and never prints secrets. Unknown (non-`hcip-*`) client sessions fail the check (use `--report-only` to print without failing).

This release sets `application_name` to `hcip-<role>[-<HCIP_RELEASE_ID>]`. Sessions with empty `application_name` or a foreign `client_addr` are **other processes**. **Stop. Do not continue the deploy** until those processes are stopped on their hosts. This tree cannot SIGTERM remote PIDs and will not rewrite `alembic_version` for an unknown revision in production.

Manual equivalent (SELECT only):

```sql
SELECT pid, client_addr, application_name, usename, backend_start, state,
       left(query, 80) AS query
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY backend_start;
```

### DEPLOY

#### 6. Deploy this application revision

Replace the code tree (rsync, package, or git checkout). Keep the production env file out of the repo.

Take a pre-migration backup before step 8. Procedure: [BACKUP_RUNBOOK.md](BACKUP_RUNBOOK.md). Schema changes are forward-only; the backup is the only supported way to restore a previous schema.

#### 7. Validate required production environment variables

```bash
cd apps/backend
# FLASK_DEBUG=false DEVELOPER_MODE=false … as in the production env
python -c "from app.config.env_validator import EnvValidator; raise SystemExit(0 if EnvValidator.print_report() else 1)"
```

#### 8. Run database migrations ONCE

```bash
cd apps/backend
export HCIP_PROCESS_ROLE=migrate
alembic upgrade head
```

Do not `alembic stamp head`. Do not `alembic downgrade` as part of release. Concurrent `upgrade head` is serialized with a Postgres advisory lock (`872014002`). Do not add a second lock.

#### 9. Verify revision

```bash
cd apps/backend
alembic current
alembic heads
```

`current` must equal `heads` (today: `20260814_cid_pad3`). `scripts/release-verify.sh pre-deploy` also checks this.

### START

Export `MIGRATIONS_ALREADY_APPLIED=true` (or set it in the production env).

#### 10. Start the web service

```bash
cd apps/backend
export FLASK_DEBUG=false DEVELOPER_MODE=false
export MIGRATIONS_ALREADY_APPLIED=true
export GUNICORN_WORKERS=2   # or 4
gunicorn -c gunicorn.conf.py wsgi:app
```

The master validates env and **verifies** schema at head. Workers do not migrate. Logs must not contain `[DB] Alembic upgrade head complete` from web processes.

#### 11. Start exactly one scheduler

```bash
cd apps/backend
RUN_INTEGRATION_AUTO_SYNC=1 python -m app.domains.integrations.scheduler
```

Do **not** set `RUN_INTEGRATION_AUTO_SYNC` on Gunicorn workers. A second scheduler is idle (advisory lock); still run only one.

#### 12. Start the outbox worker role (optional dedicated)

```bash
cd apps/backend
python -m app.domains.integrations.worker
```

Safe with in-worker drain (SKIP LOCKED + `leased_until`).

#### 13. Verify health

```bash
scripts/release-verify.sh post-start
# or:
curl -sS http://127.0.0.1:3000/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/ready
```

`/ready` must be 200 when Postgres answers `SELECT 1`, and Redis is `ok` when `REDIS_URL` is set. `/health` is liveness (always 200 plus checks).

### POST-DEPLOY

#### 14. Verify expected database connections

```bash
scripts/release-verify.sh db-sessions --report-only
```

Expect `hcip-web` (one per worker), `hcip-scheduler`, and optional `hcip-outbox`. No leftover writers from the previous release on this host. Unknown `client_addr` / empty `application_name` remain an operational stop — do not hide them.

#### 15. Production smoke

- Login / JWT (not Redis-dependent)
- `/health` pid diversity with `GUNICORN_WORKERS=2`
- Resume parse against Ollama `qwen2.5:14b-instruct` (if AI enabled)

#### 16. Verify migration revision remains unchanged

```bash
cd apps/backend
alembic current
alembic heads
```

SIGTERM Gunicorn (graceful). Start it again with the same `MIGRATIONS_ALREADY_APPLIED=true`. Confirm `alembic current` still equals head. Repeat once more.

---

## Stale-writer cleanup (when `pg_stat_activity` shows foreign clients)

1. Run `scripts/release-verify.sh db-sessions --report-only`. Note `client_addr`, `pid`, `application_name`, `backend_start`.
2. On that host: stop Gunicorn / Flask / `start.js` / scheduler / outbox / leftover `python wsgi.py`.
3. Re-query until only this release’s `hcip-*` sessions remain (`scripts/release-verify.sh db-sessions` must pass).
4. `alembic current` / `alembic heads` — must match.
5. `alembic upgrade head` (idempotent; migrate role only).
6. Start this release with `MIGRATIONS_ALREADY_APPLIED=true`; verify; SIGTERM; start again; verify again.

Do not invent an in-app workaround that hides foreign writers. An unknown process on a remote host is an operational ownership problem, not an application code defect.

---

## ROLLBACK

There is **no automatic rollback**. Do not `alembic downgrade` in production. Reverse migrations are not a supported recovery path (data loss / untested reverse DDL).

### Migration fails (`alembic upgrade head` errors)

- Do **not** start web, scheduler, or outbox.
- Do **not** `alembic stamp head`.
- Do **not** `alembic downgrade`.
- Inspect the error, `alembic current`, and `scripts/release-verify.sh db-sessions --report-only`.
- Preferred: fix-forward (correct the migration / environment) and retry `HCIP_PROCESS_ROLE=migrate alembic upgrade head`.
- If the database was partially changed and cannot be repaired: restore the pre-migration backup ([BACKUP_RUNBOOK.md](BACKUP_RUNBOOK.md)), then retry migrate from the restored schema.

### Application fails after a successful migration

- The schema is already at the new head.
- Preferred: fix-forward (code hotfix) and restart with `MIGRATIONS_ALREADY_APPLIED=true`. Do not migrate again unless a new revision exists.
- Do not start the previous application version against the upgraded schema.

### Previous application version is incompatible with the new schema

- Do **not** start the old release against the upgraded database.
- Restore the pre-migration database backup first, then start the previous code.
- Treat this as restore + previous-code restart, not an Alembic downgrade.

---

## LinkedIn / Naukri

Out of scope for internal production readiness. Adapters stay fail-closed until provider access exists.
