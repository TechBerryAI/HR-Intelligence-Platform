# ADR-003: Registry Design

## Status

Accepted (M1.5 Architecture Review, extended)

## Context

The platform needs a single source of truth for models, datasets, prompts, providers, evaluations, and deployments. Milestone 1.5 introduced `registry/` with models, datasets, benchmarks, and experiments.

## Problem

Without extended registries:
- Prompt versions are orphaned in `prompts/` with no history
- Provider configs change without audit trail
- Evaluation runs are not linked to promotion decisions
- Deployments (Ollama tags, Modelfiles) drift from model registry

## Decision

**Unified `registry/` with six sub-registries:**

```
registry/
├── schema.yaml
├── models/          # Model versions, artifacts, status
├── dataset/lake/        # Dataset versions, checksums
├── benchmarks/      # Frozen benchmark definitions
├── experiments/     # EXP-* outcomes
├── prompts/         # PROMPT-* version history
├── providers/       # PROV-* capability and config refs
├── evaluations/     # EVAL-* run records
└── deployments/     # DEPLOY-* Ollama/gateway targets
```

All records are **committed YAML**. Binary artifacts referenced by path only.

Each registry record includes `artifact_id` (ADR-004) and `compatible:` cross-references (VERSIONING.md).

## Why each registry matters

| Registry | Why |
|----------|-----|
| **Prompts** | Prompt changes cause silent quality regression; must trace which prompt trained/evaluated each model |
| **Providers** | Multi-provider fallback requires versioned capability matrix (models supported, rate limits) |
| **Evaluations** | Promotion decisions require immutable eval record linked to benchmark version |
| **Deployments** | Ollama tag `latest` is mutable; registry records immutable deployment snapshot |

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Single `registry.json` | Merge conflicts; no per-entity history |
| MLflow only | External dependency; offline reproducibility harder |
| Metadata in WandB | Training-only; misses prompts, deployments |
| Git tags for models | No structured schema; hard to query |

## Consequences

**Positive:**
- Full platform state readable from git
- Cross-registry compatibility matrix
- Audit trail for compliance

**Negative:**
- Manual registry updates until M6 automation
- Schema evolution requires `schema.yaml` updates

## Future work

- `scripts/validate_registry.py` (M3)
- Auto-register on training/eval completion (M6)
- Prompt registry auto-sync from `prompts/` on version bump (M4)
