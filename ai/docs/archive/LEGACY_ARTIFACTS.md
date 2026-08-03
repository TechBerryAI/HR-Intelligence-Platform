# Archive — Legacy Artifacts

Documentation of retired paths and compatibility notes.

## Purpose

When paths were consolidated during repository modernization and the Document
Intelligence Engine migration, some references remained in git history or
external docs. This file explains what was removed and where to look now.

## Retired paths (do not recreate)

| Retired path | Replaced by | Notes |
|--------------|-------------|-------|
| `shared/types/` | `ai/toon/v1/types/toon.ts` | TOON owns TypeScript contracts |
| Frontend `mapResumeTOONToForm` / `mapJDTOONToForm` | `app.ai.document_intelligence.mapping` + Form DTOs | FE must not map TOON |
| `app/ai/parser/enrichment/resume_inference.py` | `repair_resume_toon` in runtime_adapter | Deleted |
| `call_parsing_api` in parsing_storage | Document Intelligence Engine | Deleted dead path |
| `runtime/prompts/definitions/` | `ai/capabilities/*/prompt.md` | Removed — use capabilities |
| `runtime/schemas/definitions/` | `ai/capabilities/*/schema.json` | Removed — use capabilities |

## Retained but unused / deprecate

| Path | Justification |
|------|---------------|
| `ai/schemas/` + `ai/contracts/` | Spec overlap with TOON v1 + canonical models; deprecate |
| Root shims `apps/backend/{toon,llm_service,...}.py` | Compat for older tests; prefer `app.*` |
| `ai/toon/v1/types/toon.ts` | TypeScript contracts; Form DTOs are FE autofill contract |

## Active production paths

- `apps/backend/app/ai/document_intelligence/` — Form DTOs, canonical models, explicit mappers
- `apps/backend/app/ai/parser/engine/` — Extraction / deterministic / knowledge stages
- `ai/capabilities/` — Semantic AI capability library
- `ai/runtime/` — AI runtime
- `ai/toon/v1/` — TOON ontology (persistence wire)
- `docs/document_intelligence/` — Engine architecture & acceptance

## Migration reference

See [docs/document_intelligence/](../../../docs/document_intelligence/) and
[capabilities/MIGRATION.md](../capabilities/MIGRATION.md).
