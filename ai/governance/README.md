# Governance

Cross-cutting policies, standards, and review artifacts for the AI platform.

## Contents

| Document | Location |
|----------|----------|
| Platform vision | [docs/PLATFORM_VISION.md](../docs/PLATFORM_VISION.md) |
| Engineering handbook | [docs/AI_ENGINEERING.md](../docs/AI_ENGINEERING.md) |
| Versioning strategy | [docs/VERSIONING.md](../docs/VERSIONING.md) |
| Data contracts | [docs/DATA_CONTRACTS.md](../docs/DATA_CONTRACTS.md) |
| Artifact lineage | [docs/ARTIFACT_LINEAGE.md](../docs/ARTIFACT_LINEAGE.md) |
| Benchmark strategy | [docs/BENCHMARK_STRATEGY.md](../docs/BENCHMARK_STRATEGY.md) |
| Architecture decisions | [docs/adr/](../docs/adr/) |
| Development conventions | [docs/CONVENTIONS.md](../docs/CONVENTIONS.md) |
| Canonical pipeline | [docs/DATA_PIPELINE.md](../docs/DATA_PIPELINE.md) |
| Reproducibility | [docs/REPRODUCIBILITY.md](../docs/REPRODUCIBILITY.md) |

## Review cadence (recommended)

| Review | Frequency | Trigger |
|--------|-----------|---------|
| ADR review | Per major decision | New platform capability |
| Benchmark freeze | Per version | Before model promotion |
| Registry audit | Monthly | Orphaned artifacts, stale experiments |
| Dependency pin review | Quarterly | `AI_ENGINEERING.md` stack versions |
| Data contract review | Per feature | New HRMS AI feature |

## Promotion authority

| Artifact | Promoter | Gate |
|----------|----------|------|
| Dataset version | ML engineer | Validation ≥ 95% |
| Model to staging | ML lead | Eval passes regression |
| Model to production | Architect + ML lead | HRMS integration test |
| Prompt version | ML engineer | Eval on benchmark |
| Provider config | Platform engineer | Health check pass |
