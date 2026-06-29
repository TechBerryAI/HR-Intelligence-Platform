# AI Platform

**Document ID:** ARCH-04  
**Status:** Constitutional — all AI engineering derives from this specification  
**Related:** [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) · [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md) · [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md)

---

## Purpose

This document defines the **AI Platform** architecture — the governed intelligence infrastructure that powers all capabilities in the Human Capital Intelligence Platform. The AI platform lives in `ai/` and operates independently of the HRMS backend until integrated via adapter (M9).

---

## Platform Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AI PLATFORM (ai/)                              │
├──────────────┬──────────────┬──────────────┬──────────────┬───────────┤
│    Data      │   Training   │  Inference   │  Evaluation  │ Governance│
│   Platform   │   Platform   │   Platform   │   Platform   │ Platform  │
├──────────────┼──────────────┼──────────────┼──────────────┼───────────┤
│ dataset/     │ training/    │ runtime/     │ evaluation/  │ registry/ │
│ contracts/   │ models/      │ providers/   │ benchmarks/  │ adr/      │
│ schemas/     │ experiments/ │ capabilities/│ regression/  │ configs/  │
│ knowledge/   │              │              │ comparisons/ │           │
│ toon/        │              │              │              │           │
└──────────────┴──────────────┴──────────────┴──────────────┴───────────┘
                                    │
                          M9 adapter│
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     HRMS Backend (backend/)                              │
│   llm_service.py → runtime adapter → capabilities → TOON → persistence│
└─────────────────────────────────────────────────────────────────────────┘
```

---

## AI Runtime

### Purpose

The AI Runtime (`ai/runtime/`) is the execution engine for all AI capabilities. It loads capability definitions, routes requests to providers, validates outputs, and records inference lineage.

### Components

| Component | Path | Responsibility |
|-----------|------|---------------|
| **CLI** | `runtime/cli/main.py` | Command-line capability execution for development and testing |
| **Task Engine** | `runtime/` core | Orchestrates capability loading, provider routing, validation |
| **Provider Manager** | `providers/manager.py` | Selects provider, handles retry, fallback, rate limiting |
| **Capability Loader** | `runtime/` | Reads `capability.yaml`, `prompt.md`, `schema.json`, `validation.yaml` |
| **Output Validator** | `runtime/` | Validates LLM output against schema and validation rules |

### Execution flow

```
Request → Capability Loader → Prompt Assembly → Provider Manager → LLM Inference
                                                                      │
                                                          Output Validator ←┘
                                                                │
                                                    Valid → Return result
                                                    Invalid → Retry / Fallback
```

### Runtime configuration

Default configuration in `ai/configs/`:

| Setting | Default | Purpose |
|---------|---------|---------|
| Primary provider | Ollama | Local inference |
| Fallback provider | mock (dev) / Grok (prod) | Failure recovery |
| Timeout | 60s | Per-inference limit |
| Max retries | 2 | Provider retry before fallback |
| Capabilities directory | `ai/capabilities/` | Capability discovery path |

### Integration boundary (M9)

```
backend/llm_service.py
    │
    ├── [AI_USE_GATEWAY=false] → Direct provider calls (current production)
    │
    └── [AI_USE_GATEWAY=true]  → ai/runtime/ adapter
                                      │
                                      ├── Provider Manager
                                      ├── Capability execution
                                      └── TOON output returned to backend
```

**Rule:** HRMS route handlers do not change. Only `llm_service.py` internals adapt.

---

## Providers

### Purpose

Providers (`ai/providers/`) abstract LLM backends behind a common interface. Business logic and capabilities never call providers directly — they go through the Provider Manager.

### Provider interface

```python
class BaseProvider:
    def complete(prompt, schema, options) → ProviderResponse
    def health_check() → bool
    def capabilities() → ProviderCapabilities
