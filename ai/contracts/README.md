# Domain Contracts

Machine-readable domain contracts for HR entities and documents.

## What is this?

YAML contracts define the semantic shape of HR domain objects (resume, experience, skill, etc.) before normalization, validation, or TOON projection.

## Why does it exist?

Contracts are the first layer in the authority chain. Schemas compose contracts; knowledge bases enrich them; TOON maps project them to wire format.

## What belongs here?

| File | Purpose |
|------|---------|
| `manifest.yaml` | Contract registry |
| `resume.yaml`, `job_description.yaml`, `candidate.yaml` | Document contracts |
| `skill.yaml`, `experience.yaml`, … | Entity contracts |
| `_envelope.yaml` | Shared envelope fields |
| `_templates/` | Contract authoring template |

## What should never be placed here?

- JSON Schema for runtime validation → `ai/capabilities/*/schema.json`
- TOON wire mappings → `ai/toon/v1/mappings/`
- PostgreSQL DDL → `backend/schema_pg/`

## Authority chain position

```
contracts/ → schemas/ → knowledge/ → toon/v1/ → backend/toon.py
```

## Consumers

| Consumer | Usage |
|----------|-------|
| Document schemas | `ai/schemas/*.yaml` reference contracts |
| Knowledge bases | Alias lookup during normalization |
| Documentation | `docs/ADRS.md` · YAML contracts in this package |

## Extension points

1. Add contract YAML + entry in `manifest.yaml`
2. Update corresponding schema in `ai/schemas/`
3. Update TOON mapping if wire format changes

## Related documentation

- [Schemas](../schemas/README.md)
- [DATA_CONTRACTS.md](../docs/DATA_CONTRACTS.md)
- [foundation.json](../foundation.json)
