# Job Description Parsing

**Capability ID:** `jd_parsing`  
**Version:** 1.0.0  
**Status:** active

## Overview

Parse unstructured job descriptions into structured jd_v1 output for ATS matching and search.

## Files

| File | Purpose |
|------|---------|
| `capability.yaml` | Capability metadata and registry index |
| `prompt.md` | Versioned prompt template |
| `schema.json` | JSON Schema for structured output |
| `validation.yaml` | Runtime validation rules |
| `runtime.yaml` | Provider and inference configuration |
| `examples/` | Input/output templates (no production data) |
| `benchmarks/` | Evaluation definitions |
| `tests/` | Capability package tests |

## Registration

This capability is auto-discovered from `ai/capabilities/jd_parsing/`. No runtime code changes are required.

## Adding a New Version

1. Bump `version` in `capability.yaml`
2. Update `prompt.md` or add `prompt.v2.md` and reference it
3. Evolve `schema.json` with backward-compatible changes when possible
4. Update `validation.yaml` and `benchmarks/` accordingly
