# Data Pipeline — Canonical Reference

**This is the authoritative document for the HRMS AI platform data and model pipeline.** All other docs reference this flow. If a procedure conflicts with this document, this document wins.

---

## End-to-end pipeline

```
Resume / Job Description (raw file)
        │
        ▼
┌───────────────────┐
│  TEXT EXTRACTION  │  dataset/extraction/  →  dataset/lake/extracted/
└─────────┬─────────┘
          ▼
┌───────────────────┐
│     CLEANING      │  dataset/factory/ (clean stage — planned)    →  dataset/lake/cleaned/
└─────────┬─────────┘
          ▼
┌───────────────────┐
│   NORMALIZATION   │  dataset/factory/normalizer/ →  dataset/lake/normalized/
└─────────┬─────────┘
          ▼
┌───────────────────┐
│    VALIDATION     │  dataset/factory/validator/ →  gate (≥95% pass)
└─────────┬─────────┘
          ▼
┌───────────────────┐
│      JSONL        │  dataset/factory/exporter/    →  dataset/lake/jsonl/{version}/
└─────────┬─────────┘
          │
          ├──────────────────────────────────────┐
          ▼                                      ▼
┌───────────────────┐                 ┌───────────────────┐
│ TRAINING DATASET  │                 │    BENCHMARK      │
│  (train/val/test) │                 │  (frozen, never   │
│                   │                 │   used for train) │
└─────────┬─────────┘                 └─────────┬─────────┘
          ▼                                      │
┌───────────────────┐                            │
│      QLoRA        │  training/runs/            │
└─────────┬─────────┘                            │
          ▼                                      │
┌───────────────────┐                            │
│  MERGED MODEL     │  models/merged/            │
└─────────┬─────────┘                            │
          ▼                                      │
┌───────────────────┐                            │
│      GGUF         │  models/gguf/              │
└─────────┬─────────┘                            │
          ▼                                      │
┌───────────────────┐                            │
│     OLLAMA        │  exports/modelfiles/       │
└─────────┬─────────┘                            │
          ▼                                      ▼
┌───────────────────┐                 ┌───────────────────┐
│   EVALUATION      │◀────────────────│  REGRESSION GATES │
│  (all providers)  │                 │  evaluation/      │
└─────────┬─────────┘                 │  regression/      │
          ▼                           └───────────────────┘
┌───────────────────┐
│   PRODUCTION      │  registry/models/ status → production
│  (HRMS integrate) │  future: backend provider adapter
└───────────────────┘
```

---

## Stage reference

### Stage 0: Raw ingestion

| Attribute | Value |
|-----------|-------|
| **Directory** | `dataset/lake/raw/resumes/`, `dataset/lake/raw/job_descriptions/` |
| **Input** | PDF, DOC, DOCX files |
| **Output** | Same files, immutable |
| **Module** | Manual copy or HRMS export script (future) |
| **Registry** | `registry/datasets/` provenance field |

**Rules:** Never modify raw files in place. Deduplicate by SHA-256 hash before extraction.

---

### Stage 1: Text extraction

| Attribute | Value |
|-----------|-------|
| **Module** | `dataset/extraction/` |
| **Input** | `dataset/lake/raw/` |
| **Output** | `dataset/lake/extracted/{doc_type}/{id}.json` |
| **Key fields** | `raw_text`, `source_hash`, `extraction.method` |

