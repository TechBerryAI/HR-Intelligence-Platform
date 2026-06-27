# TOON v1 Changelog

## 1.0.0 — 2026-06-27

### Added

- Canonical TOON ontology package under `ai/toon/v1/`
- Document mappings: `resume`, `job_description`, `candidate`
- Wire-format datatypes, validation rules, normalization transforms
- Field dictionary and ontology definitions
- Wire-format examples for resume and job description

### Migrated

- Projection mappings consolidated from `ai/schemas/mappings/toon.yaml` (removed)
- Flat v1 files reorganized into ontology/, dictionary/, vocabulary/, validation/, normalization/

### Unchanged

- Runtime behavior: `backend/toon.py`, `backend/parsing_utils.py`
- TOON semantics and wire format rules
- TypeScript types in `ai/toon/v1/types/toon.ts`
