# AI Platform Roadmap

## Vision

Build an **enterprise AI platform** that powers every HRMS recruitment intelligence feature for five+ years — not a one-time Ollama integration.

---

## Milestone overview

| Milestone | Name | Status |
|-----------|------|--------|
| M1 | AI Workspace Foundation | ✅ Complete |
| M1.5 | Architecture Review | ✅ Complete |
| M2 | Data Contracts | Next |
| M3 | Dataset Engineering | Planned |
| M4 | Data Preprocessing Pipeline | Planned |
| M5 | QLoRA Training | Planned |
| M6 | Evaluation & Benchmarking | Planned |
| M7 | Ollama Deployment | Planned |
| M8 | LLM Gateway | Planned |
| M9 | HRMS Integration | Planned |
| M10 | Advanced HR AI Platform | Planned |
| M11 | Monitoring & Continuous Improvement | Planned |

---

## M1 — AI Workspace Foundation ✅

- Initial `ai/` folder, configs, prompts, HRMS dependency map

---

## M1.5 — Architecture Review ✅

- Multi-stage data lake, modular preprocessing, extended registry design
- Artifact lineage, versioning strategy, data contracts (conceptual)
- Platform layers (`platform/`), governance, ADRs, benchmark strategy
- [AI_ENGINEERING.md](AI_ENGINEERING.md), [PLATFORM_VISION.md](PLATFORM_VISION.md)

**HRMS changes:** None

---

## M2 — Data Contracts

**Goal:** Formalize domain schemas before any preprocessing code.

**Deliverables:**
- Finalize [DATA_CONTRACTS.md](DATA_CONTRACTS.md)
- JSON Schema files in `governance/schemas/` (optional start)
- Contract → TOON projection mapping document
- Review with HRMS team against `validate_toon_format()`

**Why before data engineering:** Preprocessing without contracts produces inconsistent labels. Contracts are cheap to change; labeled datasets are expensive to fix.

**HRMS changes:** None

---

## M3 — Dataset Engineering

**Goal:** Build first versioned datasets with artifact lineage.

**Deliverables:**
- HRMS read-only export script design
- `datasets/raw/` populated (or export plan)
- `registry/datasets/DS-PARSE-v1.0.0.yaml`
- Manifest and artifact ID conventions implemented
- `datasets/benchmark/parsing/v1/` design finalized

**Why before preprocessing:** Know target record counts, sources, and labeling strategy before writing pipelines.

**HRMS changes:** None

---

## M4 — Data Preprocessing Pipeline

**Goal:** Implement extract → clean → normalize → validate → split.

**Deliverables:**
- Stage scripts with manifest chain
- Validation gates (≥95% pass)
- `datasets/jsonl/parsing-v1/` produced
- `registry/benchmarks/BENCH-PARSE-v1.yaml` frozen

**Why before training:** Garbage in = garbage out. No GPU time until data is validated.

**HRMS changes:** None

---

## M5 — QLoRA Training

**Goal:** First fine-tuned parsing model with full lineage.

**Deliverables:**
- `EXP-0001` experiment completed
- `training/configs/` snapshot, `training/runs/` artifacts
- `registry/models/hrms-parsing-v1.yaml`
- `models/adapters/`, `models/merged/`

**Why after data pipeline:** Training on unvalidated data wastes GPU and creates untraceable models.

**HRMS changes:** None

---

## M6 — Evaluation & Benchmarking

**Goal:** Prove model quality against frozen benchmark; establish Grok baseline.

**Deliverables:**
- `EVAL-PARSE-*` runs for Grok, Ollama (merged), OpenAI, Claude
- `registry/evaluations/` records
- `evaluation/regression/baseline.yaml`
- `evaluation/comparisons/` analysis
- Promotion decision: candidate → staging

**Why before deployment:** Never deploy a model that hasn't passed regression gates.

**HRMS changes:** None

---

## M7 — Ollama Deployment

**Goal:** Production-ready local inference artifact.

**Deliverables:**
- `models/gguf/hrparser-v1-*-q4_k_m.gguf`
- `exports/modelfiles/hrms-parsing-v1.Modelfile`
- `registry/deployments/DEPLOY-parsing-v1-ollama.yaml`
- Health checks documented in [AI_ENGINEERING.md](AI_ENGINEERING.md)

**Why after eval:** Deployment is cheap; rollback of bad deployment is expensive.

**HRMS changes:** None

---

## M8 — LLM Gateway

**Goal:** Provider abstraction and inference routing inside `ai/platform/`.

**Deliverables:**
- `platform/inference/` — routing, caching, fallback
- `platform/providers/` — Ollama, Grok, OpenAI, Claude, Gemini
- `registry/providers/` populated
- Gateway tested against BENCH-PARSE without HRMS

**Why before HRMS integration:** Prove gateway in isolation; HRMS gets a stable interface.

**HRMS changes:** None

---

## M9 — HRMS Integration

**Goal:** Non-breaking production integration.

**Deliverables:**
- Refactor `backend/llm_service.py` internals to call gateway
- Feature flag `AI_USE_GATEWAY=true`
- `exports/integration/` config bundle
- `model_version` tracks deployment registry ID

**Why after gateway:** Single integration point reduces HRMS change surface.

**HRMS changes:** `llm_service.py` internals only

---

## M10 — Advanced HR AI Platform

**Goal:** Second feature on platform (matching, summarization, or chat).

**Deliverables:**
- New data contract + benchmark category (BENCH-MATCH or BENCH-SUMMARY)
- `platform/services/` first additional service
- Demonstrate platform patterns replicate without new architecture

**HRMS changes:** New feature endpoints or background jobs (scoped separately)

---

## M11 — Monitoring & Continuous Improvement

**Goal:** Closed-loop quality, cost, and drift monitoring.

**Deliverables:**
- `platform/monitoring/` — latency, cost, quality drift
- Scheduled benchmark regression
- Human correction export → training data pipeline
- Model promotion workflow automation

**HRMS changes:** Observability hooks only

---

## Why this ordering minimizes technical debt

| Order principle | Rationale |
|-----------------|-----------|
| Contracts before data | Fix schema cheaply |
| Data before preprocessing | Know sources and volume |
| Preprocessing before training | Validated inputs only |
| Training before eval | Something to measure |
| Eval before deploy | No ungated production |
| Gateway before HRMS | Stable integration boundary |
| One feature before many | Prove patterns once |
| Monitoring last | Monitor what exists |

---

## Platform maturity model

| Level | Milestone | Characteristics |
|-------|-----------|-----------------|
| L1 | M1–M1.5 | Architecture, ADRs, contracts |
| L2 | M2–M4 | Data pipeline operational |
| L3 | M5–M6 | Model trained and measured |
| L4 | M7 | Deployable artifact |
| L5 | M8 | Inference platform |
| L6 | M9 | HRMS integrated |
| L7 | M10–M11 | Multi-feature, monitored |

---

## Related documents

- [PLATFORM_VISION.md](PLATFORM_VISION.md)
- [adr/README.md](adr/README.md)
- [DATA_PIPELINE.md](DATA_PIPELINE.md)
