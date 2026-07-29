# Contributing to HR Job Portal

Thank you for contributing. This repository contains two coordinated systems:

| System | Path | Documentation |
|--------|------|---------------|
| HRMS application | `apps/frontend/`, `apps/backend/`, `apps/desktop/` | [docs/](docs/) |
| AI platform | `ai/` | [ai/README.md](ai/README.md) |

## Before you start

1. Read [docs/DOCUMENTATION_MAP.md](docs/DOCUMENTATION_MAP.md) — single entry point for all documentation
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

- Update the directory README (see [documentation standard](docs/DOCUMENTATION_MAP.md#documentation-standard))
- Fix cross-references if paths change
- Do not duplicate content — link to the canonical source

## AI platform conventions

See [ai/docs/CONVENTIONS.md](ai/docs/CONVENTIONS.md) and [ai/docs/AI_ENGINEERING.md](ai/docs/AI_ENGINEERING.md).

Key rules:

- Capabilities are the source of truth for prompts and schemas at runtime
- TOON ontology lives in `ai/toon/v1/` only
- Dataset pipelines live under `ai/dataset/`

## Architecture decisions

Significant AI platform decisions require an ADR in `ai/docs/adr/`. See [ai/docs/adr/README.md](ai/docs/adr/README.md).

## Security

- Never commit `.env` files, API keys, or credentials
- Never commit raw resumes or PII in `dataset/lake/`
- Report security issues privately to the maintainers

## Questions

- HRMS architecture: [docs/TECHNICAL_DOCUMENTATION.md](docs/TECHNICAL_DOCUMENTATION.md)
- AI platform: [ai/README.md](ai/README.md)
- TOON: [ai/toon/README.md](ai/toon/README.md)
