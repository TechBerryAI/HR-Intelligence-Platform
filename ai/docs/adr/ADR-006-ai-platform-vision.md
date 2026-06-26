# ADR-006: AI Platform Vision

## Status

Accepted (M1.5 Architecture Review)

## Context

Early milestones risk framing the workspace as "Ollama + QLoRA for resume parsing." The HRMS roadmap includes matching, ranking, search, summarization, interview generation, chat, and salary intelligence. Architecture must reflect a **platform**, not a one-off ML project.

## Problem

Training-centric architecture leads to:
- Provider logic embedded in training scripts
- No home for inference routing, monitoring, or orchestration
- Each new feature reimplements provider calls, eval, and deployment
- HRMS integration tightly couples to one model format

## Decision

Adopt **AI Platform** paradigm with five platform subsystems:

1. **Data Platform** — contracts, staged lake, artifacts (`datasets/`, `preprocessing/`, `docs/DATA_CONTRACTS.md`)
2. **Training Platform** — experiments, QLoRA, model registry (`training/`, `models/`, `experiments/`)
3. **Inference Platform** — LLM Gateway, provider management (`platform/inference/`, `platform/providers/`)
4. **Evaluation Platform** — benchmarks, regression, comparisons (`evaluation/`, `registry/evaluations/`)
5. **Governance Platform** — registry, versioning, ADRs, engineering standards (`registry/`, `governance/`, `docs/`)

**LLM Gateway (M8)** sits between HRMS and providers — not direct Ollama calls from business logic.

**Feature services (M10)** expose parsing, matching, chat as discrete capabilities built on inference platform.

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Ollama-only architecture | Vendor lock-in; no Grok fallback |
| Embed AI in Flask immediately | Violates isolation; premature |
| Buy managed ML platform | Cost; less control over TOON contract |
| Microservices per feature now | Over-engineering before M6 eval proves patterns |

## Consequences

**Positive:**
- Each new HRMS AI feature follows same path: contract → data → benchmark → train → eval → deploy → service
- Platform team can evolve inference without retraining
- Clear M8–M11 milestones

**Negative:**
- `platform/` directories empty until M8 — requires discipline not to shortcut
- More documentation upfront

## Future work

- M8: Implement LLM Gateway in `platform/`
- M9: HRMS adapter calls gateway, not providers
- M10: Feature services for matching, summary, chat
- M11: Monitoring and continuous improvement loop

Full vision: [PLATFORM_VISION.md](../PLATFORM_VISION.md)
