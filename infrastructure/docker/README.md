# Local & production Docker stacks

## Local development

Services for local full-stack development. Adjust `POSTGRES_*` in `apps/backend/.env` to match.

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

### Schema initialization

Compose starts an **empty** Postgres volume. Create/upgrade the application schema with Alembic only:

```bash
cd apps/backend
alembic upgrade head
```

Do not mount SQL init scripts that bypass Alembic.

## Production data plane

[`docker-compose.prod.yml`](docker-compose.prod.yml) runs **Postgres + Redis** with healthchecks. Secrets come from the environment / `--env-file` (never hardcode real passwords in the compose file).

```bash
# Example: reuse backend env for POSTGRES_* (ensure POSTGRES_PASSWORD is set)
docker compose -f infrastructure/docker/docker-compose.prod.yml \
  --env-file apps/backend/.env up -d
```

Point the API at the stack:

| Variable | Example |
|----------|---------|
| `POSTGRES_HOST` | `localhost` (host) or `postgres` (from another compose service) |
| `POSTGRES_PASSWORD` | same as compose |
| `REDIS_URL` | `redis://localhost:6379/0` |

### API / frontend notes

- **API:** run gunicorn from `apps/backend` (or uncomment the optional `api` service in `docker-compose.prod.yml` once you have an image). Probe `GET /health` (liveness) and `GET /ready` (Postgres readiness).
- **Frontend:** build with `npm run build` in `apps/frontend`, then serve `dist/` behind a reverse proxy that forwards `/api`, `/health`, and `/ready` to the API.
- Do not bake JWT secrets, mail passwords, or OAuth client secrets into images; inject them at runtime.
