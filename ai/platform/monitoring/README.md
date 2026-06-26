# Monitoring Layer (Future — M11)

## Purpose

Observability for the AI platform: quality, performance, cost, and drift.

## Planned capabilities

| Capability | Metrics |
|------------|---------|
| **Inference monitoring** | Latency P50/P95, error rate, timeout rate |
| **Quality monitoring** | TOON validity on sample, field coverage drift |
| **Cost monitoring** | Token usage per provider, per feature, per tenant |
| **Model drift** | Benchmark regression on schedule |
| **Provider health** | Availability, rate limit events, cooldown frequency |
| **Alerting** | Slack/email on regression gate failure |

## Data sources

- `evaluation/regression/` — scheduled benchmark runs
- `registry/evaluations/` — historical eval records
- `platform/inference/` — runtime metrics (future)
- HRMS `model_version` field — production model tracking (M9+)

## Will NOT contain

- Training loss curves (WandB + `training/logs/`)
- Raw document content (PII)

## Milestone

**M11 — Monitoring & Continuous Improvement**
