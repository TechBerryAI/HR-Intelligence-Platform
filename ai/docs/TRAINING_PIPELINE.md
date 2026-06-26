# Training Pipeline

> **Superseded detail:** See [DATA_PIPELINE.md](DATA_PIPELINE.md) for the canonical reference.
> This document provides a quick operational checklist.

## Pipeline checklist

- [ ] **Raw data** in `datasets/raw/`
- [ ] **Extract** → `datasets/extracted/` via `preprocessing/extract/`
- [ ] **Clean** → `datasets/cleaned/` via `preprocessing/clean/`
- [ ] **Normalize** → `datasets/normalized/` via `preprocessing/normalize/`
- [ ] **Validate** → ≥95% pass via `preprocessing/validate/`
- [ ] **Split** → `datasets/jsonl/{version}/` via `preprocessing/split/`
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
| Train JSONL | `datasets/jsonl/parsing-v1/train.jsonl` |
| Benchmark | `datasets/benchmark/parsing/v1/` |
| Adapter | `models/adapters/{run_id}/` |
| Merged | `models/merged/hrms-parsing-v1/` |
| GGUF | `models/gguf/hrms-parsing-v1-q4_K_M.gguf` |
| Registry | `registry/models/hrms-parsing-v1.yaml` |
