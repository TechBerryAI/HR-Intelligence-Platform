# Configuration templates

Platform-wide YAML templates. Copy `*.example` files, remove `.example`, customize locally.

## Templates

| File | Purpose |
|------|---------|
| `training.yaml.example` | QLoRA hyperparameters, dataset version, registry links |
| `evaluation.yaml.example` | Multi-provider benchmark, regression gates |
| `ollama.yaml.example` | GGUF path, Modelfile, registry model ID |
| `providers.yaml.example` | Primary/fallback routing (future adapter) |

## Two-level config system

| Location | Role |
|----------|------|
| `configs/*.yaml` | Active working templates (local, may change) |
| `training/configs/{run_id}.yaml` | **Frozen** snapshot at run start (reproducibility) |
| `evaluation/reports/{eval_id}/config.yaml` | **Frozen** eval snapshot |

## Path conventions (M1.5)

Configs reference versioned paths:

```yaml
dataset:
  version: parsing-v1
  train_path: datasets/jsonl/parsing-v1/train.jsonl
  registry: registry/datasets/parsing-v1.yaml

benchmark:
  version: parsing/v1
  registry: registry/benchmarks/parsing-v1.yaml
```

## Secrets

Use `${ENV_VAR}` placeholders only. Never commit API keys.
