# AI Platform Architecture

Production-grade machine learning platform for the HRMS recruitment stack. Designed to power parsing, matching, ranking, summarization, and future AI features for five+ years.

---

## Platform vision

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        HRMS AI PLATFORM (ai/)                           │
│                                                                         │
│  ┌─────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │  Data   │  │ Preprocessing│  │ Prompts  │  │   Experiments     │  │
│  │  Lake   │→ │   Pipeline   │→ │ Registry │  │   (research)      │  │
│  └─────────┘  └──────────────┘  └──────────┘  └───────────────────┘  │
│       │                │                │                  │            │
│       ▼                ▼                ▼                  ▼            │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                        Training / Models                          │  │
│  │   training/runs → models/adapters → merged → gguf              │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │              Evaluation (metrics, comparisons, regression)        │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │   Registry (lineage)  +  Exports (deployment)                  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                          future M5+│ provider adapter
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     HRMS Backend (unchanged until M5)                   │
│   parsing_routes → llm_service → toon → ats_service                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Architectural layers

| Layer | Directories | Responsibility |
|-------|-------------|----------------|
| **Data** | `datasets/` | Multi-stage data lake |
| **Transform** | `preprocessing/` | Modular extract → split pipeline |
| **Configuration** | `configs/`, `prompts/` | Templates and versioned prompts |
| **Research** | `experiments/` | Hypothesis-driven exploration (EXP-*) |
| **Training** | `training/`, `models/` | Fine-tune, merge, quantize |
| **Quality** | `evaluation/` | Benchmark, compare, regress |
| **Governance** | `registry/`, `governance/` | Six sub-registries, standards |
| **Deploy** | `exports/` | Modelfiles, integration bundles |
| **Platform runtime** | `platform/` | Inference, services, providers, monitoring (M8+) |
| **Utilities** | `scripts/`, `notebooks/` | CLI and exploration |

### Registry subsystems

| Sub-registry | IDs | Purpose |
|--------------|-----|---------|
| `registry/models/` | `hrms-*-vN` | Model lineage and promotion |
| `registry/datasets/` | `DS-*-v*` | Dataset versions and checksums |
| `registry/benchmarks/` | `BENCH-*-vN` | Frozen eval sets |
| `registry/prompts/` | `PROMPT-NNNN` | Prompt version history |
| `registry/providers/` | `PROV-*` | Provider capabilities |
| `registry/evaluations/` | `EVAL-*` | Eval run records |
| `registry/deployments/` | `DEPLOY-*` | Deployment snapshots |
| `registry/experiments/` | `EXP-NNNN` | Experiment outcomes |

**Dependency rule:** upper layers depend on lower layers. `registry/` is cross-cutting metadata — referenced by all layers but depends on none.

---

## Key architectural decisions

### 1. Separate registry from model binaries

**Decision:** `registry/` holds committed YAML metadata; `models/` holds gitignored weights.

**Rationale:** Enables full lineage tracking in git without multi-GB commits. An engineer can understand platform state from registry alone.

### 2. Multi-stage dataset lake

**Decision:** Replace flat `datasets/resumes/` + `processed/` with staged `raw/` → `extracted/` → `cleaned/` → `normalized/` → `jsonl/`.

**Rationale:** Each stage is independently re-runnable, auditable, and debuggable. Supports future features that need different stage entry points (e.g. summarization from `cleaned/`).

### 3. Modular preprocessing

**Decision:** Five stage modules (`extract/`, `clean/`, `normalize/`, `validate/`, `split/`) instead of one `preprocessing/` folder.

**Rationale:** Teams can own stages independently. Validation gates prevent bad data from reaching training.

### 4. Experiments as first-class citizens

**Decision:** Top-level `experiments/` separate from `training/runs/`.

**Rationale:** Research is messy; production training is not. Experiments may fail or pivot without polluting training artifact directories.

### 5. Training config snapshots

**Decision:** `training/configs/{run_id}.yaml` frozen per run, separate from mutable `configs/training.yaml`.

**Rationale:** Reproducibility requires knowing exact hyperparameters used, not current template values.

### 6. Evaluation decomposition

