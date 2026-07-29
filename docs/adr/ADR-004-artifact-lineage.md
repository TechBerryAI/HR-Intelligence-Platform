# ADR-004: Artifact Lineage

## Status

Accepted (M1.5 Architecture Review)

## Context

Reproducibility and audit require tracing any model or evaluation back to source documents. The platform must support "show me everything that produced `hrms-parsing-v1`" queries.

## Problem

Without artifact lineage:
- Cannot explain why a model fails on specific resume types
- Cannot reproduce training after team turnover
- Regulatory/audit requests for data provenance fail
- Duplicate documents enter training undetected

## Decision

Introduce **ML Artifacts** as first-class conceptual objects. Every pipeline stage produces an artifact with:

| Field | Purpose |
|-------|---------|
| `id` | `ART-{TYPE}-{hash8}` |
| `version` | Semantic or incremental |
| `parent_id` / `parent_ids` | Lineage graph |
| `created_at` | Timestamp |
| `metadata` | Stage-specific fields |
| `sha256` | Content checksum |
| `source.dataset_id` | Link to dataset registry |

**Manifest chain:** each batch writes `manifest.yaml` referencing parent manifest.

**Registry integration:** model/dataset registry entries store root artifact IDs per stage.

## Artifact types

`RAW` → `EXTRACT` → `CLEAN` → `NORM` → `JSONL` → `ADAPTER` → `MERGED` → `GGUF` → `EVAL` → `DEPLOY`

Parallel: `BENCH`, `SYNTH`

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| DVC only | Another tool dependency; registry already planned |
| Filename conventions only | No parent linkage |
| DB lineage table | Violates file-based pipeline simplicity for M2–M4 |
| Git commit only | Insufficient granularity per document |

## Consequences

**Positive:**
- Six-month replay checklist becomes mechanical
- Duplicate detection via `source_hash` / `sha256`
- Debugging failed evals traces to source documents

**Negative:**
- Sidecar metadata per artifact (storage overhead — KB per file)
- Implementation deferred to M3–M4

## Future work

- `.artifact.yaml` sidecar convention (M3)
- `scripts/lineage_trace.py` (M4)
- CI checksum verification (M6)

Full spec: [ARTIFACT_LINEAGE.md](../ARTIFACT_LINEAGE.md)
