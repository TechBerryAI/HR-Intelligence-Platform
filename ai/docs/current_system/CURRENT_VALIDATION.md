# Current Validation — Technical Specification

**Status:** Reverse-engineered from production code  
**Primary validators:** `parsing_utils.validate_toon_format()`, `parsing_routes.calculate_confidence()`, frontend `validateFileForParsing()`

---

## Validation Layers Overview

```
Layer 1: HTTP / Upload        (parsing_routes, frontend)
Layer 2: Text Extraction      (text_extraction.py)
Layer 3: LLM Response Parse   (parse_llm_response / toon_loads_flex)
Layer 4: TOON Schema          (validate_toon_format)
Layer 5: Confidence Heuristic (calculate_confidence) — non-blocking
Layer 6: Frontend Mapping     (mapResumeTOONToForm — type check only)
```

Bulk local parsing implements **Layers 1–3 only** (no Layer 4–5).

---

## Layer 1: Upload Validation

### Backend (`parsing_routes.py`)

| Check | Resume | JD | On Failure |
|-------|--------|-----|------------|
| `file` in `request.files` | ✓ | ✓ | 400 |
| Non-empty filename | ✓ | ✓ | 400 |
| Extension in `pdf,doc,docx` | ✓ | ✓ | 400 |
| Size ≤ 10 MB | ✓ | ✓ | 400 |
| JWT `uploader_id` present | ✓ | ✓ | 401 |
| `authenticate_token` | ✓ | ✓ | 401 |

### Frontend (`parsingApi.validateFileForParsing`)

| Check | Rule | On Failure |
|-------|------|------------|
| Extension | `pdf`, `doc`, `docx` | `{valid: false, error: ...}` |
| Size | ≤ 10 MB | Error message |
| MIME type | Checked secondarily | Extension is primary |

### Admin Bulk (`modules/admin/routes.py`)

| Check | Rule |
|-------|------|
| HR role | `@require_hr` |
| At least one valid file | Extension filter |
| Non-empty file bytes | Skipped if empty |

---

## Layer 2: Text Extraction Validation

| Location | What | Threshold | Failure |
|----------|------|-----------|---------|
| `extract_text_from_pdf` | Extracted char count | ≥ 30 after strip | `ValueError` → 400 |
| `extract_text` (route) | `len(raw_text.strip())` | ≥ 30 | 400 with scanned PDF hint |
| `local_bulk_parser._process_one_file` | Same | ≥ 30 | File marked failed, skipped |
| PDF API fallback | `raw_text` from external API | ≥ 30 | Raises, cascades to 400 |

**No OCR** in local path — image PDFs fail unless external Parsing API succeeds.

---

## Layer 3: LLM Response Validation

| Step | Function | Validates | Failure |
|------|----------|-----------|---------|
| Parse | `parse_llm_response` | Non-empty dict from TOON/JSON | `ValueError` → HTTP 500 |
| Provider config | `call_llm` | `LLM_PROVIDER` known | `ValueError` |
| API keys | `call_xai_grok` | At least one key | `ValueError` |
| HTTP | Provider adapters | 2xx response | Key rotation / retry / 500 |

### Retry Logic

| Provider | Retries | Backoff | Key Rotation |
|----------|---------|---------|--------------|
| X.AI | Per-key loop (all keys once) | Cooldown 45s on 429/5xx/timeout | Yes |
| OpenAI | 3 attempts | Linear 2s, 4s | No |
| Anthropic | 3 attempts | Linear 2s, 4s | No |

**No retry** on malformed TOON/JSON content from a successful HTTP 200.

---

## Layer 4: TOON Schema Validation

### Function

```108:151:backend/parsing_utils.py
def validate_toon_format(toon: Dict[str, Any], document_type: str) -> Tuple[bool, Optional[str]]:
```

### Resume (`document_type == 'resume'`)

| Rule | Error Message |
|------|---------------|
| `toon` is dict | `"TOON must be a dictionary"` |
| `toon.type == 'resume'` | `"TOON type mismatch..."` |
| Keys exist: `person`, `skills`, `experience`, `education` | `"Missing required field: {field}"` |
| `person` is dict | `"person must be a dictionary"` |
| Keys exist: `person.name`, `person.email`, `person.phone` | `"Missing person field: {field}"` |
| Optional URL fields are str or null | `"person.{field} must be a string or null"` |
| `otherUrls` is list or null | `"person.otherUrls must be an array or null"` |

**Not validated:**

- Non-empty `skills`, `experience`, `education`
- Email/phone format
- Nested experience/education structure
- `type` field set by LLM (failure if wrong/missing)

### Job Description (`document_type == 'job_description'`)

