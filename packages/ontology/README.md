# Ontology Package (shim)

Canonical TOON ontology, contracts, and document schemas.

## Source of truth

This package re-exports paths from the `ai/` workspace during incremental migration:

| Shim path | Canonical source |
|-----------|------------------|
| `contracts/` | `../../ai/contracts/` |
| `schemas/` | `../../ai/schemas/` |
| `toon/` | `../../ai/toon/` |

## Consumers

- `apps/backend/app/ai/toon/alias_registry.py`
- Documentation and future TypeScript SDK

## Do not

Duplicate YAML or TOON definitions here — link to `ai/` until full migration completes.
