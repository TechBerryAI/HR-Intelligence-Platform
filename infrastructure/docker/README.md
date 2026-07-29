# Local development stack (scaffolding)

Services for local full-stack development. Adjust `POSTGRES_*` in `apps/backend/.env` to match.

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: JobPortal
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

Usage:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

The Flask API and Vite dev server are started via `node start.js` at the repo root.