| Rule | Error Message |
|------|---------------|
| `toon.type == 'job_description'` | Type mismatch |
| Keys exist: `title`, `location`, `skills`, `responsibilities` | Missing field |

**Not validated:** `company` (despite prompt CRITICAL and yaml `required_output_fields`)

### Route Handling

```python
is_valid, error_msg = validate_toon_format(toon, 'resume' | 'job_description')
if not is_valid:
    return jsonify({'status': 'error', 'error': f'Invalid TOON format: {error_msg}'}), 400
```

**Side effect:** Failed parse is **not stored**; raw file may already exist in DB.

---

## Layer 5: Confidence Scoring (Non-Gating)

### Resume (`calculate_confidence`)

| Category | Weight | Logic |
|----------|--------|-------|
| Required: `person`, `skills`, `experience`, `education` | 70% (0.175 each) | `person`: full if name+email; partial if one; lists: len>0 |
| Optional: `summary`, `certifications` | 30% (0.15 each) | Presence bonus |
| Floor | — | If person + (experience OR education): min 0.65 |
| Ceiling | — | 1.0 if all required fully present |

### JD (`calculate_confidence`)

| Category | Weight |
|----------|--------|
| Required: `title`, `skills`, `responsibilities` | 70% (0.233 each) |
| Optional: `company`, `location`, `qualifications` | 30% (0.1 each) |

**Mismatch with validation:** JD confidence treats `company`/`location` as optional; validation **requires** `location`.

### Frontend Confidence UX

- `JDUploadWithParsing`: warns if `confidence < 0.75`
- `ResumeUploadWithParsing`: displays confidence; similar low-confidence pattern

Confidence does **not** block API success or DB write.

---

## Layer 6: Frontend TOON Mapping Validation

| Function | Check | On Failure |
|----------|-------|------------|
| `mapResumeTOONToForm` | `toon.type === 'resume'` | Throws `Invalid resume TOON format` |
| `mapJDTOONToForm` | `toon.type === 'job_description'` | Throws `Invalid job description TOON format` |

Defensive normalization (not strict validation):

- `ensureArray`, `ensureStringArray`
- `normalizeToYYYYMM` for dates
- Portfolio URL heuristics

---

## Document Classification (Advisory Only)

```278:303:backend/llm_service.py
def classify_document(text: str) -> Literal['resume', 'jd', 'unknown']:
```

| Outcome | Action |
|---------|--------|
| `resume` / `jd` | No route change |
| `unknown` | Log warning; **proceed as resume** on resume endpoint |

**Not a validation gate.**

---

## Duplicate Detection (Cache Hit)

| Check | `file_hash` + `uploader_id` match existing parse |
| Action | Return cached TOON without re-validation |
| Risk | Stale schema if validation rules change |

---

## Apply-Time Validation (Consumer)

`applications.apply_job()`:

| Check | Failure |
|-------|---------|
| Parsed resume exists for candidate | 400 "No parsed resume found" |
| `toon_loads_flex` succeeds | 500 "Invalid stored parsing data" |
| Profile `completed` | 400 |
| Job enabled | 404 |

Does **not** re-run `validate_toon_format` on stored data.

---

## Bulk Parsing Validation Gaps

| Validation | Single Parse | Bulk Local |
|------------|--------------|------------|
| `validate_toon_format` | ✓ | ✗ |
| `calculate_confidence` | ✓ | ✗ |
| Post-process URLs/location | ✓ | ✗ |
| DB storage | ✓ | ✗ |
| Per-file error isolation | N/A | ✓ (failed files counted) |

Failed bulk files: logged in `failed_filenames`; job still completes.

---

## Failure Handling Summary

| Stage | HTTP | Stored Raw File? | Stored Parse? |
|-------|------|------------------|---------------|
| Upload invalid | 400 | No | No |
| Extraction fail | 400 | Yes (if past store) | No |
| LLM fail | 500 | Yes | No |
| TOON invalid | 400 | Yes | No |
| Success | 200 | Yes | Yes |
| Cache hit | 200 | Existing | Existing |

---

## Fallback Behavior

| Scenario | Fallback |
|----------|----------|
| PDF low text locally | External `PARSING_API_URL` parse endpoint |
| Parsing API also fails | 400 to client |
| X.AI key failure | Rotate to next key; cooldown failed keys |
| All X.AI keys fail | 500 |
| OpenAI/Anthropic network error | 3 retries then 500 |
| Bulk external service down | `local_bulk_parser` in-process |
| No parsed JD on apply | `_jd_toon_from_job_row(job)` synthetic TOON |
| ATS API down | `_internal_match()` rule-based scorer |
