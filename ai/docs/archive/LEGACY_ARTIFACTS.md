# Archive — Legacy Artifacts

Documentation of retired paths and compatibility notes. **Architecture is frozen** — this file records history, not active redirects.

## Purpose

When paths were consolidated during repository modernization, some references remained in git history or external docs. This file explains what was removed and where to look now.

## Retired paths (do not recreate)

| Retired path | Replaced by | Notes |
|--------------|-------------|-------|
| `shared/types/` | `ai/toon/v1/types/toon.ts` | TOON owns TypeScript contracts |
| `ai/dataset/factory/` | `ai/dataset/factory/` | Dataset platform consolidation |
| `ai/dataset/lake/` | `ai/dataset/lake/` | Data lake under dataset owner |
| `ai/dataset/extraction/` | `ai/dataset/extraction/` | Renamed for clarity |
| `ai/dataset/proposals/` | `ai/dataset/proposals/` | Proposal Generator package |
| `ai/runtime/providers/` | `ai/providers/` | Top-level provider system |
| `ai/dataset/` | `ai/dataset/extraction/` + `ai/dataset/factory/` | Never implemented as standalone |
| `ai/runtime/ + ai/providers/` | `ai/runtime/` + `ai/providers/` | Scaffold removed |
| `ai/docs/archive/` | `ai/docs/archive/` | This file |
| `runtime/prompts/definitions/` | `ai/capabilities/*/prompt.md` | Removed — use capabilities |
| `runtime/schemas/definitions/` | `ai/capabilities/*/schema.json` | Removed — use capabilities |
| `ai/toon/v1/` | `ai/toon/v1/` | Redirect file removed |

## Retained but unused code

| Path | Justification |
|------|---------------|
| `backend/models/candidate_auth.py` | SQLAlchemy model for schema parity; routes use raw SQL (see `docs/BACKEND_DOCUMENTATION.md`) |
| `ai/toon/v1/types/toon.ts` | TypeScript contracts; not yet imported by frontend |

## Active production paths (never delete)

- `backend/toon.py` — TOON wire runtime
- `backend/llm_service.py` — HRMS parsing prompts
- `ai/capabilities/` — Capability library
- `ai/runtime/` — AI runtime
- `ai/providers/` — LLM providers
- `ai/toon/v1/` — TOON ontology (canonical)

## Migration reference

See [capabilities/MIGRATION.md](../capabilities/MIGRATION.md) for capability-based runtime migration.