```

### Registered providers

| Provider | Path | Status | Use case |
|----------|------|--------|----------|
| **Ollama** | `providers/ollama/` | Active (runtime) | Primary local inference; fine-tuned models |
| **Mock** | `providers/mock/` | Active (tests) | Deterministic test responses |
| **Grok (X.AI)** | `backend/llm_service.py` | Active (production HRMS) | Production parsing and ATS |
| **OpenAI** | `backend/llm_service.py` | Active (production HRMS) | Alternative production provider |
| **Anthropic** | `backend/llm_service.py` | Active (production HRMS) | Alternative production provider |

### Provider selection strategy

```
1. Check capability runtime.yaml for provider preference
2. Attempt primary provider (Ollama in platform; Grok in production HRMS)
3. On failure: retry (max 2) with exponential backoff
4. On exhaustion: fallback to secondary provider
5. Log provider selection, latency, and token usage
6. Record in inference lineage
```

### Multi-key rotation (production)

Production HRMS supports multiple API keys (`HRMS_API_KEY_1..4`) via `backend/llm_key_manager.py` for rate limit distribution and failover.

### Future providers

Gemini, Azure OpenAI, AWS Bedrock — registered in `ai/registry/providers/` when needed. Provider addition requires: implementation, registry entry, benchmark validation, no capability changes.

---

## Capabilities

See [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) for the complete capability registry.

### Capability contract

Every capability package defines:

| File | Purpose |
|------|---------|
| `capability.yaml` | ID, version, description, input/output types, dependencies |
| `prompt.md` | System prompt (immutable at runtime) and user prompt template |
| `schema.json` | JSON Schema for structured output validation |
| `validation.yaml` | Business rules beyond schema (field ranges, required combinations) |
| `runtime.yaml` | Provider preference, timeout, retry policy, output mode |
| `examples/` | Golden input/output pairs for testing |
| `benchmarks/` | Capability-specific evaluation data |
| `tests/` | Automated tests |

### Authority chain

```
ai/contracts/ → ai/schemas/ → ai/knowledge/ → ai/toon/v1/ → backend/toon.py
ai/capabilities/ → ai/runtime/
ai/providers/ → ai/runtime/
```

No layer duplicates definitions from a lower layer.

---

## Evaluation

### Purpose

Evaluation (`ai/evaluation/`, `ai/registry/evaluations/`) proves capability quality before deployment. No model or prompt reaches production without passing benchmark regression.

### Evaluation pipeline

```
Benchmark (frozen) → Capability + Model → Inference → Metrics → Pass/Fail Gate
                                                                          │
                                                              Pass → Deploy
                                                              Fail → Block
```

### Benchmark registry

| Benchmark ID | Capability | Metrics | Pass criteria |
|-------------|-----------|---------|---------------|
| `BENCH-PARSE-v1` | resume_parsing, jd_parsing | Field-level F1, completeness | F1 ≥ 0.95 |
| `BENCH-MATCH-v1` | candidate_matching | Precision@shortlist, score correlation | Planned |
| `BENCH-SUMMARY-v1` | resume_summary | ROUGE, human eval score | Planned |
| `BENCH-GEN-v1` | interview_generation, hr_chat | Relevance, safety | Planned |

### Evaluation types

| Type | Purpose | Frequency |
|------|---------|-----------|
| **Regression** | Compare new model/prompt against baseline | Every deployment |
| **Comparison** | Compare providers (Grok vs Ollama vs OpenAI) | Ad-hoc / quarterly |
| **Drift detection** | Monitor production quality over time | Continuous (M11) |
| **Safety eval** | Prompt injection, PII leakage, bias | Every capability release |

### Evaluation records

Each run produces a registry entry:

```yaml
id: EVAL-PARSE-001
benchmark: BENCH-PARSE-v1
capability: resume_parsing
model: hrms-parsing-v1
provider: ollama
metrics:
  field_f1: 0.96
  completeness: 0.98
result: PASS
timestamp: 2026-06-27T00:00:00Z
```

---

## Training

### Purpose

Training (`ai/training/`, `ai/models/`) produces fine-tuned models from validated datasets. Training follows the dataset pipeline — never operates on unvalidated data.

### Training pipeline

```
Validated JSONL → Training Config Snapshot → QLoRA Fine-tune → Merge → Quantize (GGUF) → Evaluate → Deploy
```

### Training artifacts

| Artifact | Path | Purpose |
|----------|------|---------|
| Config snapshot | `training/configs/{run_id}.yaml` | Immutable hyperparameters per run |
| Run artifacts | `training/runs/{run_id}/` | Checkpoints, logs, metrics |
| Adapters | `models/adapters/` | LoRA adapter weights |
| Merged models | `models/merged/` | Full merged weights |
| GGUF exports | `models/gguf/` | Quantized deployment artifacts |
| Modelfiles | `exports/modelfiles/` | Ollama deployment configuration |

### Model naming

Pattern: `hrms-{feature}-v{N}`

| Model | Feature | Status |
|-------|---------|--------|
| `hrms-parsing-v1` | Resume + JD parsing | Planned (M5) |
| `hrms-matching-v1` | Candidate matching | Future |
| `hrms-summary-v1` | Resume summarization | Future |

### Reproducibility

Every training run records: config snapshot, dataset ID + checksum, base model, random seed, hardware, duration. See `ai/docs/REPRODUCIBILITY.md`.

---

## Dataset Pipeline

### Purpose

The dataset pipeline (`ai/dataset/`) transforms raw documents into validated training and evaluation data with full artifact lineage.

### Medallion architecture

```
raw/ → extracted/ → cleaned/ → normalized/ → jsonl/
 │         │            │            │            │
 │         │            │            │            └── Training/evaluation input
 │         │            │            └── Entity-linked, knowledge-normalized
 │         │            └── Deduplicated, format-validated
 │         └── Text extracted from PDF/DOC/DOCX/RTF/TXT
 └── Original documents (immutable)
