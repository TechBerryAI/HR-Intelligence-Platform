# ADR-001: AI Workspace Layout

## Status

Accepted (M1.5, refined M1.5 Architecture Review)

## Context

The HRMS needs an independent AI workspace that does not interfere with production Flask/React code. Milestone 1 created an initial folder structure. Before implementation, we must ensure the layout scales to ten+ AI features over five years.

## Problem

A flat or training-centric layout causes:
- Mixed concerns (data + models + deployment in one folder)
- Difficulty onboarding engineers ("where does X go?")
- Feature coupling (parsing changes break matching experiments)
- No home for platform services, monitoring, or governance

## Decision

Adopt a **layered platform layout** inside `ai/`:

```
ai/
├── datasets/          # Data lake (staged)
├── preprocessing/     # Transform pipelines
├── prompts/           # Active prompt templates
├── experiments/       # Research
├── training/          # Training execution
├── models/            # Binary artifacts by lifecycle stage
├── registry/          # Committed metadata (all registries)
├── evaluation/        # Quality measurement
├── exports/           # Deployment packages (not weights)
├── platform/          # Future runtime (inference, services, monitoring)
├── governance/        # Standards index
├── configs/           # YAML templates
├── scripts/           # CLI (future)
├── notebooks/         # Exploration only
└── docs/              # Architecture + ADRs
```

**Separate `platform/` from `training/`.** Training produces models; platform consumes them.

**Separate `registry/` from `models/`.** Metadata in git; weights out of git.

**Add `governance/`** as index to standards documents.

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Single `ml/` folder | No separation of data, training, runtime |
| Monorepo package `hrms_ai/` | Premature; docs-first layout lower risk |
| Nest everything under `training/` | Training-centric; blocks platform services |
| Put platform in `backend/` | Violates isolation constraint until M9 |

## Consequences

**Positive:**
- Clear ownership per directory
- New features add benchmark + registry entries, not new top-level folders
- Platform runtime has defined home (`platform/`)

**Negative:**
- More directories to learn (mitigated by README per folder)
- `platform/` empty until M8 (documented as intentional)

## Future work

- `AI_DATA_ROOT` env var for symlinked data mount (M3)
- `governance/schemas/` for JSON Schema (M2)
- CI validation of directory conventions (M6)
