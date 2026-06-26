# Base models

Downloaded foundation model weights used as QLoRA/LoRA training bases.

## Layout

```
base/{hf_model_id_sanitized}/
```

Example: `base/meta-llama-Llama-3.2-3B-Instruct/`

## Policy

- Gitignored (large binaries).
- Record HF revision hash in `training/configs/{run_id}.yaml`.
- Prefer pinning to a specific HF commit for reproducibility.

## Supported bases (initial)

| Model | Use case | VRAM (QLoRA 4-bit) |
|-------|----------|-------------------|
| Llama 3.2 3B Instruct | Parsing (primary) | ~8 GB |
| Mistral 7B Instruct | Parsing (quality) | ~16 GB |
| Phi-3 mini | Fast experiments | ~6 GB |
