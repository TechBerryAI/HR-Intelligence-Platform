# Datasets (Data Lake)

Multi-stage data lake for the HRMS AI platform. Each subdirectory represents **one transformation stage** in the data engineering pipeline. Data flows forward only — never skip stages without documenting why.

> **Path:** `ai/dataset/lake/` — referred to as "the data lake" or "lake" in documentation.

## Pipeline stages

```
raw/  →  extracted/  →  cleaned/  →  normalized/  →  jsonl/
                                                          ↓
                                                    benchmark/  (frozen eval set)
                                                    synthetic/  (generated augmentations)
```

| Stage | Directory | Format | Purpose |
|-------|-----------|--------|---------|
| 1. Ingestion | `raw/resumes/`, `raw/job_descriptions/` | PDF, DOC, DOCX | Immutable source documents; never mutate in place |
| 2. Extraction | `extracted/` | JSON per document | Plain text + metadata from [Document Extraction](../extraction/README.md) |
| 3. Cleaning | `cleaned/` | JSON per document | Normalized whitespace, encoding fixes, section hints |
| 4. Normalization | `normalized/` | JSON per document | TOON-aligned structured records; schema-validated |
| 5. Training format | `jsonl/` | JSONL | Instruction pairs for fine-tuning and provider benchmarking |
| — | `benchmark/` | JSONL (frozen) | Held-out gold set; versioned, never used for training |
| — | `synthetic/` | JSON / JSONL | LLM-generated or rule-augmented samples for edge cases |
| — | `silver/` | Per-document dirs | Silver layer for Proposal Generator input |
| — | `proposals/` | Per-document dirs | Proposal Generator output |

## Stage artifact schema

Each JSON artifact (stages `extracted` through `normalized`) should include provenance:

```json
{
  "id": "uuid",
  "doc_type": "resume",
  "source_file": "dataset/lake/raw/resumes/example.pdf",
  "source_hash": "sha256:...",
  "pipeline_version": "1.0.0",
  "stage": "normalized",
  "created_at": "ISO8601",
  "payload": { }
}
```

JSONL records in `jsonl/` and `benchmark/` follow the schema in [DATA_PIPELINE.md](../../docs/DATA_PIPELINE.md).

## Versioning

Dataset versions are registered in `registry/datasets/`. Never overwrite a versioned dataset — create `jsonl/v2/` or a new manifest entry.

## Git policy

- **Committed:** README, manifests in `registry/datasets/`, benchmark version metadata
- **Gitignored:** Raw files, intermediate JSON, JSONL (may contain PII) — see `ai/.gitignore`

## HRMS export (future)

Read-only export from `parsed_resumes` / `parsed_jds` lands in `raw/` or `normalized/` depending on whether raw files are available. Register export provenance in `registry/datasets/`.

## Feature coverage (long-term)

| Feature | Primary dataset stage |
|---------|----------------------|
| Resume parsing | `normalized/` → `jsonl/` |
| JD parsing | `normalized/` → `jsonl/` |
| Bulk parsing | Same pipeline, batch manifests |
| Resume matching | `normalized/` + job embeddings (future) |
| Skill extraction / normalization | `normalized/` skills fields |
| Summarization | `cleaned/` or `normalized/` |
| Interview questions | `normalized/` pairs |

Canonical pipeline reference: [DATA_PIPELINE.md](../../docs/DATA_PIPELINE.md).
