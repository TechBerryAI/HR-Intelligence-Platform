# Extract

**Stage 1** of the preprocessing pipeline — document → plain text.

## Inputs

| Source | Format |
|--------|--------|
| `datasets/raw/resumes/` | PDF, DOC, DOCX |
| `datasets/raw/job_descriptions/` | PDF, DOC, DOCX |

## Outputs

| Destination | Format |
|-------------|--------|
| `datasets/extracted/{doc_type}/{id}.json` | JSON with `raw_text`, file metadata |

## Responsibilities

1. Detect file type and route to appropriate extractor (PyPDF, pdfplumber, python-docx).
2. Compute `source_hash` (SHA-256 of raw bytes) for deduplication and cache keys.
3. Record extraction method, page count, and character count.
4. Flag extraction failures (scanned PDF, corrupt file) without halting the batch.

## Output schema (excerpt)

```json
{
  "id": "uuid",
  "doc_type": "resume",
  "source_file": "datasets/raw/resumes/candidate_001.pdf",
  "source_hash": "sha256:abc...",
  "stage": "extracted",
  "extraction": {
    "method": "pypdf",
    "page_count": 2,
    "char_count": 4521,
    "warnings": []
  },
  "raw_text": "..."
}
```

## Alignment with HRMS

Behavior should mirror `backend/text_extraction.py` so training data matches production inference inputs.

## Future scripts

| Script | Purpose |
|--------|---------|
| `scripts/extract_batch.py` | Batch extract all files in `raw/` |
| `scripts/extract_single.py` | CLI for one file (debugging) |

## Next stage

→ `preprocessing/clean/`
