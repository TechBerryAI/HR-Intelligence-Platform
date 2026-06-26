# Training

Experiment execution layer for fine-tuning, LoRA, and QLoRA. Supports many concurrent and historical experiments with full artifact traceability.

## Directory layout

```
training/
├── README.md           # This file
├── configs/            # Immutable per-run config snapshots
├── runs/               # One directory per training run
├── checkpoints/        # Best / latest checkpoint symlinks or copies
└── logs/               # Plain-text and structured training logs
```

## What belongs where

| Directory | Contents | Git | Lifecycle |
|-----------|----------|-----|-----------|
| `configs/` | Frozen copy of `configs/training.yaml` + overrides at run start | Per-run snapshot committed optionally | Permanent |
| `runs/{run_id}/` | Full run artifact tree (adapter, metrics, wandb id) | Gitignored | Archive after merge |
| `checkpoints/` | Pointers to best checkpoint per run | Gitignored | Delete after merge to `models/merged/` |
| `logs/` | stdout captures, loss curves CSV | Gitignored | 90-day retention |

## Run directory structure

```
runs/{run_id}/
├── config.yaml              # Snapshot from training/configs/
├── metrics.json             # Final train/val metrics
├── adapter/                 # LoRA weights → promoted to models/adapters/
├── tokenizer/               # If customized
├── wandb_run_id.txt         # External tracker reference
└── README.md                # Human notes on run (optional)
```

## Run ID convention

```
{feature}-{method}-{base_model_short}-v{N}-{YYYYMMDD}
```

Example: `parsing-qlora-llama32-3b-v1-20260625`

## Config hierarchy

| Location | Role |
|----------|------|
| `configs/training.yaml.example` | Platform template (committed) |
| `configs/training.yaml` | Local active template (gitignored) |
| `training/configs/{run_id}.yaml` | Immutable snapshot at run start |
| `registry/models/{model_id}.yaml` | Links run to promoted model |

## Workflow

1. Register experiment intent in `experiments/` (optional for ad-hoc runs).
2. Snapshot config → `training/configs/{run_id}.yaml`.
3. Execute training (future: `scripts/train_qlora.py`).
4. Checkpoints land in `training/runs/{run_id}/`.
5. Promote best adapter → `models/adapters/{run_id}/`.
6. Merge → `models/merged/{model_id}/`.
7. Register model in `registry/models/`.

## Multi-feature training (long-term)

| Feature | Suggested run prefix | Dataset |
|---------|---------------------|---------|
| Resume + JD parsing | `parsing-qlora-*` | `datasets/jsonl/parsing-v*` |
| Summarization | `summary-qlora-*` | `datasets/jsonl/summary-v*` (future) |
| Skill normalization | `skills-qlora-*` | `datasets/jsonl/skills-v*` (future) |

## Hardware notes

Document GPU, CUDA version, and driver in each run's `config.yaml` for reproducibility. See [docs/REPRODUCIBILITY.md](../docs/REPRODUCIBILITY.md).
