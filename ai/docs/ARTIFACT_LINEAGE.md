# Artifact Lineage

Every transformation in the AI platform produces a **versioned artifact** with traceable parentage. This document defines the artifact model — no implementation code yet.

---

## Artifact chain (parsing feature)

```
ART-RAW          Raw Resume / JD (PDF, DOC, DOCX)
    │
    ▼
ART-EXTRACT      Extracted Text (JSON)
    │
    ▼
ART-CLEAN        Cleaned Text (JSON)
    │
    ▼
ART-NORM         Normalized JSON (TOON-aligned)
    │
    ▼
ART-JSONL        JSONL Dataset (train / val / test)
    │
    ▼
ART-ADAPTER      LoRA / QLoRA Adapter
    │
    ▼
ART-MERGED       Merged Model (HF format)
    │
    ▼
ART-GGUF         GGUF Quantized Model
    │
    ▼
ART-EVAL         Evaluation Report
    │
    ▼
ART-DEPLOY       Deployment Package (Modelfile, manifest)
```

Parallel branches:
- `ART-NORM` → `ART-BENCH` (benchmark gold records, frozen)
- `ART-NORM` → `ART-SYNTH` (synthetic augmentations)

---

## Artifact record schema (conceptual)

Every artifact will eventually carry:

```yaml
artifact:
  id: ART-EXTRACT-a1b2c3d4          # Unique ID (required)
  type: EXTRACT                       # Artifact type enum (required)
  version: "1.0.0"                    # Semantic or incremental (required)
  parent_id: ART-RAW-e5f6g7h8         # Parent artifact (null for roots)
  parent_ids: []                      # Multiple parents for merges
  created_at: "2026-06-25T12:00:00Z"  # ISO 8601 (required)
  created_by: engineer@company.com     # Actor (required)
  pipeline_version: "1.2.0"           # Preprocessing pipeline version
  git_commit: abc1234                 # AI workspace commit

  source:
    dataset_id: DS-PARSE-v1.0.0       # Source dataset (if applicable)
    document_id: uuid                 # Source document (if applicable)
    file_path: datasets/raw/resumes/x.pdf

  storage:
    path: datasets/extracted/resume/uuid.json
    size_bytes: 12400
    sha256: "a1b2c3d4e5f6..."         # Content checksum (required)

  metadata:
    doc_type: resume
    char_count: 4521
    extraction_method: pypdf
    feature: parsing

  lineage:
    children: []                      # Populated by downstream stages
    registry_refs:                    # Links to registry entries
      - registry/datasets/DS-PARSE-v1.0.0.yaml
```

---

## Artifact types

| Type | ID prefix | Storage location | Parent(s) |
|------|-----------|------------------|-----------|
| Raw document | `ART-RAW` | `datasets/raw/` | — |
| Extracted text | `ART-EXTRACT` | `datasets/extracted/` | `ART-RAW` |
| Cleaned text | `ART-CLEAN` | `datasets/cleaned/` | `ART-EXTRACT` |
| Normalized record | `ART-NORM` | `datasets/normalized/` | `ART-CLEAN` |
| JSONL dataset | `ART-JSONL` | `datasets/jsonl/` | `ART-NORM` (many) |
| Benchmark set | `ART-BENCH` | `datasets/benchmark/` | `ART-NORM` (curated) |
| Synthetic record | `ART-SYNTH` | `datasets/synthetic/` | `ART-NORM` or generated |
| LoRA adapter | `ART-ADAPTER` | `models/adapters/` | `ART-JSONL` |
| Merged model | `ART-MERGED` | `models/merged/` | `ART-ADAPTER` + base |
| GGUF model | `ART-GGUF` | `models/gguf/` | `ART-MERGED` |
| Evaluation report | `ART-EVAL` | `evaluation/reports/` | `ART-GGUF` or provider |
| Deployment package | `ART-DEPLOY` | `exports/` | `ART-GGUF` |

---

## Lineage graph (multi-feature)

```
                    ART-RAW
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ART-EXTRACT   ART-EXTRACT   ART-EXTRACT
     (resume)       (jd)       (profile)
          │            │            │
          ▼            ▼            ▼
    ART-NORM      ART-NORM      ART-NORM
          │            │            │
    ┌─────┴─────┐      │      ┌─────┴─────┐
    ▼           ▼      ▼      ▼           ▼
ART-JSONL  ART-BENCH  ...  ART-JSONL  ART-BENCH
(parsing)  (BENCH-PARSE)     (matching) (BENCH-MATCH)
    │
    ▼
ART-ADAPTER → ART-MERGED → ART-GGUF → ART-EVAL → ART-DEPLOY
```

Each feature branch shares early stages (RAW → NORM) but diverges at JSONL/benchmark/training.

---

## Merge artifacts (multiple parents)

| Artifact | Parents |
|----------|---------|
| `ART-MERGED` | `ART-ADAPTER` + `ART-BASE` (foundation model) |
| `ART-JSONL` (combined) | Multiple `ART-NORM` records |
| `ART-BENCH` | Curated subset of `ART-NORM` (human selection) |

```yaml
parent_ids:
  - ART-ADAPTER-parsing-qlora-v1
  - ART-BASE-llama32-3b
```

---

## Checksum rules

1. **SHA-256 of file content** for all stored artifacts.
2. **Manifest checksum** — SHA-256 of sorted artifact IDs in a batch.
3. **Registry checksum** — aggregate of split checksums in `registry/datasets/`.
4. Re-processing a stage with same inputs must produce **same checksum** (idempotency).

---

## Manifest chain

Each pipeline stage writes `manifest.yaml` referencing parent manifest:

```yaml
manifest:
  artifact_id: ART-JSONL-parsing-v1
  stage: split
  pipeline_version: "1.2.0"
  parent_manifest: datasets/normalized/manifest.yaml
  record_count: 1000
  artifact_ids:
    - ART-NORM-uuid1
    - ART-NORM-uuid2
  checksum: sha256:...
  created_at: "2026-06-25T12:00:00Z"
```

---

## Reproducibility query

Given `ART-GGUF-hrparser-v1`, trace lineage:

```
ART-GGUF → ART-MERGED → ART-ADAPTER → ART-JSONL → ART-NORM* → ART-CLEAN* → ART-EXTRACT* → ART-RAW*
```

Registry entry `registry/models/hrms-parsing-v1.yaml` stores root `artifact_id` for each stage.

---

## Future implementation

| Component | Milestone | Location |
|-----------|-----------|----------|
| Artifact metadata sidecar | M3 | `{path}.artifact.yaml` next to each file |
| Lineage query CLI | M4 | `scripts/lineage_trace.py` |
| Registry integration | M3 | `registry/` records include `artifact_id` |
| CI checksum verification | M6 | Compare manifest checksums on PR |

---

## Related documents

- [VERSIONING.md](VERSIONING.md)
- [DATA_PIPELINE.md](DATA_PIPELINE.md)
- [adr/ADR-004-artifact-lineage.md](adr/ADR-004-artifact-lineage.md)
