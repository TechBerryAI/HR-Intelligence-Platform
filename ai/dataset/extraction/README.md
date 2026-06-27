# Document Extraction

Extracts plain text and metadata from HR documents (PDF, DOC, DOCX, RTF, TXT).

## What is this?

The Document Extraction engine discovers source files, runs format-specific extractors, cleans and validates output, and writes per-document artifacts to the data lake.

## Why does it exist?

Downstream factory stages and the Proposal Generator require consistent `raw_text.txt` and extraction reports. This module is the canonical text-extraction implementation for the AI platform.

## What belongs here?

| Path | Purpose |
|------|---------|
| `extractors/` | Format-specific extractors (pdf, docx, doc, rtf, txt) |
| `cleaners/` | Post-extraction text cleaning |
| `validators/` | Quality gates and finalization |
| `engine/` | Discovery, orchestration, processing |
| `cli/` | `python -m dataset.extraction.cli.extract_documents` |
| `tests/` | Golden and integration tests |

## What should never be placed here?

- LLM parsing or TOON projection → `ai/capabilities/`, `ai/runtime/`
- Dataset factory inspector logic → `dataset/factory/inspector/`
- Production HRMS upload parsing → `backend/text_extraction.py`

## Dependencies

| Consumes | From |
|----------|------|
| Inspector hashing (tests) | `dataset/factory/inspector/` |
| Output paths | `dataset/lake/extracted/` |

## Consumers

| Consumer | Usage |
|----------|-------|
| Dataset Factory pipeline | Stage after raw ingestion |
| Proposal Generator | Reads silver-layer documents |

## Quick start

```bash
cd ai
python -m dataset.extraction.cli.extract_documents --help
pytest dataset/extraction/tests/
```

## Configuration

Default: `config.default.yaml` in this directory.

Default inspection path: `dataset/lake/inspection/`

## Related documentation

- [Dataset platform](../README.md)
- [Data lake](../lake/README.md)
