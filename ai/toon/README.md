# TOON — Token-Oriented Object Notation

Canonical ontology package for HRMS structured documents. TOON is the wire format for resumes, job descriptions, and ATS results across the platform.

## Authority chain

| Layer | Path | Role |
|-------|------|------|
| **Runtime implementation** | `backend/toon.py` | Serialize/parse (read-only reference) |
| **Type definitions** | `ai/toon/v1/types/toon.ts` | TypeScript contracts |
| **Ontology (this package)** | `ai/toon/v1/` | Mappings, validation, vocabulary, examples |
| **Normalized schemas** | `ai/schemas/` | Document schemas that project to TOON |
| **Production validation** | `backend/parsing_utils.py` | HRMS runtime validation |

**Single source of truth for TOON ontology:** `ai/toon/v1/`.  
Do not duplicate mappings or validation rules elsewhere.

## Version registry

See [`versions.yaml`](versions.yaml) for active versions.

## Quick navigation

```
ai/toon/
├── README.md              ← you are here
├── versions.yaml          ← version registry
└── v1/                    ← current active version
    ├── ontology/          ← document types and relationships
    ├── dictionary/        ← field glossary and aliases
    ├── vocabulary/        ← wire format types (datatypes)
    ├── validation/        ← wire-format validation rules
    ├── normalization/     ← projection transforms
    ├── mappings/          ← per-document projection maps
    ├── types/             ← TypeScript contracts (toon.ts)
    ├── examples/          ← wire-format samples
    ├── benchmarks/        ← TOON conformance benchmarks
    └── tests/             ← ontology and mapping tests
```

## Related documentation

- [CURRENT_TOON_SCHEMA.md](../docs/current_system/CURRENT_TOON_SCHEMA.md) — reverse-engineered production spec
- [foundation.json](../foundation.json) — M2 foundation manifest
- [schemas/manifest.yaml](../schemas/manifest.yaml) — normalized document schemas
