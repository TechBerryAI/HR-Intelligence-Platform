# CI/CD

Single source of truth: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml). GitHub Actions only
auto-discovers workflows under `.github/workflows/`, so there is intentionally no second copy here anymore —
a previous `github-actions.yml` template in this directory had drifted out of sync with the real workflow
(missing dependencies in one direction, a live Postgres service missing in the other) without either copy
ever failing a build to reveal it, since GitHub never executed the orphaned copy at all. Edit the live file.

Triggers on push/PR to `development` and `production` (this repo's actual merge flow: feature branch →
`development` → `production`; there is no `main` branch).

## Pipelines

| Job | Command |
|-----|---------|
| secret-scan | `gitleaks` over the diff — blocks the build on a real finding |
| backend-tests | `pytest tests/backend/` against a live Postgres (ignores Ollama/smoke tests that need external services); includes `antiword` so legacy `.doc` extraction is actually exercised, plus a report-only `pip-audit` |
| frontend-build | `npm ci && npm run test && npm run build` (Node version from `.nvmrc`), plus a report-only `npm audit --audit-level=high` |
| alembic-upgrade | Empty **PostgreSQL 15/16/17** DBs → `alembic upgrade head`, then asserts a handful of schema markers exist |
| ai-tests | `cd ai && pytest runtime/tests` (mocked providers; `requirements-runtime.txt` only) |
