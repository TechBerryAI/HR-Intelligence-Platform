# Scripts

CLI utilities for the AI platform. Scripts are added incrementally per roadmap milestone.

## Pipeline scripts (M2)

| Script | Stage | Input → Output |
|--------|-------|----------------|
| `extract_batch.py` | extract | `datasets/raw/` → `datasets/extracted/` |
| `clean_batch.py` | clean | `extracted/` → `cleaned/` |
| `normalize_batch.py` | normalize | `cleaned/` → `normalized/` |
| `validate_dataset.py` | validate | `normalized/` → report + gate |
| `split_dataset.py` | split | `normalized/` → `jsonl/{version}/` |
| `export_hrms_dataset.py` | ingest | HRMS DB → `datasets/raw/` or `normalized/` |

## Training scripts (M4)

| Script | Purpose |
|--------|---------|
| `train_qlora.py` | QLoRA training from `training/configs/{run_id}.yaml` |
| `merge_adapter.py` | Merge to `models/merged/` |
| `export_gguf.py` | Export to `models/gguf/` |

## Evaluation scripts (M3)

| Script | Purpose |
|--------|---------|
| `benchmark_providers.py` | Multi-provider eval → `evaluation/reports/` |
| `compare_reports.py` | Cross-report analysis → `evaluation/comparisons/` |

## Deployment scripts (M4)

| Script | Purpose |
|--------|---------|
| `deploy_ollama.py` | Create Ollama model from `exports/modelfiles/` |

## Registry scripts (M2)

| Script | Purpose |
|--------|---------|
| `validate_registry.py` | Validate YAML against `registry/schema.yaml` |

## Conventions

- Typer CLI with `--config` flag
- Load secrets from `ai/.env`
- Write manifests at each pipeline stage
- Register versions in `registry/` on completion
