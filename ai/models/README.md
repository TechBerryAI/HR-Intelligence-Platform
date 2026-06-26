# Models

Binary model artifacts organized by lifecycle stage. **Metadata lives in `registry/`** — this directory holds weights only.

## Directory layout

```
models/
├── base/       # Downloaded foundation models (HF cache or local copy)
├── adapters/   # LoRA / QLoRA adapter weights per training run
├── merged/     # Full merged models (base + adapter)
└── gguf/       # Quantized GGUF files for Ollama inference
```

## What belongs where

| Directory | Contents | Source | Consumer |
|-----------|----------|--------|----------|
| `base/` | Foundation model weights (e.g. Llama 3.2 3B) | Hugging Face download | Training |
| `adapters/{run_id}/` | LoRA adapter checkpoints | `training/runs/` | Merge step |
| `merged/{model_id}/` | Full-precision merged HF model | Merge script | GGUF export |
| `gguf/{model_id}.gguf` | Quantized inference weights | GGUF export | Ollama |

## Model ID convention

```
hrms-{feature}-v{N}
```

Examples: `hrms-parsing-v1`, `hrms-parsing-v2`, `hrms-summary-v1`

## Git policy

All weight directories are **gitignored**. Only README files are committed. Paths are recorded in `registry/models/`.

## Lineage

Every artifact traces back through the registry:

```
registry/models/hrms-parsing-v1.yaml
  → training_run: parsing-qlora-llama32-3b-v1-20260625
  → dataset: parsing-v1
  → adapter: models/adapters/parsing-qlora-llama32-3b-v1-20260625/
  → merged: models/merged/hrms-parsing-v1/
  → gguf: models/gguf/hrms-parsing-v1-q4_K_M.gguf
```

## Deployment artifacts

Ollama Modelfiles and serve manifests live in `exports/` — not here. See [exports/README.md](../exports/README.md).