Extractors: PyPDF, pdfplumber, python-docx. Production HRMS upload parsing uses PyMuPDF first, then optional pdfplumber fallback — see `apps/backend/app/ai/parser/text_extraction.py` and [DOCUMENT_INTELLIGENCE.md](DOCUMENT_INTELLIGENCE.md#pdf-text-extraction).

---

### Stage 2: Cleaning

| Attribute | Value |
|-----------|-------|
| **Module** | `dataset/factory/ (clean stage — planned)` |
| **Input** | `dataset/lake/extracted/` |
| **Output** | `dataset/lake/cleaned/{doc_type}/{id}.json` |
| **Key fields** | `text` (cleaned), `cleaning.rules_applied` |

No semantic structuring at this stage — text only.

---

### Stage 3: Normalization

| Attribute | Value |
|-----------|-------|
| **Module** | `dataset/factory/normalizer/` |
| **Input** | `dataset/lake/cleaned/` |
| **Output** | `dataset/lake/normalized/{doc_type}/{id}.json` |
| **Key fields** | `toon` (structured dict), `labeling.source` |

Produces TOON-compatible records. Label sources: human, grok, openai, synthetic.

---

### Stage 4: Validation

| Attribute | Value |
|-----------|-------|
| **Module** | `dataset/factory/validator/` |
| **Input** | `dataset/lake/normalized/` |
| **Output** | Pass → split; Fail → quarantine |
| **Gate** | ≥ 95% pass rate |

Validates TOON schema, cross-field consistency, duplicate hashes.

---

### Stage 5: JSONL splits

| Attribute | Value |
|-----------|-------|
| **Module** | `dataset/factory/exporter/` |
| **Input** | Validated `dataset/lake/normalized/` |
| **Output** | `dataset/lake/jsonl/{version}/train.jsonl`, `val.jsonl`, `test.jsonl` |
| **Registry** | `registry/datasets/{version}.yaml` |

Split: 80/10/10 stratified by `doc_type`. No hash leakage across splits.

---

### Stage 6: Benchmark (parallel track)

| Attribute | Value |
|-----------|-------|
| **Directory** | `dataset/lake/benchmark/parsing/v{N}/` |
| **Input** | Curated gold labels (never from train split) |
| **Registry** | `registry/benchmarks/parsing-v{N}.yaml` |
| **Rule** | **Frozen** — new version = new directory |

---

### Stage 7: QLoRA training

| Attribute | Value |
|-----------|-------|
| **Directory** | `training/runs/{run_id}/` |
| **Config snapshot** | `training/configs/{run_id}.yaml` |
| **Input** | `dataset/lake/jsonl/{version}/train.jsonl` |
| **Output** | `training/runs/{run_id}/adapter/` → `models/adapters/` |

---

### Stage 8: Merge

| Attribute | Value |
|-----------|-------|
| **Input** | `models/base/` + `models/adapters/{run_id}/` |
| **Output** | `models/merged/{model_id}/` |

---

### Stage 9: GGUF export

| Attribute | Value |
|-----------|-------|
| **Input** | `models/merged/{model_id}/` |
| **Output** | `models/gguf/{model_id}-{quant}.gguf` |
| **Quantization** | `q4_K_M` (production default) |

---

### Stage 10: Ollama deployment

| Attribute | Value |
|-----------|-------|
| **Modelfile** | `exports/modelfiles/{model_id}.Modelfile` |
| **Registry** | `registry/models/{model_id}.yaml` → `deployment.ollama_*` |

---

### Stage 11: Evaluation

| Attribute | Value |
|-----------|-------|
| **Directory** | `evaluation/reports/{eval_id}/` |
| **Benchmark** | `dataset/lake/benchmark/parsing/v{N}/` |
| **Providers** | Grok, Ollama, OpenAI, Claude, fine-tuned |
| **Comparisons** | `evaluation/comparisons/` |
| **Regression** | `evaluation/regression/baseline.yaml` |

---

### Stage 12: Production

| Attribute | Value |
|-----------|-------|
| **Registry status** | `production` in `registry/models/` |
| **HRMS** | Future provider adapter (M5+) — no changes in this milestone |

---

## TOON schema contract

All normalized and model outputs must conform to HRMS TOON rules.

### Resume (`type: resume`)

| Field | Required | Notes |
|-------|----------|-------|
| `person.name` | Yes | |
| `person.email` | Yes | |
| `person.phone` | No | |
| `person.location` | No | |
| `person.linkedin`, `github`, etc. | No | Empty string if absent |
| `skills` | Yes | Array or pipe-separated |
| `experience` | Yes | Array of objects |
| `education` | No | |
| `summary` | No | |
| `total_experience_years` | No | |

### Job description (`type: job_description`)

| Field | Required | Notes |
|-------|----------|-------|
| `title` | Yes | |
| `company` | Yes | |
| `location` | No | |
| `skills` | Yes | |
| `qualifications` | No | |
| `responsibilities` | No | |
| `min_experience_years` | No | |

**HRMS reference:** `backend/toon.py`, `backend/parsing_utils.py` `validate_toon_format()`.

---

## Synthetic data

`dataset/lake/synthetic/` holds LLM-generated or rule-based augmentations for edge cases (sparse resumes, non-English, multi-column layouts). Synthetic records flow through the same pipeline stages and are tagged `labeling.source: synthetic` in normalization.

---

## Feature expansion map

| HRMS AI feature | Pipeline entry | Benchmark | Model registry prefix |
|-----------------|----------------|-----------|----------------------|
| Resume parsing | `raw/resumes/` | `benchmark/parsing/` | `hrms-parsing-*` |
| JD parsing | `raw/job_descriptions/` | `benchmark/parsing/` | `hrms-parsing-*` |
| Bulk parsing | Same as resume | Same | Same |
| Resume matching | `normalized/` pairs | `benchmark/matching/` (future) | `hrms-matching-*` |
| Candidate ranking | embeddings (future) | `benchmark/ranking/` (future) | `hrms-ranking-*` |
| Summarization | `cleaned/` or `normalized/` | `benchmark/summarization/` (future) | `hrms-summary-*` |
| Interview questions | `normalized/` | `benchmark/interview/` (future) | `hrms-interview-*` |
| Skill extraction | `normalized/` skills | `benchmark/skills/` (future) | `hrms-skills-*` |
| Skill normalization | ontology mappings (future) | `benchmark/skills/` (future) | `hrms-skills-norm-*` |
| Salary intelligence | external data (future) | `benchmark/salary/` (future) | `hrms-salary-*` |
| AI chat assistant | RAG corpus (future) | `benchmark/chat/` (future) | `hrms-chat-*` |

---

## Manifest files

Every batch operation writes a `manifest.yaml`:

```yaml
stage: normalized
version: parsing-v1
created_at: "2026-06-25T12:00:00Z"
input_manifest: dataset/lake/cleaned/manifest.yaml
record_count: 1000
pass_count: 972
fail_count: 28
checksum: sha256:...
git_commit: abc1234
pipeline_version: "1.1.0"
```

Manifests enable reproducibility — see [REPRODUCIBILITY.md](REPRODUCIBILITY.md).

---

## Related documents

| Document | Scope |
|----------|-------|
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) | Versioning, lineage, six-month replay |
| [CONVENTIONS.md](CONVENTIONS.md) | Naming and folder standards |
| [MODEL_LIFECYCLE.md](MODEL_LIFECYCLE.md) | Model status and promotion |
| [HRMS_DEPENDENCY_MAP.md](HRMS_DEPENDENCY_MAP.md) | Current production AI touchpoints |
