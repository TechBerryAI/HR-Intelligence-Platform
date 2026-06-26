# HRMS AI Platform

Enterprise AI platform for the HR Job Portal — designed for five-year maintainability. Powers parsing, matching, ranking, search, summarization, interview generation, chat, and future HR intelligence.

**Independent of the HRMS application** until Milestone 9. No backend, frontend, or API changes in current milestones.

## Platform paradigm

This is **not** a training repository. It is an AI platform with five subsystems:

| Subsystem | Directories |
|-----------|-------------|
| Data Platform | `datasets/`, `preprocessing/`, `docs/DATA_CONTRACTS.md` |
| Training Platform | `training/`, `models/`, `experiments/` |
| Inference Platform | `platform/inference/`, `platform/providers/` (M8) |
| Evaluation Platform | `evaluation/`, `datasets/benchmark/` |
| Governance Platform | `registry/`, `governance/`, `docs/adr/` |

## Directory map

```
ai/
├── runtime/              # AI Runtime — executes capabilities (M7+)
├── capabilities/         # AI Capability Library — prompts, schemas, validation (source of truth)
├── dataset_factory/      # Dataset Factory pipeline (M3.1+)
│   ├── inspector/        # Stage 1 — profile raw corpora (designed)
│   ├── extractor/        # Stage 2 — interface only
│   ├── validator/        # Stage 3 — interface only
│   ├── normalizer/       # Stage 4 — interface only
│   ├── reviewer/         # Stage 5 — interface only
│   ├── exporter/         # Stage 6 — interface only
│   ├── benchmark/        # Parallel branch — interface only
│   └── shared/           # Stage interface, formats, medallion
├── foundation.json       # Machine-readable foundation manifest (M2)
├── contracts/            # Domain contracts (YAML, not JSON Schema)
├── knowledge/            # Reference datasets (skills, titles, degrees, …)
├── schemas/              # Document schemas + TOON mappings + validation
├── configs/              # Platform YAML templates
├── datasets/             # Staged data lake (raw → jsonl + benchmark + synthetic)
├── preprocessing/        # extract/ clean/ normalize/ validate/ split/
├── prompts/              # Active prompt templates
├── experiments/          # EXP-* research
├── training/             # runs/ checkpoints/ logs/ configs/
├── models/               # base/ adapters/ merged/ gguf/
├── registry/             # models/ datasets/ benchmarks/ prompts/ providers/
│                         # evaluations/ deployments/ experiments/
├── evaluation/           # metrics/ reports/ comparisons/ regression/
├── exports/              # Modelfiles, deployment manifests
├── platform/             # inference/ services/ orchestration/ monitoring/ providers/
├── governance/           # Standards index
├── scripts/              # CLI (future)
├── notebooks/            # Exploration only
└── docs/                 # Architecture, ADRs, handbook
    └── adr/              # ADR-001 through ADR-006
```

## HR Intelligence Foundation (M2)

Machine-readable domain layer — contracts, knowledge bases, and schemas. Entry point: [`foundation.json`](foundation.json).

| Layer | Path | Manifest |
|-------|------|----------|
| Domain contracts | `contracts/` | `contracts/manifest.yaml` |
| Knowledge bases | `knowledge/` | `knowledge/manifest.yaml` |
| Document schemas | `schemas/` | `schemas/manifest.yaml` |
| TOON mappings | `schemas/mappings/` | `schemas/mappings/toon.yaml` |
| Validation rules | `schemas/validation/` | `schemas/validation/rules.yaml` |

Authority chain: **contracts → schemas → knowledge → TOON** (`backend/toon.py`, read-only).

## Dataset Factory (M3.1)

Reusable data engineering pipeline inside `dataset_factory/`. Entry point: [`dataset_factory/manifest.yaml`](dataset_factory/manifest.yaml).

| Stage | Status |
|-------|--------|
| Inspector | Designed — schemas, templates, quality model |
| Extractor → Benchmark | Interface + architecture docs only |

Pipeline: [`dataset_factory/pipeline.yaml`](dataset_factory/pipeline.yaml) · Roadmap: [`dataset_factory/roadmap.yaml`](dataset_factory/roadmap.yaml)

## Canonical documents

| Document | Purpose |
|----------|---------|
| [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) | End-to-end pipeline |
| [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md) | Domain schemas |
| [docs/PLATFORM_VISION.md](docs/PLATFORM_VISION.md) | Platform thinking |
| [docs/VERSIONING.md](docs/VERSIONING.md) | Naming and version rules |
| [docs/ARTIFACT_LINEAGE.md](docs/ARTIFACT_LINEAGE.md) | ML artifact model |
| [docs/BENCHMARK_STRATEGY.md](docs/BENCHMARK_STRATEGY.md) | Eval categories |
| [docs/AI_ENGINEERING.md](docs/AI_ENGINEERING.md) | Engineering handbook |
| [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) | Six-month replay |
| [docs/ROADMAP.md](docs/ROADMAP.md) | M1–M11 milestones |
| [docs/adr/](docs/adr/) | Architecture Decision Records |

## Current milestone

**M3.1 — Dataset Factory / Inspector (design)** ✅ Complete

Inspector architecture, output schemas, templates, quality model, and future-stage interfaces are in place.

**M2 — HR Intelligence Foundation** ✅ Complete

**Next:** M3.2 — Dataset Inspector implementation (Python CLI)

## Quick start

```bash
cd ai && python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
```

See [docs/AI_ENGINEERING.md](docs/AI_ENGINEERING.md) for full environment setup.
