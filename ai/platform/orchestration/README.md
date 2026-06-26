# Orchestration Layer (Future — M9+)

## Purpose

Coordinate multi-step AI workflows that span services, providers, and fallbacks.

## Example workflows

| Workflow | Steps |
|----------|-------|
| Candidate apply | fetch TOON → match → rank → notify |
| Bulk upload | extract batch → parse parallel → validate → export Excel |
| AI search | embed query → retrieve → rerank → summarize |
| Chat with context | retrieve JD + resume → augment prompt → generate |

## Responsibilities (planned)

- DAG definition (YAML or code)
- Step retries and compensating actions
- Provider fallback per step
- Workflow-level tracing (links to `platform/monitoring/`)
- Idempotency keys for long-running jobs

## Will NOT contain

- Individual model inference (delegates to `platform/inference/`)
- Data preprocessing (delegates to `preprocessing/`)

## Milestone

**M9+** — after LLM Gateway (M8) and initial HRMS integration patterns are proven.
