# ADR-002: Dataset Pipeline

## Status

Accepted (M1.5 Architecture Review)

## Context

Resume and JD data flows through multiple transformations before training. Milestone 1.5 introduced staged directories (`raw/` → `jsonl/`). We must confirm this supports all future features and artifact lineage.

## Problem

A single `processed/` folder:
- Cannot re-run individual stages
- Loses intermediate artifacts for debugging
- Blocks features that enter at different stages (summarization from `cleaned/`, not `normalized/`)
- Makes lineage tracing impossible

## Decision

**Seven-stage data lake** with one directory per transformation:

```
raw → extracted → cleaned → normalized → jsonl
                    ↓              ↓
               synthetic      benchmark (frozen branch)
```

**Five preprocessing modules** map 1:1 to stages: `extract/`, `clean/`, `normalize/`, `validate/`, `split/`.

Each stage produces **versioned artifacts** with manifests (see ADR-004).

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Single `processed/` JSONL | No intermediate replay |
| Database instead of files | Overkill for M2–M4; files portable to cloud |
| Skip `cleaned/` stage | Summarization and search need clean text without TOON |
| Merge `normalized/` and `jsonl/` | Different consumers (validation vs training format) |

## Consequences

**Positive:**
- Idempotent stage re-runs
- Feature-specific entry points
- Benchmark branch isolated from training data
- Aligns with artifact lineage model

**Negative:**
- More disk usage (mitigated by retention policy in AI_ENGINEERING.md)
- Manifest chain must be maintained

## Future work

- M3: Implement stage scripts with manifest generation
- M4: Validation gates block bad data before JSONL
- Artifact sidecar files (`.artifact.yaml`) per record
