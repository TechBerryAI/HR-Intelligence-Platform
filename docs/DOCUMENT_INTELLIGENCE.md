# Document Intelligence Engine

Production document understanding subsystem for HCIP.

## Pipeline

```
Document → Extraction → Layout → Sections → Independent Section Parsers
  → Canonical Model → Knowledge → Validation → Confidence
  → Form Mapper → Form DTO → Frontend
  → Canonical→TOON → DB/ATS
```

**Critical rule:** React never consumes raw AI/TOON. Clients receive Form DTOs only.

## PDF text extraction

Production extraction lives in `app/ai/parser/text_extraction.py`.

| Engine | Role |
|--------|------|
| **PyMuPDF** (`extract_text_from_pdf_pymupdf`) | Primary / default. Digital text + per-page OCR + PyMuPDF tables. |
| **pdfplumber** (`pdfplumber_extractor.py`) | Automatic secondary. Considered only when PyMuPDF text is thin, garbage, layout-broken, or looks like unextracted tables; selected only if objectively better. |
| PyPDF2 / parsing API / force OCR | Existing last-resort fallbacks. Unchanged. |

The decision is automatic. There is no `PDF_ENABLE_PDFPLUMBER` / `PDF_PRIMARY_EXTRACTOR` switch. A usable PyMuPDF result is never replaced, and both libraries are not run on every PDF. Scanned pages stay on the existing PyMuPDF+OCR path.

```bash
# From repo root
pytest tests/backend/test_text_extraction_ocr.py tests/backend/test_pdfplumber_fallback.py -q
```

## Package layout

```
app/ai/document_intelligence/
  pipeline.py       # sole production entry (run_document_intelligence)
  contracts/        # FieldContract registry
  deterministic/    # email/phone/URL/dates (never AI)
  sections/         # typed SectionSpan isolation
  parsers/resume/   # personal, contact, experience, education, skills, …
  parsers/jd/       # title, responsibilities, skills, salary, …
  semantic/         # section-scoped AI for unresolved gaps only
  knowledge/        # skill/title normalization on canonical models
  validation/       # validators + anti-contamination
  mapping/          # explicit Form DTO mappers
  serialize/toon.py # Canonical → TOON for ATS only
  models/           # CandidateProfile, JobProfile, Form DTOs
  response.py       # client payloads (Form DTO only)
```

## Clients

- Parse APIs: `domains/recruitment/api/parsing.py`
- Frontend: `takeResumeFormDTO` / `takeJDFormDTO` in `parsingApi.js`

## Eval / gold lake

- Gold lake: `ai/dataset/lake/benchmark/parsing/v1`
- Regenerate / report (writes `ai/eval/reports/`):

```bash
python3 ai/eval/upgrade_gold_canonical.py
python3 ai/eval/run_field_accuracy_report.py
pytest tests/backend/document_intelligence/ -q
```

See also: [WORKFLOWS.md](WORKFLOWS.md).
