# Training Pipeline

> **Superseded detail:** See [DATA_PIPELINE.md](DATA_PIPELINE.md) for the canonical reference.
> This document provides a quick operational checklist.

## Pipeline checklist

- [ ] **Raw data** in `dataset/lake/raw/`
- [ ] **Extract** → `dataset/lake/extracted/` via `dataset/extraction/`
- [ ] **Clean** → `dataset/lake/cleaned/` via `dataset/factory/ (clean stage — planned)`
- [ ] **Normalize** → `dataset/lake/normalized/` via `dataset/factory/normalizer/`
- [ ] **Validate** → ≥95% pass via `dataset/factory/validator/`
- [ ] **Split** → `dataset/lake/jsonl/{version}/` via `dataset/factory/exporter/`
- [ ] **Register dataset** → `registry/datasets/{version}.yaml`
- [ ] **Snapshot config** → `training/configs/{run_id}.yaml`
- [ ] **QLoRA train** → `training/runs/{run_id}/`
- [ ] **Promote adapter** → `models/adapters/{run_id}/`
- [ ] **Merge** → `models/merged/{model_id}/`
- [ ] **GGUF export** → `models/gguf/{model_id}-{quant}.gguf`
- [ ] **Ollama deploy** → `exports/modelfiles/{model_id}.Modelfile`
- [ ] **Evaluate** → `evaluation/reports/{eval_id}/`
- [ ] **Register model** → `registry/models/{model_id}.yaml`
- [ ] **Production** → HRMS integration (M5+)

## Config references

| Step | Config |
|------|--------|
| Training | `configs/training.yaml` → snapshot to `training/configs/` |
| Evaluation | `configs/evaluation.yaml` |
| Ollama | `configs/ollama.yaml` |
| Providers | `configs/providers.yaml` |

## Key paths (M1.5 structure)

| Artifact | Path |
|----------|------|
| Train JSONL | `dataset/lake/jsonl/parsing-v1/train.jsonl` |
| Benchmark | `dataset/lake/benchmark/parsing/v1/` |
| Adapter | `models/adapters/{run_id}/` |
| Merged | `models/merged/hrms-parsing-v1/` |
| GGUF | `models/gguf/hrms-parsing-v1-q4_K_M.gguf` |
| Registry | `registry/models/hrms-parsing-v1.yaml` |
