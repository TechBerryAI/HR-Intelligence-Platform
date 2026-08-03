# Document Intelligence Engine — Removal & Replacement Plan

**Status:** Active migration  
**Date:** 2026-08-03  
**Owner:** HCIP Architecture

## Problem

Resume/JD parsing was architecturally inconsistent: multiple schemas (`ai/toon`, `ai/schemas`, `ai/contracts`, capability JSON), frontend heuristic TOON→form mapping, dual prompts, dead shims, and unused façades. Autofill was non-deterministic.

## Target

One subsystem: **Document Intelligence Engine** (`app.ai.document_intelligence`).

```
Document → Extraction → Layout → Sections → Resume/JD Parser
  → Knowledge → Validation → Canonical Model → Form Mapper → Form DTO → Frontend
```

Frontend receives **only Form DTOs**. TOON remains the persistence/ATS wire format (serialization of canonical models), never consumed by React for autofill.

## Removal plan

| Artifact | Action | Rationale |
|----------|--------|-----------|
| FE `mapResumeTOONToForm` / `mapJDTOONToForm` heuristics | **Delete** | Mapping moves to backend Form Mapper |
| `resume_inference.py` deprecated wrapper | **Delete** | Tests migrate to `repair_resume_toon` |
| `call_parsing_api` in `parsing_storage.py` | **Delete** | Dead; never called by engine |
| Root shims `apps/backend/{resume_inference,parsing_utils}.py` | **Delete** after import audit | Compat only |
| Duplicate schema docs claiming FE maps TOON | **Update** to Form DTO contract |
| `ai/schemas` + `ai/contracts` overlap | **Deprecate** → point to canonical models + TOON v1 | Spec debt; not runtime |
| Unused `parse_*_from_text` façade result | **Wire or remove call** | Orchestrator discards return |
| Inline `get_system_prompt` dual path | Keep gated; prefer capability prompts | Gateway-default |

## Replacement plan (milestones)

1. Canonical models (`CandidateProfile`, `JobProfile`) + `TraceableField`
2. Explicit Form Mapper + Form DTOs
3. Orchestrator attaches `form`; API response for clients omits raw TOON for autofill
4. Frontend consumes `result.form` only
5. Mapping + gold regression tests
6. Delete obsolete code; publish architecture deliverables

## Keep (consolidated under engine façade)

- `parser/engine/*` orchestration stages
- Deterministic extractors (email/phone/URL/dates)
- Layout, sections, knowledge, confidence, hardware
- TOON persistence for ATS
- Capability prompts for semantic AI only
