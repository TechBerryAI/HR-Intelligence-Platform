# Reproducibility Guide

Design goal: **an engineer joining six months from now can reproduce any training run, evaluation, or promoted model** using only committed metadata, pinned dependencies, and documented artifact paths.

---

## Reproducibility pillars

| Pillar | Mechanism |
|--------|-----------|
| **Config immutability** | `training/configs/{run_id}.yaml` frozen at run start |
| **Dataset versioning** | `registry/datasets/` + checksums in manifests |
| **Model lineage** | `registry/models/` links run → adapter → merged → gguf |
| **Benchmark freezing** | `dataset/lake/benchmark/` versioned directories, never mutated |
| **Prompt versioning** | Semver in `prompts/*.yaml` recorded in every registry entry |
| **Dependency pinning** | `requirements.txt` with version ranges |
| **Git commit tracking** | `git_commit` field in manifests and training configs |

---

## Directory conventions for reproducibility

### Data artifacts

```
datasets/{stage}/{doc_type}/{id}.json     # Per-document records
datasets/jsonl/{version}/train.jsonl      # Versioned splits
dataset/lake/benchmark/{feature}/v{N}/        # Frozen eval sets
```

**Never overwrite a versioned path.** Create `v2`, `v3`, etc.

### Training artifacts

```
training/configs/{run_id}.yaml              # Immutable run config
training/runs/{run_id}/                     # Full run output
models/adapters/{run_id}/                   # Promoted adapter
models/merged/{model_id}/                   # Merged weights
models/gguf/{model_id}-{quant}.gguf       # Inference weights
```

### Evaluation artifacts

```
evaluation/reports/{eval_id}/summary.json   # Scores
evaluation/regression/baseline.yaml         # Production baseline
registry/models/{model_id}.yaml             # Links all of the above
```

---

## Artifact naming conventions

| Artifact | Pattern | Example |
|----------|---------|---------|
| Dataset version | `{feature}-v{N}` | `parsing-v1` |
| Benchmark version | `{feature}/v{N}` | `parsing/v1` |
| Training run | `{feature}-{method}-{base}-v{N}-{YYYYMMDD}` | `parsing-qlora-llama32-3b-v1-20260625` |
| Model ID | `hrms-{feature}-v{N}` | `hrms-parsing-v1` |
| GGUF file | `{model_id}-{quant}.gguf` | `hrms-parsing-v1-q4_K_M.gguf` |
| Eval run | `eval-{feature}-{benchmark}-v{N}-{YYYYMMDD}` | `eval-parsing-v1-20260625` |
| Experiment | `{YYYY-MM-DD}_{slug}` | `2026-06-25_parsing-qlora-baseline` |

---

## Dataset versioning

1. Create splits in `dataset/lake/jsonl/{version}/`.
2. Write `registry/datasets/{version}.yaml` with:
   - Record counts per split
   - SHA-256 checksums of each JSONL file
   - `prompt_version` used for instruction formatting
   - Provenance (HRMS export date, labeling method)
3. Reference `{version}` in training config — never a raw path that might change.

**Reproducing a dataset:** Re-run preprocessing pipeline with same `raw/` inputs and `pipeline_version`, verify checksums match registry.

---

## Model lineage

Every promoted model has a complete chain in `registry/models/`:

```
registry/models/hrms-parsing-v1.yaml
  │
  ├─ training.config → training/configs/parsing-qlora-llama32-3b-v1-20260625.yaml
  │     ├─ dataset: parsing-v1 → registry/datasets/parsing-v1.yaml
  │     ├─ prompt_version: 1.0.0
  │     ├─ base_model: meta-llama/Llama-3.2-3B-Instruct
  │     └─ git_commit: abc1234
  │
  ├─ artifacts.adapter → models/adapters/parsing-qlora-llama32-3b-v1-20260625/
  ├─ artifacts.merged  → models/merged/hrms-parsing-v1/
  ├─ artifacts.gguf    → models/gguf/hrms-parsing-v1-q4_K_M.gguf
  │
  └─ evaluation.report → evaluation/reports/eval-parsing-v1-20260625/
        └─ benchmark: parsing/v1 → registry/benchmarks/parsing-v1.yaml
```

**Reproducing a model:**

1. Check out AI workspace at `git_commit` from training config.
2. Recreate dataset per `registry/datasets/parsing-v1.yaml` checksums.
3. Run training with `training/configs/{run_id}.yaml`.
4. Merge adapter, export GGUF, evaluate against `benchmark/parsing/v1/`.
5. Compare metrics to `registry/models/hrms-parsing-v1.yaml` → `evaluation.metrics`.

---

## Experiment versioning

| Field | Location |
|-------|----------|
| Hypothesis | `experiments/{id}/README.md` |
| Variables | `experiments/{id}/config.yaml` |
| Outcome | `registry/experiments/{id}.yaml` |
| Links to runs | `experiments/{id}/links.yaml` |

Experiments that produce models must link to `registry/models/` on completion.

---

## Benchmark versioning

| Rule | Rationale |
|------|-----------|
| New directory per version (`v1/`, `v2/`) | Prevents silent benchmark drift |
| `frozen: true` in registry | Signals immutability |
| Baseline metrics recorded at creation | Enables historical comparison |
| Never train on benchmark rows | Prevents overfitting to eval set |

**Reproducing an evaluation:**

1. Load `evaluation/reports/{eval_id}/config.yaml` (frozen snapshot).
2. Verify benchmark checksums against `registry/benchmarks/`.
3. Run eval with same providers, prompts, and model versions.
4. Compare `summary.json` to archived report.

---

## Environment reproducibility

### Python dependencies

```bash
pip install -r requirements.txt
# Future: requirements-lock.txt with exact pins
```

### GPU environment

Record in every `training/configs/{run_id}.yaml`:

```yaml
environment:
  gpu: NVIDIA A100 40GB
  cuda: "12.1"
  driver: "535.54.03"
  torch: "2.1.2"
  transformers: "4.38.2"
```

### Random seeds

- Platform default: `AI_RANDOM_SEED=42` (`.env.example`)
- Record per-run seed in training config.
- Set seeds for Python, NumPy, PyTorch, and CUDA in training script (future).

---

## Six-month replay checklist

To reproduce model `hrms-parsing-v1`:

- [ ] Clone repo; checkout `git_commit` from training config
- [ ] `pip install -r requirements.txt` (or locked version)
- [ ] Restore `dataset/lake/jsonl/parsing-v1/` (verify checksums vs registry)
- [ ] Restore or re-download `models/base/` foundation model at pinned HF revision
- [ ] Run training with `training/configs/{run_id}.yaml`
- [ ] Merge → `models/merged/hrms-parsing-v1/`
- [ ] Export GGUF → `models/gguf/hrms-parsing-v1-q4_K_M.gguf`
- [ ] Evaluate vs `dataset/lake/benchmark/parsing/v1/`
- [ ] Compare metrics to `registry/models/hrms-parsing-v1.yaml`

---

## What is NOT required for reproducibility

- Raw PDF files (if `extracted/` or `normalized/` checksums match)
- WandB account (metrics duplicated in `training/runs/{run_id}/metrics.json`)
- Cloud API keys (for re-training; needed only for Grok baseline re-evaluation)

---

## Related documents

- [DATA_PIPELINE.md](DATA_PIPELINE.md) — canonical pipeline stages
- [CONVENTIONS.md](CONVENTIONS.md) — naming standards
- [registry/README.md](../registry/README.md) — registry schema
