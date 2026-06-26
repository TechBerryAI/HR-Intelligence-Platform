# Interview Question Generation

**Capability ID:** `interview_generation`  
**Version:** 1.0.0  
**Status:** active

## Overview

Generate role-appropriate interview questions from resume and job description context.

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

This capability is auto-discovered from `ai/capabilities/interview_generation/`. No runtime code changes are required.

## Adding a New Version

1. Bump `version` in `capability.yaml`
2. Update `prompt.md` or add `prompt.v2.md` and reference it
3. Evolve `schema.json` with backward-compatible changes when possible
4. Update `validation.yaml` and `benchmarks/` accordingly
