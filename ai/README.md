# HRMS AI Platform

Enterprise AI platform for the HR Job Portal — designed for long-term maintainability. Powers parsing, matching, ranking, search, summarization, interview generation, chat, and future HR intelligence.

**Independent of the HRMS application** until Milestone 9. No backend, frontend, or API changes in current milestones.

## Directory map

```
ai/
├── runtime/              # AI Runtime — executes capabilities
├── providers/            # LLM provider implementations (Ollama, mock, …)
├── capabilities/         # Capability library — prompts, schemas, validation
├── dataset/              # Data platform
│   ├── factory/          # Dataset factory pipeline (inspector + stages)
│   ├── lake/             # Staged data lake (raw → silver → jsonl)
│   ├── extraction/       # Document text extraction engine
│   └── proposals/        # LLM proposal generation from silver docs
├── toon/                 # TOON ontology — canonical HR semantics
├── contracts/            # Domain contracts (YAML)
├── schemas/              # Normalized document schemas + validation
├── knowledge/            # Reference datasets (skills, titles, degrees, …)
├── configs/              # Platform YAML templates
├── registry/             # Registry schema (models, datasets, benchmarks)
├── docs/                 # Architecture, ADRs, handbook, archive
│   └── adr/              # ADR-001 through ADR-006
└── foundation.json       # Machine-readable foundation manifest (M2)
```

## HR Intelligence Foundation (M2)

Machine-readable domain layer — contracts, knowledge bases, and schemas. Entry point: [`foundation.json`](foundation.json).

| Layer | Path | Manifest |
|-------|------|----------|
| Domain contracts | `contracts/` | `contracts/manifest.yaml` |
| Knowledge bases | `knowledge/` | `knowledge/manifest.yaml` |
| Document schemas | `schemas/` | `schemas/manifest.yaml` |
| TOON ontology | `toon/v1/` | `toon/versions.yaml` |
| Normalized validation | `schemas/validation/` | `schemas/validation/rules.yaml` |
| TOON wire validation | `toon/v1/validation/` | `toon/v1/validation/validation.yaml` |

Authority chain: **contracts → schemas → knowledge → toon/v1 → TOON runtime** (`backend/toon.py`, read-only).

## Dataset platform

| Component | Path | Status |
|-----------|------|--------|
| Factory pipeline | `dataset/factory/` | Inspector implemented; other stages interface-only |
| Data lake | `dataset/lake/` | Medallion stages (raw, extracted, silver, …) |
| Document extraction | `dataset/extraction/` | PDF/DOC/DOCX/RTF/TXT extractors |
| Proposal Generator | `dataset/proposals/` | Silver → LLM proposals pipeline |

Entry points:

- [`dataset/factory/manifest.yaml`](dataset/factory/manifest.yaml)
- [`dataset/extraction/cli/extract_documents.py`](dataset/extraction/cli/extract_documents.py)
- [`dataset/proposals/cli/generate_proposals.py`](dataset/proposals/cli/generate_proposals.py)

## Canonical documents

| Document | Purpose |
|----------|---------|
| [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) | End-to-end pipeline |
| [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md) | Domain schemas |
| [docs/PLATFORM_VISION.md](docs/PLATFORM_VISION.md) | Platform thinking |
| [docs/AI_ENGINEERING.md](docs/AI_ENGINEERING.md) | Engineering handbook |
| [docs/ROADMAP.md](docs/ROADMAP.md) | M1–M11 milestones |
| [docs/adr/](docs/adr/) | Architecture Decision Records |
| [toon/README.md](toon/README.md) | TOON ontology package |

## Quick start

```bash
cd ai
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest                      # Run platform tests
python -m runtime.cli.main --help
```

## Current milestone

| Area | Status |
|------|--------|
| M2 Foundation (contracts, schemas, TOON, knowledge) | Active — manifests in place |
| M7 Runtime + capabilities + providers | **Implemented** — `pytest` passes |
| M3 Dataset platform | Inspector + extraction + proposals implemented; other factory stages interface-only |
| M9 HRMS integration | Planned |

See [docs/ROADMAP.md](docs/ROADMAP.md) for full milestone timeline. Roadmap status labels may lag implementation — verify against code and tests.
