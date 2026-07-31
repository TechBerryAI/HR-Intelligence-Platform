# Documentation

Single entry point for repository documentation.

## Quick routing

| I need to… | Start here |
|------------|------------|
| Set up locally | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Contribute | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Run the HRMS app | [README.md](../README.md) |
| Understand architecture & product | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Work on backend / frontend / APIs | [ENGINEERING.md](ENGINEERING.md) |
| Review sprint freeze history | [HISTORY.md](HISTORY.md) |
| Work on the AI platform | [ai/README.md](../ai/README.md) |
| Understand TOON wire format | [ai/toon/README.md](../ai/toon/README.md) |
| Follow AI milestones & ADRs | [ai/docs/ROADMAP.md](../ai/docs/ROADMAP.md) · [ai/docs/adr/](../ai/docs/adr/) |

## Docs in this folder

| Document | Scope |
|----------|-------|
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local setup and workflows |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Product vision, domain, system design, security, roadmap |
| [ENGINEERING.md](ENGINEERING.md) | Stack, APIs, backend structure, frontend structure |
| [HISTORY.md](HISTORY.md) | Completed sprint freeze / migration reports |

ADRs live under [`ai/docs/adr/`](../ai/docs/adr/) (not duplicated here).

## Directory indexes

### Repository root

| Path | README | Purpose |
|------|--------|---------|
| `apps/frontend/` | — | React SPA (see [ENGINEERING.md](ENGINEERING.md#frontend)) |
| `apps/backend/` | [README.md](../apps/backend/README.md) | Flask API |
| `apps/desktop/` | — | Electron shell |
| `ai/` | [README.md](../ai/README.md) | AI platform |
| `docs/` | This file | HRMS documentation |
| `scripts/` | [README.md](../scripts/README.md) | Dev utilities |
| `tests/` | [README.md](../tests/README.md) | Test index |
| `tools/` | [README.md](../tools/README.md) | CLI index |

### AI platform (`ai/`)

| Path | README | Purpose |
|------|--------|---------|
| `runtime/` | [README.md](../ai/runtime/README.md) | Task execution engine |
| `providers/` | [README.md](../ai/providers/README.md) | LLM providers |
| `capabilities/` | [README.md](../ai/capabilities/README.md) | Capability library |
| `dataset/` | [README.md](../ai/dataset/README.md) | Data platform |
| `toon/` | [README.md](../ai/toon/README.md) | TOON ontology |
| `contracts/` | [README.md](../ai/contracts/README.md) | Domain contracts |
| `schemas/` | [README.md](../ai/schemas/README.md) | Document schemas |
| `knowledge/` | [README.md](../ai/knowledge/README.md) | Knowledge bases |
| `registry/` | [README.md](../ai/registry/README.md) | Artifact registry |
| `configs/` | [README.md](../ai/configs/README.md) | Config templates |

## Documentation standard

Every major directory README answers:

1. **What is this?** — one-sentence purpose
2. **Why does it exist?** — problem it solves
3. **What belongs here?** — allowed contents
4. **What should never be placed here?** — boundary violations
5. **Dependencies / consumers** — who uses it
6. **Extension points** — how to add functionality
7. **Related documentation** — links to canonical sources

## Authority chain (no duplication)

```
contracts/ → schemas/ → knowledge/ → toon/v1/ → backend/toon.py (runtime)
capabilities/ → runtime/ (AI execution)
providers/ → runtime/ (LLM backends)
dataset/ → lake/ (artifacts)
```

| Concept | Canonical location |
|---------|-------------------|
| TOON ontology | `ai/toon/v1/` |
| TOON wire runtime | `apps/backend` / `backend/toon.py` |
| Normalized schemas | `ai/schemas/` |
| AI prompts/schemas at runtime | `ai/capabilities/` |
| HRMS LLM prompts | backend `llm_service` |
| Data lake artifacts | `ai/dataset/lake/` |

## Legacy & archive

Retired paths and migration notes: [ai/docs/archive/LEGACY_ARTIFACTS.md](../ai/docs/archive/LEGACY_ARTIFACTS.md)

## Canonical naming

| Concept | Canonical form |
|---------|----------------|
| Proposal Generator (product) | Title case in docs |
| Python package | `dataset.proposals` |
| Data lake path | `dataset/lake/` |
| TOON | Always uppercase |
| Document Extraction | Title case; path `dataset/extraction/` |
