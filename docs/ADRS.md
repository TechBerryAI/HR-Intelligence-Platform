# Architecture Decision Records

Significant AI platform decisions. New ADRs: add a section as `ADR-NNN` below (do not recreate subfolders).

## Index

| ADR | Title |
|-----|-------|
| [ADR-001-ai-workspace-layout](#adr-001-ai-workspace-layout) | ADR-001: AI Workspace Layout |
| [ADR-002-dataset-pipeline](#adr-002-dataset-pipeline) | ADR-002: Dataset Pipeline |
| [ADR-003-registry-design](#adr-003-registry-design) | ADR-003: Registry Design |
| [ADR-004-artifact-lineage](#adr-004-artifact-lineage) | ADR-004: Artifact Lineage |
| [ADR-005-versioning-strategy](#adr-005-versioning-strategy) | ADR-005: Versioning Strategy |
| [ADR-006-ai-platform-vision](#adr-006-ai-platform-vision) | ADR-006: AI Platform Vision |

---

## ADR-001-ai-workspace-layout

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
├── dataset/lake/          # Data lake (staged)
├── dataset/     # Transform pipelines
├── prompts/           # Active prompt templates
├── experiments/       # Research
├── training/          # Training execution
├── models/            # Binary artifacts by lifecycle stage
├── registry/          # Committed metadata (all registries)
├── evaluation/        # Quality measurement
├── exports/           # Deployment packages (not weights)
├── platform/          # Future runtime (inference, services, monitoring)
├── docs/ADRS.md           # ADRs (flat under repo docs/)
├── configs/           # YAML templates
├── scripts/           # CLI (future)
├── notebooks/         # Exploration only
└── (see also docs/*.md) # Architecture + workflows
```

**Separate `runtime/` + `providers/` from `training/`.** Training produces models; platform consumes them.

**Separate `registry/` from `models/`.** Metadata in git; weights out of git.

**Add flat markdown under `docs/`** (`AI_WORKFLOW.md`, `AI_DATA_PIPELINE.md`, `ADRS.md`) as the centralized AI docs.

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
- Platform runtime has defined home (`runtime/` + `providers/`)

**Negative:**
- More directories to learn (mitigated by README per folder)
- `runtime/` + `providers/` empty until M8 (documented as intentional)

## Future work

- `AI_DATA_ROOT` env var for symlinked data mount (M3)
- `docs/ADRS.md` / `docs/AI_WORKFLOW.md` for AI workflows and ADRs
- CI validation of directory conventions (M6)

---

## ADR-002-dataset-pipeline

## Status

Accepted (M1.5 Architecture Review)

## Context

Resume and JD data flows through multiple transformations before training. Milestone 1.5 introduced staged directories (`raw/` → `jsonl/`). We must confirm this supports all future features and artifact lineage.

## Problem

A single `processed/` folder:
- Cannot re-run individual stages
- Loses intermediate artifacts for debugging
- Blocks features that enter at different stages (summarization from `cleaned/`, not `normalized/`)
- Makes lineage tracing impossible

## Decision

**Seven-stage data lake** with one directory per transformation:

```
raw → extracted → cleaned → normalized → jsonl
                    ↓              ↓
               synthetic      benchmark (frozen branch)
```

**Five preprocessing modules** map 1:1 to stages: `extract/`, `clean/`, `normalize/`, `validate/`, `split/`.

Each stage produces **versioned artifacts** with manifests (see ADR-004).

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Single `processed/` JSONL | No intermediate replay |
| Database instead of files | Overkill for M2–M4; files portable to cloud |
| Skip `cleaned/` stage | Summarization and search need clean text without TOON |
| Merge `normalized/` and `jsonl/` | Different consumers (validation vs training format) |

## Consequences

**Positive:**
- Idempotent stage re-runs
- Feature-specific entry points
- Benchmark branch isolated from training data
- Aligns with artifact lineage model

**Negative:**
- More disk usage (mitigated by retention policy in AI_ENGINEERING.md)
- Manifest chain must be maintained

## Future work

- M3: Implement stage scripts with manifest generation
- M4: Validation gates block bad data before JSONL
- Artifact sidecar files (`.artifact.yaml`) per record

---

## ADR-003-registry-design

## Status

Accepted (M1.5 Architecture Review, extended)

## Context

The platform needs a single source of truth for models, datasets, prompts, providers, evaluations, and deployments. Milestone 1.5 introduced `registry/` with models, datasets, benchmarks, and experiments.

## Problem

Without extended registries:
- Prompt versions are orphaned in `prompts/` with no history
- Provider configs change without audit trail
- Evaluation runs are not linked to promotion decisions
- Deployments (Ollama tags, Modelfiles) drift from model registry

## Decision

**Unified `registry/` with six sub-registries:**

```
registry/
├── schema.yaml
├── models/          # Model versions, artifacts, status
├── dataset/lake/        # Dataset versions, checksums
├── benchmarks/      # Frozen benchmark definitions
├── experiments/     # EXP-* outcomes
├── prompts/         # PROMPT-* version history
├── providers/       # PROV-* capability and config refs
├── evaluations/     # EVAL-* run records
└── deployments/     # DEPLOY-* Ollama/gateway targets
```

All records are **committed YAML**. Binary artifacts referenced by path only.

Each registry record includes `artifact_id` (ADR-004) and `compatible:` cross-references (VERSIONING.md).

## Why each registry matters

| Registry | Why |
|----------|-----|
| **Prompts** | Prompt changes cause silent quality regression; must trace which prompt trained/evaluated each model |
| **Providers** | Multi-provider fallback requires versioned capability matrix (models supported, rate limits) |
| **Evaluations** | Promotion decisions require immutable eval record linked to benchmark version |
| **Deployments** | Ollama tag `latest` is mutable; registry records immutable deployment snapshot |

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Single `registry.json` | Merge conflicts; no per-entity history |
| MLflow only | External dependency; offline reproducibility harder |
| Metadata in WandB | Training-only; misses prompts, deployments |
| Git tags for models | No structured schema; hard to query |

## Consequences

**Positive:**
- Full platform state readable from git
- Cross-registry compatibility matrix
- Audit trail for compliance

**Negative:**
- Manual registry updates until M6 automation
- Schema evolution requires `schema.yaml` updates

## Future work

- `scripts/validate_registry.py` (M3)
- Auto-register on training/eval completion (M6)
- Prompt registry auto-sync from `prompts/` on version bump (M4)

---

## ADR-004-artifact-lineage

## Status

Accepted (M1.5 Architecture Review)

## Context

Reproducibility and audit require tracing any model or evaluation back to source documents. The platform must support "show me everything that produced `hrms-parsing-v1`" queries.

## Problem

Without artifact lineage:
- Cannot explain why a model fails on specific resume types
- Cannot reproduce training after team turnover
- Regulatory/audit requests for data provenance fail
- Duplicate documents enter training undetected

## Decision

Introduce **ML Artifacts** as first-class conceptual objects. Every pipeline stage produces an artifact with:

| Field | Purpose |
|-------|---------|
| `id` | `ART-{TYPE}-{hash8}` |
| `version` | Semantic or incremental |
| `parent_id` / `parent_ids` | Lineage graph |
| `created_at` | Timestamp |
| `metadata` | Stage-specific fields |
| `sha256` | Content checksum |
| `source.dataset_id` | Link to dataset registry |

**Manifest chain:** each batch writes `manifest.yaml` referencing parent manifest.

**Registry integration:** model/dataset registry entries store root artifact IDs per stage.

## Artifact types

`RAW` → `EXTRACT` → `CLEAN` → `NORM` → `JSONL` → `ADAPTER` → `MERGED` → `GGUF` → `EVAL` → `DEPLOY`

Parallel: `BENCH`, `SYNTH`

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| DVC only | Another tool dependency; registry already planned |
| Filename conventions only | No parent linkage |
| DB lineage table | Violates file-based pipeline simplicity for M2–M4 |
| Git commit only | Insufficient granularity per document |

## Consequences

**Positive:**
- Six-month replay checklist becomes mechanical
- Duplicate detection via `source_hash` / `sha256`
- Debugging failed evals traces to source documents

**Negative:**
- Sidecar metadata per artifact (storage overhead — KB per file)
- Implementation deferred to M3–M4

## Future work

- `.artifact.yaml` sidecar convention (M3)
- `scripts/lineage_trace.py` (M4)
- CI checksum verification (M6)

Full spec: [ARTIFACT_LINEAGE.md](../ARTIFACT_LINEAGE.md)

---

## ADR-005-versioning-strategy

## Status

Accepted (M1.5 Architecture Review)

## Context

Multiple engineers will create datasets, models, prompts, benchmarks, and experiments concurrently. Ad hoc naming causes collisions, broken reproducibility, and impossible cross-references in tickets and ADRs.

## Problem

Milestone 1.5 used mixed conventions (`parsing-v1`, `hrms-parsing-v1`, date-prefixed experiments). Without canonical rules:
- Registry entries become ambiguous
- Filenames collide across features
- GGUF files on disk are unidentifiable
- Prompt versions conflict with model versions

## Decision

Adopt **prefixed ID system** with documented rules:

| Entity | ID format | Example |
|--------|-----------|---------|
| Dataset file | `{type}_v{semver}.jsonl` | `resume_v1.0.0.jsonl` |
| Dataset registry | `DS-{FEATURE}-v{semver}` | `DS-PARSE-v1.0.0` |
| Model | `hrms-{feature}-v{N}` | `hrms-parsing-v1` |
| GGUF file | `{short}-v{N}-{base}-{quant}.gguf` | `hrparser-v1-qwen2.5-7b-q4_k_m.gguf` |
| Experiment | `EXP-{NNNN}` | `EXP-0001` |
| Prompt | `PROMPT-{NNNN}` | `PROMPT-0007` |
| Benchmark | `BENCH-{CAT}-v{N}` | `BENCH-PARSE-v1` |
| Evaluation | `EVAL-{CAT}-{YYYYMMDD}` | `EVAL-PARSE-20260625` |
| Deployment | `DEPLOY-{feature}-v{N}-{target}` | `DEPLOY-parsing-v1-ollama` |
| Provider | `PROV-{NAME}` | `PROV-GROK` |
| Artifact | `ART-{TYPE}-{hash8}` | `ART-NORM-a1b2c3d4` |

**Immutability rule:** released versions are never mutated.

**Compatibility matrix:** model registry entries declare compatible dataset, prompt, benchmark, and deployment IDs.

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Date-only IDs | Sortable but collide; hard to reference |
| Semver everywhere | Experiments don't need semver |
| UUID only | Human-opaque in logs and tickets |
| No prefix | Namespace collisions across entity types |

## Consequences

**Positive:**
- Unambiguous ticket/ADR references
- Automated validation possible
- GGUF files self-describing on disk

**Negative:**
- Migration from M1.5 informal names (document mapping in registry)
- Sequential ID allocation needs convention (lowest unallocated N)

## Future work

- `scripts/allocate_id.py` for EXP-/PROMPT- IDs (M3)
- CI check for naming compliance (M6)

Full spec: [VERSIONING.md](../VERSIONING.md)

---

## ADR-006-ai-platform-vision

## Status

Accepted (M1.5 Architecture Review)

## Context

Early milestones risk framing the workspace as "Ollama + QLoRA for resume parsing." The HRMS roadmap includes matching, ranking, search, summarization, interview generation, chat, and salary intelligence. Architecture must reflect a **platform**, not a one-off ML project.

## Problem

Training-centric architecture leads to:
- Provider logic embedded in training scripts
- No home for inference routing, monitoring, or orchestration
- Each new feature reimplements provider calls, eval, and deployment
- HRMS integration tightly couples to one model format

## Decision

Adopt **AI Platform** paradigm with five platform subsystems:

1. **Data Platform** — contracts, staged lake, artifacts (`dataset/lake/`, `dataset/`, `docs/DATA_CONTRACTS.md`)
2. **Training Platform** — experiments, QLoRA, model registry (`training/`, `models/`, `experiments/`)
3. **Inference Platform** — LLM Gateway, provider management (`runtime/`, `providers/`)
4. **Evaluation Platform** — benchmarks, regression, comparisons (`evaluation/`, `registry/evaluations/`)
5. **Governance Platform** — registry, versioning, ADRs, engineering standards (`registry/`, `docs/ADRS.md`, `docs/`)

**LLM Gateway (M8)** sits between HRMS and providers — not direct Ollama calls from business logic.

**Feature services (M10)** expose parsing, matching, chat as discrete capabilities built on inference platform.

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Ollama-only architecture | Vendor lock-in; no Grok fallback |
| Embed AI in Flask immediately | Violates isolation; premature |
| Buy managed ML platform | Cost; less control over TOON contract |
| Microservices per feature now | Over-engineering before M6 eval proves patterns |

## Consequences

**Positive:**
- Each new HRMS AI feature follows same path: contract → data → benchmark → train → eval → deploy → service
- Platform team can evolve inference without retraining
- Clear M8–M11 milestones

**Negative:**
- `runtime/` + `providers/` directories empty until M8 — requires discipline not to shortcut
- More documentation upfront

## Future work

- M8: Implement LLM Gateway in `runtime/` + `providers/`
- M9: HRMS adapter calls gateway, not providers
- M10: Feature services for matching, summary, chat
- M11: Monitoring and continuous improvement loop

Full vision: [PLATFORM_VISION.md](../PLATFORM_VISION.md)

---
