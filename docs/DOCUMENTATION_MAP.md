# Documentation Map

Single entry point for all repository documentation.

## Quick routing

| I need to… | Start here |
|------------|------------|
| Set up locally | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Contribute | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Run the HRMS app | [README.md](../README.md) |
| Understand HRMS architecture & APIs | [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) |
| Work on the AI platform | [ai/README.md](../ai/README.md) |
| Understand TOON wire format | [ai/toon/README.md](../ai/toon/README.md) |
| Review production TOON behavior | [ai/docs/current_system/CURRENT_TOON_SCHEMA.md](../ai/docs/current_system/CURRENT_TOON_SCHEMA.md) |
| Follow AI milestones & ADRs | [ai/docs/ROADMAP.md](../ai/docs/ROADMAP.md) |

## Directory indexes

### Repository root

| Path | README | Purpose |
|------|--------|---------|
| `frontend/` | — | React SPA (see [FRONTEND_DOCUMENTATION.md](FRONTEND_DOCUMENTATION.md)) |
| `backend/` | [README.md](../backend/README.md) | Flask API |
| `electron/` | [README.md](../electron/README.md) | Desktop shell |
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
| `dataset/factory/` | [README.md](../ai/dataset/factory/README.md) | Dataset Factory |
| `dataset/lake/` | [README.md](../ai/dataset/lake/README.md) | Data lake |
| `dataset/extraction/` | [README.md](../ai/dataset/extraction/README.md) | Document Extraction |
| `dataset/proposals/` | [README.md](../ai/dataset/proposals/README.md) | Proposal Generator |
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

## Documentation trees

### HRMS Application (`docs/`)

| Document | Scope |
|----------|-------|
| [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) | Full-stack architecture, API catalog, security |
| [BACKEND_DOCUMENTATION.md](BACKEND_DOCUMENTATION.md) | Flask blueprints, database patterns |
| [FRONTEND_DOCUMENTATION.md](FRONTEND_DOCUMENTATION.md) | React SPA, routing, state |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local setup and workflows |

### AI Platform (`ai/docs/`)

| Document | Scope |
|----------|-------|
| [PLATFORM_VISION.md](../ai/docs/PLATFORM_VISION.md) | Platform thinking |
| [DATA_PIPELINE.md](../ai/docs/DATA_PIPELINE.md) | End-to-end data pipeline |
| [DATA_CONTRACTS.md](../ai/docs/DATA_CONTRACTS.md) | Domain schemas |
| [AI_ENGINEERING.md](../ai/docs/AI_ENGINEERING.md) | Engineering handbook |
| [CONVENTIONS.md](../ai/docs/CONVENTIONS.md) | Naming and layout conventions |
| [adr/](../ai/docs/adr/) | Architecture Decision Records |

### TOON Ontology (`ai/toon/`)

| Document | Scope |
|----------|-------|
| [README.md](../ai/toon/README.md) | Package overview and authority chain |
| [v1/ontology/ontology.yaml](../ai/toon/v1/ontology/ontology.yaml) | Document types |
| [v1/mappings/](../ai/toon/v1/mappings/) | Projection maps |
| [v1/types/toon.ts](../ai/toon/v1/types/toon.ts) | TypeScript contracts |

### Production Snapshots (`ai/docs/current_system/`)

Reverse-engineered snapshots of live HRMS behavior. Verify against code before relying on them.

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
| TOON wire runtime | `backend/toon.py` |
| Normalized schemas | `ai/schemas/` |
| AI prompts/schemas at runtime | `ai/capabilities/` |
| HRMS LLM prompts | `backend/llm_service.py` |
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
