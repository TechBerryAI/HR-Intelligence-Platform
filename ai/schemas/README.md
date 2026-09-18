# Document Schemas

Normalized document schemas composed from domain contracts.

## What is this?

YAML schemas define versioned document shapes (`resume`, `job_description`, `candidate`) used at normalization boundaries. They are **not** JSON Schema and **not** TOON wire format.

## Why does it exist?

Schemas sit between contracts and TOON. They specify fields, nesting, and validation rules before projection to TOON via `ai/toon/v1/mappings/`.

## What belongs here?

| Path | Purpose |
|------|---------|
| `manifest.yaml` | Schema registry |
| `resume.yaml`, `job_description.yaml`, `candidate.yaml` | Document schemas |
| `validation/rules.yaml` | Normalized validation rules |
| `mappings/manifest.yaml` | TOON projection registry (pointers only) |
| `examples/` | Sample normalized instances |

## What should never be placed here?

- TOON ontology definitions → `ai/toon/v1/`
- Runtime JSON Schema → `ai/capabilities/*/schema.json`
- SQL table definitions → `apps/backend/alembic/` (migrations)

## Authority chain position

```
contracts/ → schemas/ (this) → knowledge/ → toon/v1/ → backend/toon.py
```

## Consumers

| Consumer | Usage |
|----------|-------|
| TOON mappings | `ai/toon/v1/mappings/*.yaml` reference schemas |
| Dataset normalization (future) | `dataset/factory/normalizer/` |
| Documentation | `docs/AI.md` · YAML schemas in this package |

## Related documentation

- [Contracts](../contracts/README.md)
- [TOON](../toon/README.md)
- [Mappings registry](mappings/manifest.yaml)