**Decision:** `metrics/`, `reports/`, `comparisons/`, `regression/` instead of flat `reports/`.

**Rationale:** Supports multi-provider comparison (Grok vs Ollama vs OpenAI vs Claude vs fine-tuned) and CI regression gates as distinct concerns.

### 7. GGUF under models/, deployment under exports/

**Decision:** `models/gguf/` for weight files; `exports/modelfiles/` for Ollama Modelfiles.

**Rationale:** Weights are model artifacts; Modelfiles are deployment configuration. Clean separation for registry lineage.

### 8. Prompts remain top-level

**Decision:** Keep `prompts/` at platform root, not nested under features.

**Rationale:** Prompts are shared across preprocessing (labeling), training (instruction format), evaluation (inference), and deployment (Ollama system message). Central location avoids duplication.

### 9. No provider abstraction yet

**Decision:** Milestone 1.5 is architecture only — no `providers/` package.

**Rationale:** User explicitly deferred implementation. `configs/providers.yaml.example` documents future routing without code.

### 10. Platform configs vs run configs

| `configs/` (top-level) | `training/configs/` |
|------------------------|---------------------|
| Working templates | Immutable run snapshots |
| Shared across features | Per training run |
| `.example` committed | Run-specific, optionally committed |

---

## Feature roadmap alignment

| Feature | Data entry | Model prefix | Benchmark |
|---------|------------|--------------|-----------|
| Resume parsing | `raw/resumes/` | `hrms-parsing-*` | `benchmark/parsing/` |
| JD parsing | `raw/job_descriptions/` | `hrms-parsing-*` | `benchmark/parsing/` |
| Bulk parsing | Same pipeline | Same | Same |
| Resume matching | `normalized/` pairs | `hrms-matching-*` | future |
| Candidate ranking | embeddings | `hrms-ranking-*` | future |
| Summarization | `cleaned/` | `hrms-summary-*` | future |
| Interview questions | `normalized/` | `hrms-interview-*` | future |
| Skill extraction | `normalized/` skills | `hrms-skills-*` | future |
| Skill normalization | ontology | `hrms-skills-norm-*` | future |
| Salary intelligence | external + normalized | `hrms-salary-*` | future |
| AI chat assistant | RAG corpus | `hrms-chat-*` | future |

---

## Boundaries with HRMS

| Concern | HRMS | AI Platform |
|---------|------|-------------|
| HTTP APIs | `parsing_routes.py` | None until M5 |
| LLM inference (prod) | `llm_service.py` | Evaluation only |
| TOON schema | `toon.py` (authority today) | Mirrored in validation |
| ATS matching | `ats_service.py` | Future: optional LLM rerank |
| Database | Read/write | Read-only export (future) |

---

## Security

- Secrets in `ai/.env` only (gitignored).
- No PII in committed files.
- Raw documents gitignored.
- Registry contains paths and metrics only — never document content.

---

## Documentation index

| Document | Scope |
|----------|-------|
| [PLATFORM_VISION.md](PLATFORM_VISION.md) | AI platform paradigm |
| [DATA_PIPELINE.md](DATA_PIPELINE.md) | **Canonical** pipeline reference |
| [DATA_CONTRACTS.md](DATA_CONTRACTS.md) | Domain schemas |
| [VERSIONING.md](VERSIONING.md) | Naming and version rules |
| [ARTIFACT_LINEAGE.md](ARTIFACT_LINEAGE.md) | ML artifact model |
| [BENCHMARK_STRATEGY.md](BENCHMARK_STRATEGY.md) | Eval categories |
| [AI_ENGINEERING.md](AI_ENGINEERING.md) | Engineering handbook |
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) | Six-month replay |
| [CONVENTIONS.md](CONVENTIONS.md) | Folder standards |
| [MODEL_LIFECYCLE.md](MODEL_LIFECYCLE.md) | Model promotion |
| [ROADMAP.md](ROADMAP.md) | M1–M11 milestones |
| [adr/README.md](adr/README.md) | Architecture Decision Records |
| [HRMS_DEPENDENCY_MAP.md](HRMS_DEPENDENCY_MAP.md) | Production AI map |
