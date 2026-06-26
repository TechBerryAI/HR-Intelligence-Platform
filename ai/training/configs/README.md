# Training run configs

Immutable configuration snapshots captured at the start of each training run.

## Purpose

Reproducing a training run six months later requires the **exact** hyperparameters, dataset version, and prompt version used — not the latest `configs/training.yaml`.

## Naming

```
{run_id}.yaml
```

Example: `parsing-qlora-llama32-3b-v1-20260625.yaml`

## Required fields in every snapshot

```yaml
run_id: parsing-qlora-llama32-3b-v1-20260625
created_at: "2026-06-25T14:30:00Z"
git_commit: abc1234                    # AI workspace commit at run start
dataset_version: parsing-v1            # registry/datasets/parsing-v1.yaml
prompt_version: "1.0.0"
base_model: meta-llama/Llama-3.2-3B-Instruct
experiment_ref: experiments/2026-06-25_parsing-qlora-baseline  # optional
# ... full training hyperparameters ...
```

## Git policy

- Snapshots **may** be committed for production runs (no secrets).
- Never store API keys or WandB tokens in snapshots — reference env vars only.

## Relationship to top-level `configs/`

| `configs/training.yaml` | Active working template — may change |
| `training/configs/{run_id}.yaml` | Frozen record of what was actually run |
