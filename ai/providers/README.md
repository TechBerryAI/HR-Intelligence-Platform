# AI Providers

LLM provider implementations consumed by the AI Runtime.

## What is this?

Providers translate runtime inference requests into provider-specific API calls and return normalized responses. Each provider implements `BaseProvider`.

## Why does it exist?

The runtime stays provider-agnostic. Swapping Ollama for another backend requires only a new provider module and config change.

## What belongs here?

| Path | Purpose |
|------|---------|
| `base.py` | `BaseProvider` interface |
| `factory.py` | Provider instantiation by type |
| `manager.py` | Routing, fallback, health |
| `mock.py` | Deterministic provider for tests |
| `ollama/` | Ollama HTTP client and provider |

## What should never be placed here?

- Task orchestration → `ai/runtime/`
- Capability prompts/schemas → `ai/capabilities/`
- HRMS API keys / Flask config → `backend/`

## Dependencies

| Consumes | From |
|----------|------|
| Runtime types | `runtime/interfaces/` |
| Runtime exceptions | `runtime/exceptions/` |

## Consumers

| Consumer | Usage |
|----------|-------|
| AI Runtime | `runtime/core/executor.py` via `ProviderManager` |
| Tests | `providers/ollama/tests/` |

## Extension points

1. Create `providers/<name>/` with client + provider class
2. Register type in `providers/factory.py`
3. Add provider block to `runtime/config/runtime.default.yaml`

## Quick start

```bash
cd ai
pytest providers/ollama/tests/
```

## Related documentation

- [Runtime](../runtime/README.md)
- [Configs](../configs/README.md) — provider YAML templates
