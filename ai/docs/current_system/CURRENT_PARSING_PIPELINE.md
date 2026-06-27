# Current Parsing Pipeline — Technical Specification

**Status:** Reverse-engineered from production code (read-only analysis)  
**Scope:** Resume parsing, job description (JD) parsing, bulk resume parsing  
**Evidence base:** `backend/parsing_routes.py`, `backend/text_extraction.py`, `backend/llm_service.py`, `backend/parsing_utils.py`, `backend/toon.py`, `frontend/src/utils/parsingApi.js`

---

## Executive Summary

The HRMS converts uploaded PDF/DOC/DOCX files into structured **TOON** (Token-Oriented Object Notation) dictionaries via this path:

1. Authenticated HTTP upload
2. SHA-256 duplicate cache lookup
3. Raw file persistence (`raw_files` + local disk)
4. Local text extraction (with optional external Parsing API fallback for image PDFs)
5. Optional heuristic document classification (resume route only)
6. LLM invocation (default: X.AI Grok) with inline system prompts
7. Resume-only regex post-processing (URLs, location)
8. Schema validation (`validate_toon_format`)
9. Heuristic confidence scoring (`calculate_confidence`)
10. Database persistence (`parsed_resumes` / `parsed_jds`)
11. JSON API response consumed by React autofill mappers

Bulk parsing follows a **parallel path**: external Bulk-Resume-Parser service or in-process `local_bulk_parser`, producing Excel rows — **not** full TOON persistence.

---

## Pipeline A: Single Resume Parse

### Entry Point

| Attribute | Value |
|-----------|-------|
| **HTTP** | `POST /api/parse/resume` |
| **Auth** | `Authorization: Bearer <JWT>` via `@authenticate_token` |
| **Body** | `multipart/form-data`: `file`, optional `candidate_id` |
| **Handler** | `parsing_routes.parse_resume_upload()` |

### Frontend Origin

| File | Function |
|------|----------|
| `frontend/src/components/ResumeUploadWithParsing.jsx` | `processFile()` |
| `frontend/src/utils/parsingApi.js` | `uploadAndParseResume()` |
| `frontend/src/pages/ApplicantProfile.jsx` | Embeds upload component; `handleResumeAutofill()` |

### Stage-by-Stage

#### 1. Upload & Request Validation

| | |
|---|---|
| **Purpose** | Accept file, enforce type/size, resolve uploader identity |
| **Input** | Multipart file bytes, JWT claims |
| **Output** | `file_data`, `filename`, `uploader_id`, `uploader_role`, `candidate_id` |
| **Files** | `backend/parsing_routes.py` (`allowed_file`, `get_mime_type`) |
| **Rules** | Extensions: `pdf`, `doc`, `docx`; max 10 MB; `secure_filename()` |
| **Errors** | 400 missing file/type/size; 401 missing user ID |
| **Security** | JWT required; candidate auto-links `candidate_id` from token |

#### 2. Duplicate Detection (Cache)

| | |
|---|---|
| **Purpose** | Skip re-parse for identical file from same uploader |
| **Input** | `SHA-256(file_data)`, `uploader_id`, doc type `'resume'` |
| **Output** | Cached `{parsed_id, raw_file_id, toon, confidence, model_version}` or `None` |
| **Files** | `parsing_utils.compute_file_hash()`, `parsing_utils.get_cached_parsing_result()` |
| **Query** | Join `parsed_resumes` ↔ `raw_files` on `file_hash` + `uploader_id` |
| **Side effect** | On cache hit for candidates: `UPDATE parsed_resumes SET candidate_id` |
| **Response flag** | `is_duplicate: true` |

#### 3. Raw File Storage

| | |
|---|---|
| **Purpose** | Persist original bytes + metadata |
| **Input** | File bytes, uploader metadata |
| **Output** | `raw_file_id`, `storage_url` (`file://...`) |
| **Files** | `parsing_utils.store_raw_file()`, `parsing_utils.save_file_to_storage()` |
| **DB** | `raw_files` table; unique `(file_hash, uploader_id)` |
| **Env** | `UPLOAD_FOLDER` (default `./uploads`) |

#### 4. Text Extraction

| | |
|---|---|
| **Purpose** | Convert binary document to plain text for LLM |
| **Input** | `file_data`, `filename` |
| **Output** | `raw_text` string |
| **Files** | `backend/text_extraction.py` |
| **PDF** | `PyPDF2.PdfReader`; optional `PDF_MAX_PAGES` cap |
| **DOCX/DOC** | `python-docx` paragraphs + table cells |
| **Fallback** | If PDF local extraction yields &lt;30 chars → `extract_text_from_pdf_via_api()` → `POST {PARSING_API_URL}/api/v1/parse/resume` |
| **Min text** | 30 characters after strip; else 400 |
| **Errors** | 400 with scanned/corrupted guidance |
| **Performance** | `PDF_MAX_PAGES=0` means all pages; env tunable |

