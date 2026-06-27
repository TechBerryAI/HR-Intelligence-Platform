# Development Conventions

Repository standards for the HRMS AI platform. All engineers must follow these conventions to ensure scalability, reproducibility, and five-year maintainability.

> **Canonical versioning rules:** [VERSIONING.md](VERSIONING.md)
> **Artifact lineage:** [ARTIFACT_LINEAGE.md](ARTIFACT_LINEAGE.md)
> **ADRs:** [adr/README.md](adr/README.md)

---

## Folder conventions

### Top-level layout

```
ai/
├── configs/           # Platform-wide YAML templates (committed)
├── dataset/lake/          # Multi-stage data lake (binaries gitignored)
├── dataset/     # Modular pipeline stages (extract → split)
├── prompts/           # Versioned prompt templates per feature
├── experiments/       # Hypothesis-driven research
├── training/          # Training runs, checkpoints, logs
├── models/            # Binary weights (base, adapters, merged, gguf)
├── registry/          # Committed metadata and lineage (source of truth)
├── evaluation/        # Metrics, reports, comparisons, regression
├── exports/           # Deployment artifacts (Modelfiles, manifests)
├── scripts/           # CLI utilities (future)
├── notebooks/         # Exploratory analysis only
└── docs/              # Architecture and pipeline documentation
```

### Stage-pure directories

Each `dataset/lake/` subdirectory represents **exactly one transformation stage**. Never mix stages (e.g. do not put cleaned text in `raw/`).

### Metadata vs binaries

| Committed to git | Gitignored |
|------------------|------------|
| `registry/` YAML files | `models/` weights |
| README files | `dataset/lake/raw/`, `extracted/`, etc. |
| `configs/*.example` | `training/runs/`, `checkpoints/` |
| `exports/modelfiles/` | `*.gguf`, `*.safetensors` |
| `prompts/*.yaml` (no secrets) | `evaluation/reports/` |
| `experiments/*/README.md` | Large experiment artifacts |

---

## Naming conventions

### Identifiers

| Entity | Pattern | Example |
|--------|---------|---------|
| Dataset version | `{feature}-v{N}` | `parsing-v1` |
| Benchmark version | `{feature}/v{N}` | `parsing/v1` |
| Training run | `{feature}-{method}-{base_short}-v{N}-{YYYYMMDD}` | `parsing-qlora-llama32-3b-v1-20260625` |
| Model ID | `hrms-{feature}-v{N}` | `hrms-parsing-v1` |
| GGUF file | `{model_id}-{quant}.gguf` | `hrms-parsing-v1-q4_K_M.gguf` |
| Eval run | `eval-{feature}-{benchmark}-v{N}-{YYYYMMDD}` | `eval-parsing-v1-20260625` |
| Experiment | `{YYYY-MM-DD}_{kebab-slug}` | `2026-06-25_parsing-qlora-baseline` |
| Ollama model | `hrms-{feature}-v{N}` | `hrms-parsing-v1` |
| Prompt version | Semver | `1.0.0` |

### Files

| Type | Pattern |
|------|---------|
| Registry record | `registry/{type}/{id}.yaml` |
| Training config snapshot | `training/configs/{run_id}.yaml` |
| Per-document artifact | `dataset/lake/{stage}/{doc_type}/{uuid}.json` |
| JSONL split | `dataset/lake/jsonl/{version}/{split}.jsonl` |
| Modelfile | `exports/modelfiles/{model_id}.Modelfile` |

### Kebab-case rules

- Use lowercase and hyphens for directories and IDs.
- No spaces or underscores in model IDs (underscores allowed in experiment IDs only).
- Sanitize HuggingFace model IDs: `meta-llama/Llama-3.2-3B-Instruct` → `meta-llama-Llama-3.2-3B-Instruct` for directory names.

---

## Dataset versioning

1. **Immutable versions** — create `parsing-v2`, never edit `parsing-v1` rows.
2. **Registry required** — every dataset version has `registry/datasets/{version}.yaml`.
3. **Checksums** — SHA-256 of every JSONL split in registry.
4. **Manifest chain** — each preprocessing stage writes `manifest.yaml` referencing the prior stage's manifest.
5. **Provenance** — record labeling source, HRMS export date, prompt version.

---

## Model versioning

1. **Semantic model IDs** — `hrms-parsing-v1`, `hrms-parsing-v2` (not date-based).
2. **Registry required** — every model has `registry/models/{model_id}.yaml`.
3. **Status lifecycle** — `candidate` → `staging` → `production` → `deprecated`.
4. **Lineage complete** — registry entry links training run, dataset, eval report, and all artifact paths.
5. **No overwrite** — new version = new model ID. Deprecate old entries.

---

## Experiment versioning

1. **Date-prefixed IDs** — `YYYY-MM-DD_slug` for chronological sorting.
2. **README required** — hypothesis, method, outcome in `experiments/{id}/README.md`.
3. **Registry on completion** — `registry/experiments/{id}.yaml` with outcome links.
4. **One variable at a time** — isolate changes for causal attribution.
5. **Promote or abandon** — no indefinite "running" experiments older than 30 days.

---

## Benchmark versioning

1. **Frozen directories** — `dataset/lake/benchmark/{feature}/v{N}/`.
2. **Registry required** — `registry/benchmarks/{feature}-v{N}.yaml`.
3. **Never train on benchmark data** — enforced by split scripts and review.
4. **Baseline recorded at creation** — Grok scores stored in registry at benchmark v1 creation.
5. **New version for new cases** — add hard cases to `v2`, don't edit `v1`.

---

## Configuration conventions

| Location | Purpose | Mutable? |
|----------|---------|----------|
| `configs/*.yaml.example` | Platform templates | Updated carefully |
| `configs/*.yaml` | Local working copy | Yes (gitignored) |
| `training/configs/{run_id}.yaml` | Frozen run snapshot | **Never** |
| `evaluation/reports/{eval_id}/config.yaml` | Frozen eval snapshot | **Never** |

Secrets: environment variables only. `${VAR_NAME}` or `${VAR_NAME:default}` in YAML.

---

## Prompt conventions

- One YAML per feature per doc type: `prompts/resume_parser.yaml`, `prompts/jd_parser.yaml`.
- Future: `prompts/summary.yaml`, `prompts/interview_questions.yaml`.
- Bump `version` field on any text change.
- Record version in registry entries, training configs, and eval reports.

---

## Git and branching

| Branch pattern | Use |
|----------------|-----|
| `ai/data-*` | Dataset and preprocessing |
| `ai/exp-*` | Experiments |
| `ai/train-*` | Training runs and registry updates |
| `ai/eval-*` | Evaluation and benchmark |
| `ai/docs-*` | Documentation only |

Keep AI branches separate from HRMS feature branches until M5 integration.

---

## HRMS contract compliance

All model outputs must:

1. Parse via TOON/JSON (`toon_loads_flex` compatible)
2. Pass `validate_toon_format()` for the document type
3. Include correct `type` field
4. Match field shapes expected by ATS and frontend

---

## Related documents

- [DATA_PIPELINE.md](DATA_PIPELINE.md) — canonical pipeline
- [REPRODUCIBILITY.md](REPRODUCIBILITY.md) — six-month replay guide
- [registry/schema.yaml](../registry/schema.yaml) — registry field definitions
