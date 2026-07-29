# ADR-005: Versioning Strategy

## Status

Accepted (M1.5 Architecture Review)

## Context

Multiple engineers will create datasets, models, prompts, benchmarks, and experiments concurrently. Ad hoc naming causes collisions, broken reproducibility, and impossible cross-references in tickets and ADRs.

## Problem

Milestone 1.5 used mixed conventions (`parsing-v1`, `hrms-parsing-v1`, date-prefixed experiments). Without canonical rules:
- Registry entries become ambiguous
- Filenames collide across features
- GGUF files on disk are unidentifiable
- Prompt versions conflict with model versions

## Decision

Adopt **prefixed ID system** with documented rules:

| Entity | ID format | Example |
|--------|-----------|---------|
| Dataset file | `{type}_v{semver}.jsonl` | `resume_v1.0.0.jsonl` |
| Dataset registry | `DS-{FEATURE}-v{semver}` | `DS-PARSE-v1.0.0` |
| Model | `hrms-{feature}-v{N}` | `hrms-parsing-v1` |
| GGUF file | `{short}-v{N}-{base}-{quant}.gguf` | `hrparser-v1-qwen2.5-7b-q4_k_m.gguf` |
| Experiment | `EXP-{NNNN}` | `EXP-0001` |
| Prompt | `PROMPT-{NNNN}` | `PROMPT-0007` |
| Benchmark | `BENCH-{CAT}-v{N}` | `BENCH-PARSE-v1` |
| Evaluation | `EVAL-{CAT}-{YYYYMMDD}` | `EVAL-PARSE-20260625` |
| Deployment | `DEPLOY-{feature}-v{N}-{target}` | `DEPLOY-parsing-v1-ollama` |
| Provider | `PROV-{NAME}` | `PROV-GROK` |
| Artifact | `ART-{TYPE}-{hash8}` | `ART-NORM-a1b2c3d4` |

**Immutability rule:** released versions are never mutated.

**Compatibility matrix:** model registry entries declare compatible dataset, prompt, benchmark, and deployment IDs.

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Date-only IDs | Sortable but collide; hard to reference |
| Semver everywhere | Experiments don't need semver |
| UUID only | Human-opaque in logs and tickets |
| No prefix | Namespace collisions across entity types |

## Consequences

**Positive:**
- Unambiguous ticket/ADR references
- Automated validation possible
- GGUF files self-describing on disk

**Negative:**
- Migration from M1.5 informal names (document mapping in registry)
- Sequential ID allocation needs convention (lowest unallocated N)

## Future work

- `scripts/allocate_id.py` for EXP-/PROMPT- IDs (M3)
- CI check for naming compliance (M6)

Full spec: [VERSIONING.md](../VERSIONING.md)