#### 5. Document Classification (Resume Only)

| | |
|---|---|
| **Purpose** | Heuristic sanity check (not enforced) |
| **Input** | `raw_text` |
| **Output** | `'resume'`, `'jd'`, or `'unknown'` |
| **Files** | `llm_service.classify_document()` |
| **Logic** | Keyword scoring: resume vs JD indicators; threshold ≥2 matches |
| **Behavior** | If `'unknown'`, logs warning and **continues as resume** |
| **Note** | JD route does **not** call classification |

#### 6. Prompt Construction & LLM Invocation

| | |
|---|---|
| **Purpose** | Structure unstructured text into TOON dict |
| **Input** | `raw_text` (optionally truncated by `LLM_MAX_INPUT_CHARS`) |
| **Output** | Python `dict` (TOON semantics) |
| **Files** | `llm_service.call_llm()`, `get_system_prompt()`, `parse_llm_response()` |
| **System prompt** | Inline in `get_system_prompt('resume')` — see `CURRENT_PROMPTS.md` |
| **User message** | **Raw document text only** (no template wrapper) |
| **Provider** | `LLM_PROVIDER` env: `xai` (default), `openai`, `anthropic` |
| **Default model** | `grok-4-fast-reasoning` (`XAI_MODEL`) |
| **X.AI params** | `temperature: 0.2`, `max_tokens: 2048`, timeout `LLM_REQUEST_TIMEOUT` (default 45s) |
| **Key rotation** | `llm_key_manager`: `HRMS_API_KEY_1..9`, fallback `XAI_API_KEY` |
| **Parse** | `toon_loads_flex(content)` — accepts TOON text or JSON |

#### 7. Resume Post-Processing (Route-Level)

| | |
|---|---|
| **Purpose** | Fill gaps LLM missed |
| **Input** | `toon`, `raw_text` |
| **Output** | Enriched `toon['person']` |
| **Files** | `parsing_routes.parse_resume_upload()` lines 273–352 |
| **URL regex** | LinkedIn, GitHub, Twitter/X, portfolio → `person.*`; remainder → `otherUrls` |
| **Location** | Regex patterns + Indian city header fallback |
| **Note** | **Not applied** in bulk local parser |

#### 8. TOON Validation

| | |
|---|---|
| **Purpose** | Reject structurally invalid parses before DB write |
| **Input** | `toon`, `document_type='resume'` |
| **Output** | `(bool, error_message)` |
| **Files** | `parsing_utils.validate_toon_format()` |
| **Rules** | See `CURRENT_VALIDATION.md` |
| **Failure** | HTTP 400 |

#### 9. Confidence Scoring

| | |
|---|---|
| **Purpose** | UI quality indicator (not used for gating) |
| **Input** | `toon`, `doc_type='resume'` |
| **Output** | Float 0.0–1.0 |
| **Files** | `parsing_routes.calculate_confidence()` |
| **Logic** | Weighted field completeness; floor 0.65 if person + (experience OR education) |

#### 10. Database Storage

| | |
|---|---|
| **Purpose** | Persist canonical parse for ATS and apply flow |
| **Input** | `raw_file_id`, `candidate_id`, `toon`, `full_text`, `confidence`, `model_version` |
| **Output** | `parsed_id` (UUID) |
| **Files** | `parsing_utils.store_parsed_resume()` |
| **Serialization** | `toon_dumps(toon)` → TEXT column |
| **model_version** | `{LLM_PROVIDER}-v1` e.g. `xai-v1` |

#### 11. API Response & Consumer Mapping

```json
{
  "status": "ok",
  "raw_file_id": "uuid",
  "parsed_id": "uuid",
  "confidence": 0.94,
  "toon": { ... },
  "is_duplicate": false,
  "model_version": "xai-v1"
}
```

Frontend: `mapResumeTOONToForm(toon)` → profile form fields (`ApplicantProfile`).

---

## Pipeline B: Single Job Description Parse

### Entry Point

| Attribute | Value |
|-----------|-------|
| **HTTP** | `POST /api/parse/jd` |
| **Auth** | JWT; uploader resolved from `hrId` or `id` |
| **Body** | `file`, optional `job_id` |
| **Handler** | `parsing_routes.parse_jd_upload()` |

### Differences from Resume Pipeline

| Stage | Resume | JD |
|-------|--------|-----|
| Classification | Yes (non-blocking) | **No** |
| Post-processing | URL/location regex | **None** |
| `call_llm` doc_type | `'resume'` | `'jd'` |
| System prompt | Resume TOON example | JD TOON example |
| Validation type | `'resume'` | `'job_description'` |
| Storage table | `parsed_resumes` | `parsed_jds` |
| Confidence fields | person, skills, experience, education | title, skills, responsibilities (+ optional company, location, qualifications) |

