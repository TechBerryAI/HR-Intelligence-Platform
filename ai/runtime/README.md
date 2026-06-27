# AI Runtime

Central orchestration layer that executes AI capabilities against configured providers.

## What is this?

The runtime loads capabilities, resolves prompts and schemas, routes requests to providers (with retry and fallback), validates outputs, and records metrics and health.

## Why does it exist?

Capabilities define *what* to run; providers define *how* to call an LLM; the runtime wires them together with a stable public API.

## What belongs here?

| Path | Purpose |
|------|---------|
| `core/` | `AIRuntime`, task executor, public API |
| `config/` | Default YAML configs and loader |
| `registry/` | Capability, prompt, schema, model, task registries |
| `validation/` | Output validation against capability rules |
| `cli/` | `python -m runtime.cli.main` |
| `tests/` | Runtime integration tests |

## What should never be placed here?

- LLM provider implementations → `ai/providers/`
- Capability definitions (prompts, schemas) → `ai/capabilities/`
- Dataset pipelines → `ai/dataset/`
- HRMS business logic → `backend/`

## Dependencies

| Consumes | From |
|----------|------|
| Capabilities | `ai/capabilities/` |
| Providers | `ai/providers/` |
| Config templates | `ai/configs/` (optional local copies) |

## Consumers

| Consumer | Usage |
|----------|-------|
| Proposal Generator | `dataset/proposals/engine/runtime_client.py` |
| CLI | `runtime/cli/main.py` |
| Future HRMS integration | Milestone 9 |

## Extension points

1. Add a provider → `ai/providers/` + register in `config/runtime.default.yaml`
2. Add a capability → `ai/capabilities/<name>/` (auto-discovered via `capabilities_dir`)
3. Override routing → copy `config/runtime.default.yaml` locally

## Quick start

```bash
cd ai
source .venv/bin/activate
python -m runtime.cli.main --help
pytest runtime/tests/
```

## Configuration

Default config: `config/runtime.default.yaml`

Required keys when using capabilities (recommended):

```yaml
runtime:
  capabilities_dir: ../../capabilities
  models_config_path: models.default.yaml
```

Legacy `prompts_dir` / `schemas_dir` are optional fallbacks when `capabilities_dir` is unset.

## Related documentation

- [Capabilities](../capabilities/README.md)
- [Providers](../providers/README.md)
- [AI platform overview](../README.md)