```

### Pipeline stages

| Stage | Module | Input | Output | Gate |
|-------|--------|-------|--------|------|
| **Extract** | `dataset/extraction/` | Raw files | Plain text | Text non-empty |
| **Clean** | `dataset/factory/clean/` | Extracted text | Cleaned text | No corruption |
| **Normalize** | `dataset/factory/normalize/` | Cleaned text | Normalized entities | Knowledge pack linked |
| **Validate** | `dataset/factory/validate/` | Normalized data | Validated records | Schema compliance |
| **Split** | `dataset/factory/split/` | Validated records | Train/val/test JSONL | ≥95% pass rate |

### Artifact lineage

Every dataset artifact carries:

```yaml
id: DS-PARSE-v1.0.0
source: hrms-export-2026-06
stages:
  - raw: checksum abc123
  - extracted: checksum def456
  - jsonl: checksum ghi789
record_count: 10000
created: 2026-06-27T00:00:00Z
```

Full lineage specification: `ai/docs/ARTIFACT_LINEAGE.md`.

---

## Proposal Generation

### Purpose

Proposal generation (`ai/dataset/proposals/`) uses LLM inference to create structured label proposals from silver-stage documents. Human reviewers approve or correct proposals before they enter the training pipeline.

### Flow

```
Silver document → LLM proposal → Structured JSON proposal → Human review → Approved label → Gold dataset
```

### Governance

- Proposals are never auto-accepted into training data
- Human corrections are tracked and fed back for model improvement
- Proposal prompts are versioned in `ai/registry/prompts/`

---

## Inference

### Modes

| Mode | Use case | Latency target | Example |
|------|----------|---------------|---------|
| **Synchronous** | Interactive user flows | < 15s | Single resume parse, HR chat |
| **Asynchronous** | Background processing | < 60s | ATS matching, bulk parsing |
| **Batch** | Large-scale processing | Throughput-optimized | Bulk resume parsing (500+/hr) |

### Inference record (lineage)

Every inference produces a traceable record:

| Field | Purpose |
|-------|---------|
| `inference_id` | Unique identifier |
| `capability_id` | Which capability executed |
| `capability_version` | Capability semver |
| `provider` | Which provider served the request |
| `model_id` | Model registry ID |
| `prompt_version` | Prompt registry ID |
| `input_hash` | SHA-256 of input (not raw input — PII safety) |
| `output_valid` | Validation pass/fail |
| `latency_ms` | Execution time |
| `timestamp` | ISO 8601 |

### Caching (future)

Identical inputs (by hash) may return cached results within TTL. Cache invalidation follows model/prompt version changes.

---

## Model Lifecycle

```
                    ┌─────────────────────────────────┐
                    │                                 │
    ┌───────────┐   │   ┌───────────┐   ┌──────────┐ │   ┌────────────┐
    │  Dataset  │───┼──►│  Training │──►│ Evaluate │─┼──►│  Deploy    │
    │  Pipeline │   │   │           │   │          │ │   │            │
    └───────────┘   │   └───────────┘   └──────────┘ │   └────────────┘
          ▲         │         ▲              │         │         │
          │         │         │              │ Fail    │         │
          │         │    ┌────┴────┐         │         │         ▼
          │         │    │Experiment│        │         │   ┌────────────┐
          │         │    └─────────┘         │         │   │ Production │
          │         │                        │         │   │ Inference  │
          │         │                        ▼         │   └────────────┘
          │         │                   ┌─────────┐    │         │
          └─────────┼───────────────────│ Reject  │    │         │
     Human corrections                  └─────────┘    │         │
          ▲                                            │         │
          └────────────────────────────────────────────┘─────────┘
                         Continuous improvement loop (M11)
