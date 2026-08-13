# CI/CD

Live workflow: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)

Template (kept in sync as reference): [`github-actions.yml`](github-actions.yml)

## Pipelines

| Job | Command |
|-----|---------|
| backend-tests | `pytest tests/backend/` (unit tests; ignores Ollama/smoke that need live services) |
| frontend-build | `cd apps/frontend && npm ci && npm run build` |
| ai-tests | `cd ai && pytest runtime/tests` (mocked providers; `requirements-runtime.txt` only) |
