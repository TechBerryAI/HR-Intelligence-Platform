# Contributing to HR Job Portal

Thank you for contributing. This repository contains two coordinated systems:

| System | Path | Documentation |
|--------|------|---------------|
| HRMS application | `apps/frontend/`, `apps/backend/`, `apps/desktop/` | [docs/](docs/) |
| AI platform | `ai/` | [ai/README.md](ai/README.md) |

## Before you start

1. Read [docs/README.md](docs/README.md) — single entry point for all documentation
2. Read [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — local setup and workflows
3. Identify which system you are changing — do not mix concerns across boundaries

## Architecture boundaries (frozen)

| Owner | Responsibility |
|-------|----------------|
| `apps/frontend/` | Presentation only |
| `apps/backend/` | Business logic, APIs, TOON runtime (`app/ai/toon/`) |
| `apps/desktop/` | Desktop integration only (dialogs, IPC, FS) |
| `ai/` | All AI intelligence (runtime, providers, capabilities, dataset, TOON) |

**Do not** place AI-specific code outside `ai/`. **Do not** place business logic in Electron.

## Branch and commit workflow

1. Create a feature branch from `main`
2. Make focused changes — one concern per PR
3. Follow existing naming and code style in the touched area
4. Update documentation when you change behavior or paths
5. Open a PR with a clear summary and test plan

## Code style

| Area | Convention |
|------|------------|
| Python (backend) | PEP 8; match existing Flask patterns |
| Python (ai) | PEP 8; type hints where present; `pytest` for tests |
| JavaScript/React | Existing Vite + Tailwind + Radix patterns |
| YAML manifests | Match existing manifest structure in the same directory |

## Testing

| Component | Command |
|-----------|---------|
| AI platform | `cd ai && pytest` |
| Frontend build | `cd apps/frontend && npm run build` |
| Backend unit tests | `pytest tests/backend/` |
| Database | `node scripts/db-preflight.js` |

Component tests are colocated. See [tests/README.md](tests/README.md).

## Documentation requirements

When adding or changing a major component:

- Update the relevant README under `docs/` or the component directory
- Keep [docs/user-manual/](docs/user-manual/README.md) in mind for user-facing flow changes
- Fix cross-references if paths change
- Prefer live code as the source of truth over archive narratives

## AI platform conventions

See [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md), [docs/ADRS.md](docs/ADRS.md), and [ai/README.md](ai/README.md).

Key rules:

- Capabilities are the source of truth for prompts and schemas at runtime
- TOON ontology lives in `ai/toon/v1/` only
- Dataset pipelines live under `ai/dataset/`

## Architecture decisions

Significant AI platform decisions go in [docs/ADRS.md](docs/ADRS.md).

## Security

- Never commit `.env` files, API keys, or credentials
- Never commit raw resumes or PII in `dataset/lake/`
- Report security issues privately to the maintainers

## Questions

- Docs index: [docs/README.md](docs/README.md)
- User manuals: [docs/user-manual/README.md](docs/user-manual/README.md)
- AI platform: [ai/README.md](ai/README.md)
- TOON: [ai/toon/README.md](ai/toon/README.md)