```

### Lifecycle states

| State | Description | Registry |
|-------|-------------|----------|
| **Experimental** | Research/hypothesis stage | `registry/experiments/` |
| **Candidate** | Trained, evaluated, not yet deployed | `registry/models/` |
| **Staging** | Passed eval, deployed to staging environment | `registry/deployments/` |
| **Production** | Serving live inference | `registry/deployments/` |
| **Deprecated** | Superseded, no new inference | `registry/models/` (marked) |
| **Retired** | Removed from all environments | Archive only |

### Promotion gates

| Transition | Gate |
|-----------|------|
| Experimental → Candidate | Training complete, artifacts committed |
| Candidate → Staging | Benchmark regression PASS |
| Staging → Production | Staging validation PASS + feature flag ready |
| Production → Deprecated | Successor deployed and stable |
| Any → Retired | No active inference for 30 days |

---

## Versioning

### Version hierarchy

```
Platform version (semver)
  └── TOON version (TOON-v1, TOON-v2)
  └── Capability version (per capability.yaml)
      └── Prompt version (PROMPT-NNNN)
      └── Model version (hrms-{feature}-v{N})
          └── Deployment version (DEPLOY-{feature}-v{N}-{target})
```

### Compatibility rules

| Change type | Version bump | Breaking? |
|------------|-------------|-----------|
| New capability | Platform MINOR | No |
| Prompt tuning (same schema) | Prompt PATCH | No |
| Schema field addition | Capability MINOR | No |
| Schema field removal/rename | Capability MAJOR | Yes |
| TOON entity addition | TOON MINOR | No |
| TOON entity removal/rename | TOON MAJOR | Yes |
| Model retrain (same schema) | Model PATCH | No |
| New model architecture | Model MAJOR | Potentially |

Full strategy: `ai/docs/VERSIONING.md`, ADR-005.

---

## Fallback Strategy

### Provider fallback

```
Primary provider fails
  → Retry (max 2, exponential backoff)
    → Still failing?
      → Fallback provider (capability.runtime.yaml)
        → Fallback succeeds? → Log fallback event, return result
        → Fallback fails? → Return structured error (never fabricated data)
```

### Model fallback

```
Fine-tuned model unavailable
  → Fall back to base model for same capability
    → Log degradation event
    → Flag result with degraded=true
```

### Graceful degradation rules

| Scenario | Behavior |
|----------|----------|
| AI runtime unreachable | Return error to user; queue for retry (async flows) |
| Parse validation fails | Retry with fallback provider; if all fail, return partial with confidence=0 |
| Match score unavailable | Application created without score; ATS retried in background |
| Chat unavailable | Display "AI assistant temporarily unavailable" |

**Never:** Return fabricated data, silent failures, or stale cached results after model version change.

---

## Registry

The registry (`ai/registry/`) is the governance layer for all AI artifacts.

| Sub-registry | ID pattern | Contents |
|-------------|-----------|----------|
| `registry/models/` | `hrms-*-vN` | Model metadata, lineage, promotion state |
| `registry/datasets/` | `DS-*-v*` | Dataset versions, checksums, record counts |
| `registry/benchmarks/` | `BENCH-*-vN` | Frozen eval sets, pass criteria |
| `registry/prompts/` | `PROMPT-NNNN` | Prompt version history |
| `registry/providers/` | `PROV-*` | Provider capabilities and config |
| `registry/evaluations/` | `EVAL-*` | Evaluation run records |
| `registry/deployments/` | `DEPLOY-*` | Deployment snapshots |
| `registry/experiments/` | `EXP-NNNN` | Experiment outcomes |

**Dependency rule:** Registry is cross-cutting metadata — referenced by all layers, depends on none. Registry entries are committed YAML; model weights are gitignored.

---

## Cross-References

| Topic | Document |
|-------|----------|
| Capability definitions | [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) |
| TOON ontology | [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md) |
| Domain ownership | [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md) |
| Security (AI safety) | [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md) |
| NFRs (performance, reliability) | [10_NON_FUNCTIONAL_REQUIREMENTS.md](10_NON_FUNCTIONAL_REQUIREMENTS.md) |
| Milestones | [11_PRODUCT_ROADMAP.md](11_PRODUCT_ROADMAP.md) |
| ADRs | `ai/docs/adr/` |
| Platform vision | `ai/docs/PLATFORM_VISION.md` |
