# Dataset Platform

Unified data engineering layer for the HRMS AI platform.

## What is this?

The dataset platform transforms raw HR documents into structured, validated, benchmark-ready artifacts. It comprises four components under one owner.

## Components

| Directory | Name | Purpose |
|-----------|------|---------|
| `factory/` | Dataset Factory | Multi-stage pipeline (inspector, extractor, …) |
| `lake/` | Data Lake | Medallion storage (`raw/` → `jsonl/`) |
| `extraction/` | Document Extraction | PDF/DOC/DOCX/RTF/TXT text extraction |
| `proposals/` | Proposal Generator | Silver documents → LLM proposals via runtime |

## Why does it exist?

Training, evaluation, and benchmarking require reproducible document pipelines. Consolidating extraction, factory stages, lake storage, and proposal generation under `dataset/` gives one clear owner.

## What belongs here?

- Pipeline stages and their Python implementations
- Stage manifests, schemas, and architecture YAML
- Data lake directory structure (artifacts gitignored)
- CLIs for inspection, extraction, and proposal generation

## What should never be placed here?

- AI runtime execution → `ai/runtime/`
- Capability definitions → `ai/capabilities/`
- TOON ontology → `ai/toon/`
- Production HRMS parsing → `backend/`

## Data flow

```
raw (lake) → extraction → extracted (lake) → factory stages → silver (lake)
                                                              ↓
                                                    proposals (lake)
                                                              ↓
                                                    jsonl / benchmark (lake)
```

## CLIs

| Tool | Command |
|------|---------|
| Dataset Inspector | `python dataset/factory/inspector/inspect_dataset.py` |
| Document Extraction | `python -m dataset.extraction.cli.extract_documents` |
| Proposal Generator | `python -m dataset.proposals.cli.generate_proposals` |

## Related documentation

- [Factory](factory/README.md)
- [Lake](lake/README.md)
- [Extraction](extraction/README.md)
- [Proposal Generator](proposals/README.md)
- [Data pipeline](../docs/DATA_PIPELINE.md)
