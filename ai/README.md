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
└── foundation.json       # Machine-readable foundation manifest (M2)
```

Docs (centralized, flat): [`docs/AI_WORKFLOW.md`](../docs/AI_WORKFLOW.md), [`docs/AI_DATA_PIPELINE.md`](../docs/AI_DATA_PIPELINE.md), [`docs/ADRS.md`](../docs/ADRS.md).

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
| [docs/AI_WORKFLOW.md](../docs/AI_WORKFLOW.md) | Engineering workflow loop |
| [docs/AI_DATA_PIPELINE.md](../docs/AI_DATA_PIPELINE.md) | End-to-end dataset pipeline |
| [docs/ADRS.md](../docs/ADRS.md) | Architecture Decision Records |
| [docs/WORKFLOWS.md](../docs/WORKFLOWS.md) | App + AI unique workflows index |
| [toon/README.md](toon/README.md) | TOON ontology package |
| Domain contracts / schemas | `contracts/`, `schemas/` (YAML is SoT) |

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

Milestone labels may lag implementation — verify against code, tests, and [docs/AI_WORKFLOW.md](../docs/AI_WORKFLOW.md).
