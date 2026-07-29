# CI/CD

GitHub Actions workflow: [`github-actions.yml`](github-actions.yml)

Copy to `.github/workflows/ci.yml` when enabling CI on the remote repository.

## Pipelines

| Job | Command |
|-----|---------|
| backend-tests | `pytest tests/backend/` (unit tests, no integration) |
| frontend-build | `cd apps/frontend && npm run build` |
| ai-tests | `cd ai && pytest` |
