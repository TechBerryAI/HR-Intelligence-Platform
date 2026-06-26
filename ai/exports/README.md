# Deployment exports

Non-weight deployment artifacts for Ollama and future HRMS integration. **GGUF weight files live in `models/gguf/`** — this directory holds everything needed to deploy them.

## Layout

```
exports/
├── modelfiles/              # Ollama Modelfile per model version
├── manifests/               # Deployment manifests (env, health checks)
└── integration/             # Future: HRMS adapter config bundles
```

## What belongs here vs `models/gguf/`

| Artifact | Location |
|----------|----------|
| `.gguf` weight files | `models/gguf/` |
| Ollama Modelfile | `exports/modelfiles/` |
| Serve / health check config | `exports/manifests/` |
| Provider routing snapshot for HRMS | `exports/integration/` (M5) |

## Modelfile naming

```
exports/modelfiles/{model_id}.Modelfile
```

Example: `exports/modelfiles/hrms-parsing-v1.Modelfile`

Referenced from `registry/models/hrms-parsing-v1.yaml` → `deployment.modelfile`.

## Git policy

Modelfiles and manifests: **committed** (no secrets).
Integration bundles: **committed** after M5 (config only, no keys).
