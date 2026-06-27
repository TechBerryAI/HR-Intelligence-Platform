# Resume Parsing v1

**Capability ID:** `resume_parsing`  
**Schema ID:** `resume_v1`  
**Version:** 1.0.0  
**Status:** active (prompt pending manual authoring)  
**Foundation for:** HRParser-v1

## Overview

Production Resume Parsing capability for the AI Platform. Parses unstructured resume text into the canonical HRMS Resume object defined by `schema.json`. All production assets are complete except the final extraction prompt, which must be authored from `prompt.template.md`.

## Architecture Position

```
Document → resume_parsing → resume_v1 JSON → proposal_mapping → TOON projection → HRMS
```

This capability is the **permanent source of truth** for Resume Parsing inside the AI Platform. It does not modify runtime APIs, provider interfaces, or HRMS.

## Files

| File | Purpose |
|------|---------|
| `capability.yaml` | Capability metadata, registry references, asset index |
| `schema.json` | Production JSON Schema (Draft 2020-12) for `resume_v1` |
| `validation.yaml` | Runtime validation rules (required, regex, dates, enums, confidence, cross-field) |
| `runtime.yaml` | Provider and inference configuration |
| `proposal_mapping.yaml` | Provider-independent output normalization to canonical schema |
| `field_definitions.yaml` | Per-field purpose, examples, normalization, and business meaning |
| `prompt.template.md` | Prompt section template for manual authoring |
| `prompt.md` | Loader stub; replace with authored prompt |
| `examples/` | Input/output templates (no production HR data) |
| `benchmarks/` | Evaluation profile definitions and templates |
| `tests/` | Capability package validation tests |

## Schema Coverage

The `resume_v1` schema represents the canonical HRMS Resume superset:

| Section | Schema Path | TOON Projected |
|---------|-------------|----------------|
| Personal Information | `person` | Yes |
| Experience | `experience[]` | Yes |
| Education | `education[]` | Yes |
| Skills | `skills[]` | Yes |
| Projects | `projects[]` | No (normalized only) |
| Certifications | `certifications[]` | Yes |
| Languages | `languages[]` | Yes |
| Awards | `awards[]` | No |
| Publications | `publications[]` | No |
| Links | `links[]` | No (merged from person URLs) |
| Metadata | `metadata` | No |
| Confidence | `confidence` | No |
| Source Tracking | `source_tracking` | No |
| Validation | `validation` | No |

TOON projection rules: `ai/toon/v1/mappings/resume.yaml`

## Remaining Manual Work

1. Author extraction logic in each section of `prompt.template.md`
2. Copy completed prompt into `prompt.md`
3. Run benchmarks against `datasets/evaluation/resume_parsing`

## Registration

Auto-discovered from `ai/capabilities/resume_parsing/`. Shared by `bulk_resume_parsing` via `resume_v1` schema.

## Running Tests

```bash
cd ai && python -m pytest capabilities/resume_parsing/tests/ -v
```

## Adding a New Version

1. Bump `version` in `capability.yaml`
2. Evolve `schema.json` with backward-compatible changes when possible
3. Update `proposal_mapping.yaml`, `field_definitions.yaml`, `validation.yaml`
4. Add benchmark profile if new edge case category emerges
5. Author new prompt version from `prompt.template.md`