### Frontend Origin

| File | Consumer |
|------|----------|
| `frontend/src/components/JDUploadWithParsing.jsx` | HR job posting form |
| `frontend/src/pages/Dashboard.jsx` | `handleJDAutofill()` |

---

## Pipeline C: Bulk Resume Parse (Admin)

### Entry Point

| Attribute | Value |
|-----------|-------|
| **HTTP** | `POST /api/admin/bulk-parse/upload` |
| **Auth** | JWT + `@require_hr` |
| **Handler** | `modules/admin/routes.bulk_parse_upload()` → `bulk_parsing_service.upload_files()` |

### Routing Logic

```
upload_files(files_list)
  ├─ IF BULK_PARSER_URL reachable
  │     POST {BULK_PARSER_URL}/api/upload  (external service, port 8001 default)
  └─ ELSE
        local_bulk_parser.start_local_job()
          ThreadPoolExecutor (BULK_PARSE_MAX_WORKERS, default 6)
          per file: extract_text → call_llm('resume') → _flatten_toon → Excel row
```

### Critical Divergences from Single Parse

| Feature | Single Resume | Bulk Local |
|---------|---------------|------------|
| `validate_toon_format` | Yes | **No** |
| URL/location post-process | Yes | **No** |
| DB persistence | Yes | **No** (in-memory job store) |
| Output | JSON + TOON | Excel download |
| Duplicate cache | Yes | **No** |
| `candidate_id` link | Yes | **No** |
| Parallelism | Sequential per request | Thread pool per job |

### Progress & Download

- `GET /api/admin/bulk-parse/progress/{job_id}`
- `GET /api/admin/bulk-parse/download/{job_id}` → streams `.xlsx`

---

## Retrieval Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/parsed/resume/{parsed_id}` | Fetch stored TOON by parse ID |
| `GET /api/parsed/jd/{parsed_id}` | Fetch stored JD TOON |

Both deserialize with `toon_loads_flex()`.

---

## Dead / Latent Code Paths

| Code | Status |
|------|--------|
| `parsing_utils.call_parsing_api()` | Defined but **not called** by `parsing_routes` |
| `PARSING_API_URL` microservice | Referenced only for PDF text fallback; service **not in this repo** |
| `ai/capabilities/*/prompt.md*.yaml.example` | Documentation/training templates; **not loaded at runtime** |

---

## Environment Variables (Parsing)

| Variable | Default | Role |
|----------|---------|------|
| `LLM_PROVIDER` | `xai` | Provider selection |
| `XAI_MODEL` | `grok-4-fast-reasoning` | Grok model |
| `HRMS_API_KEY_1..9` | — | Key rotation |
| `XAI_API_KEY` | — | Fallback key |
| `LLM_REQUEST_TIMEOUT` | `45` | API timeout (seconds) |
| `LLM_MAX_INPUT_CHARS` | `0` (no trim) | Truncate long docs |
| `LLM_KEY_COOLDOWN_SECONDS` | `45` | Key cooldown on failure |
| `UPLOAD_FOLDER` | `./uploads` | Raw file storage |
| `PDF_MAX_PAGES` | `0` | PDF page limit |
| `PARSING_API_URL` | `http://localhost:4000` | PDF extraction fallback |
| `PARSING_API_KEY` | — | Fallback API auth |
| `BULK_PARSER_URL` | `http://localhost:8001` | External bulk service |
| `BULK_PARSE_MAX_WORKERS` | `6` | Local bulk parallelism |

---

## Data Flow Diagram (Single Resume)

```
[Browser] ResumeUploadWithParsing
    │ POST /api/parse/resume + JWT
    ▼
[parsing_routes] validate file → hash → cache?
    │ miss
    ▼
[store_raw_file] → raw_files + disk
    ▼
[extract_text] PyPDF2 / docx → raw_text
    ▼
[classify_document] (warning only)
    ▼
[call_llm] Grok/OpenAI/Anthropic → TOON dict
    ▼
[post-process] URLs, location (resume only)
    ▼
[validate_toon_format] → [calculate_confidence]
    ▼
[store_parsed_resume] → parsed_resumes
    ▼
[JSON response] → mapResumeTOONToForm → ApplicantProfile
```

---

## Downstream Use of Parsed Data

Parsed TOON is consumed by:

1. **Profile autofill** — frontend form mapping (not DB profile tables directly)
2. **Job apply + ATS** — `applications.apply_job()` loads latest `parsed_resumes` / `parsed_jds`
3. **Internal or external ATS** — `ats_service.match_candidate_to_job()`
4. **Optional n8n** — `trigger_n8n()` (configured separately; not auto-called in current `apply_job`)

See `CURRENT_DATABASE_FLOW.md` and `CURRENT_DEPENDENCIES.md`.
