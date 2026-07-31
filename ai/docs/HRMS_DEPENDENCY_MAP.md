# HRMS AI Dependency Map

Repository inspection performed for Milestone 1. This document maps every AI-related module, data flow, and integration point in the existing HRMS — **without modifying any of them**.

## Executive summary

| Capability | Uses LLM? | Primary module | Provider today |
|------------|-----------|----------------|----------------|
| Resume parsing | Yes | `llm_service.call_llm` | Grok/X.AI (default) |
| JD parsing | Yes | `llm_service.call_llm` | Grok/X.AI (default) |
| Document classification | No (heuristics) | `llm_service.classify_document` | N/A |
| Bulk resume parsing | Yes (local fallback) | `local_bulk_parser` → `call_llm` | Grok/X.AI |
| ATS matching | No (rule-based) | `ats_service._internal_match` | Optional external HR-ATS-API |
| Apply workflow | Indirect | Uses stored TOON, triggers ATS thread | N/A |
| n8n webhook ATS | No LLM in-app | `applications.trigger_n8n` | External n8n workflow |

---

## System context diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React)                               │
│  ResumeUploadWithParsing.jsx ──POST──▶ /api/parse/resume                 │
│  JDUploadWithParsing.jsx       ──POST──▶ /api/parse/jd                   │
│  parsingApi.js                 ◀── TOON response normalization           │
│  adminService.js               ──POST──▶ /api/admin/bulk-parse/*         │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ Bearer JWT
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        BACKEND (Flask)                                   │
│                                                                          │
│  parsing_routes.py                                                       │
│    ├─ store_raw_file (parsing_utils)                                     │
│    ├─ extract_text (text_extraction)                                     │
│    ├─ classify_document (llm_service)                                    │
│    ├─ call_llm (llm_service) ──────────────────────────────┐             │
│    ├─ validate_toon_format (parsing_utils)                   │             │
│    ├─ calculate_confidence                                   │             │
│    └─ store_parsed_resume / store_parsed_jd                  │             │
│                                                              │             │
│  modules/admin/routes.py                                     │             │
│    └─ bulk_parsing_service ──▶ local_bulk_parser ────────────┤             │
│                              └─▶ external Bulk-Resume-Parser │             │
│                                                              ▼             │
│  llm_service.py ◀────────────────────────────────────────────┘             │
│    ├─ call_xai_grok ──▶ llm_key_manager (multi-key rotation)              │
│    ├─ call_openai                                                          │
│    ├─ call_anthropic                                                       │
│    ├─ get_system_prompt (resume / jd)                                    │
│    └─ parse_llm_response ──▶ toon.toon_loads_flex                          │
│                                                                          │
│  applications.py                                                           │
│    ├─ fetch parsed_resumes / parsed_jds (TOON from DB)                   │
│    └─ thread ──▶ ats_service.match_candidate_to_job                      │
│                    ├─ external HR-ATS-API (if ATS_API_URL set)             │
│                    └─ _internal_match (weighted rules, no LLM)           │
└──────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PostgreSQL / SQLite                                                     │
│    raw_files, parsed_resumes, parsed_jds, applications (ats_result)      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Module inventory

### Core AI modules (backend root)

| File | Role | LLM dependency |
|------|------|----------------|
| `llm_service.py` | Provider dispatch, prompts, response parsing | **Direct** — XAI, OpenAI, Anthropic |
| `llm_key_manager.py` | API key rotation, cooldown, metrics | Supports `call_xai_grok` |
| `toon.py` | TOON serialize/deserialize | None (format layer) |
| `text_extraction.py` | PDF/DOC/DOCX → plain text | None (feeds LLM input) |
| `parsing_utils.py` | Cache, store, validate TOON | None |
| `parsing_routes.py` | HTTP `/api/parse/resume`, `/api/parse/jd` | Via `call_llm` |
| `env_validator.py` | Documents required env vars for Grok keys | Config only |

### Services (backend/services/)

| File | Role | LLM dependency |
|------|------|----------------|
| `local_bulk_parser.py` | In-process parallel bulk parse | `call_llm(raw_text, 'resume')` |
| `bulk_parsing_service.py` | Proxy to external parser or local fallback | Indirect |
| `ats_service.py` | Weighted skill/experience/education matching | **No LLM** (optional external API) |

### Application flow (backend/)

| File | Role | LLM dependency |
|------|------|----------------|
| `applications.py` | Apply to job, background ATS | Uses **stored TOON**, no re-parse |
| `head_hr.py` | ATS analysis display | `toon_loads_flex` only |
| `jobs.py` | Job CRUD | May reference parsed JD linkage |

### Admin module

| File | Role | LLM dependency |
|------|------|----------------|
| `modules/admin/routes.py` | Bulk parse upload/progress/download | Via `bulk_parsing_service` |

### Frontend

| File | Role | LLM dependency |
|------|------|----------------|
| `utils/parsingApi.js` | Upload, normalize TOON fields | Consumes API response |
| `components/ResumeUploadWithParsing.jsx` | Resume upload UI | API client |
| `components/JDUploadWithParsing.jsx` | JD upload UI | API client |
| `components/JobCard.jsx` | Displays skills from TOON/Grok format | Display only |
| `services/adminService.js` | Bulk parse admin API | API client |
| `utils/pdfReportUtils.js` | Reports from parsed data | Display only |

---

## Data flows

### Flow 1: Single resume parse

```
User uploads PDF
  → parsing_routes.parse_resume_upload()
  → parsing_utils.get_cached_parsing_result() [hash cache]
  → text_extraction.extract_text()
  → llm_service.classify_document() [heuristic]
  → llm_service.call_llm(raw_text, 'resume')
      → call_xai_grok() [default]
          → llm_key_manager.get_key_for_service()
          → POST https://api.x.ai/v1/chat/completions
      → parse_llm_response() → toon_loads_flex()
  → parsing_routes post-process (URLs, location from regex)
  → parsing_utils.validate_toon_format()
  → parsing_utils.calculate_confidence()
  → parsing_utils.store_parsed_resume() → DB
  → JSON response { toon, parsed_id, confidence }
```

### Flow 2: Single JD parse

Same as Flow 1 with `doc_type='jd'`, `store_parsed_jd`, JD system prompt, and JD validation schema.

### Flow 3: Bulk resume parse (admin)

```
Admin uploads multiple files
  → admin/routes.bulk_parse_upload()
  → bulk_parsing_service.upload_files()
      → [if BULK_PARSER_URL reachable] external Bulk-Resume-Parser API
      → [else] local_bulk_parser.start_local_job()
          → ThreadPoolExecutor (BULK_PARSE_MAX_WORKERS)
          → per file: extract_text + call_llm('resume')
          → flatten TOON → Excel export
```

### Flow 4: Candidate apply + ATS

```
Candidate applies to job
  → applications.apply_to_job()
  → fetch parsed_resumes.toon (no re-parse)
  → fetch parsed_jds.toon OR build minimal TOON from job row
  → insert application row
  → background thread: ats_service.match_candidate_to_job()
      → [if ATS_API_URL] external HR-ATS-API POST /api/match
      → [else] _internal_match() — weighted rules, no LLM
  → update applications.ats_result, match_score, shortlisted
```

Optional parallel path: `trigger_n8n()` sends TOON to n8n webhook for external ATS workflow.

---

## Environment variables (AI-related)

| Variable | Used by | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` | `llm_service` | `xai` (default), `openai`, `anthropic` |
| `XAI_MODEL` | `llm_service` | e.g. `grok-4-fast-reasoning` |
| `HRMS_API_KEY_1..9` | `llm_key_manager` | Grok key rotation |
| `XAI_API_KEY` | `llm_key_manager` | Fallback single key |
| `LLM_REQUEST_TIMEOUT` | `llm_service` | Default 45s |
| `LLM_MAX_INPUT_CHARS` | `llm_service` | Truncation (0 = none) |
| `LLM_KEY_COOLDOWN_SECONDS` | `llm_key_manager` | Default 45s |
| `OPENAI_API_KEY` | `llm_service` | OpenAI provider |
| `ANTHROPIC_API_KEY` | `llm_service` | Anthropic provider |
| `BULK_PARSER_URL` | `bulk_parsing_service` | External bulk parser |
| `BULK_PARSE_MAX_WORKERS` | `local_bulk_parser` | Parallelism |
| `ATS_API_URL`, `ATS_API_KEY` | `ats_service` | External ATS API |
| `ATS_THRESHOLD` | `ats_service` | Match threshold (60) |
| `N8N_WEBHOOK_URL` | `applications` | External workflow |

Defined in: `backend/.env.example`

---

## TOON schema contract

**Serializer:** `backend/toon.py` — `toon_dumps`, `toon_loads`, `toon_loads_flex`

**Validator:** `backend/parsing_utils.py` — `validate_toon_format()`

**Resume required shape:**
- `type: resume`
- `person` (dict): `name`, `email`, optional `phone`, `location`, URL fields
- `skills`, `experience`, `education` (lists)
- Optional: `summary`, `certifications`, `total_experience_years`

**JD required shape:**
- `type: job_description`
- `title`, `company`, `location`, `skills`, `qualifications`, `responsibilities`

**ATS consumption:** `ats_service` reads dict fields from TOON — `skills`, `mandatory_skills`, `preferred_skills`, `experience`, `education`, `person.location`, etc.

---

## Provider implementation status

| Provider | Code path | Production ready | Key rotation |
|----------|-----------|------------------|--------------|
| Grok/X.AI | `call_xai_grok` | **Yes (default)** | `llm_key_manager` |
| OpenAI | `call_openai` | Stub with retries | Single key |
| Anthropic | `call_anthropic` | Stub with retries | Single key |
| Ollama | — | **Not implemented** | — |
| Gemini | — | **Not implemented** | — |

`model_version` stored as `{LLM_PROVIDER}-v1` in `parsed_resumes` / `parsed_jds`.

---

## External services

| Service | Config | Purpose |
|---------|--------|---------|
| Bulk-Resume-Parser | `BULK_PARSER_URL` | Optional external bulk parse microservice |
| HR-ATS-API | `ATS_API_URL` | Optional external ATS scoring |
| n8n | `N8N_WEBHOOK_URL` | Optional workflow automation |
| Parsing API microservice | `PARSING_API_URL` | Referenced in `text_extraction` fallback |

---

## Integration points for future AI workspace

| HRMS touchpoint | M5 integration approach |
|-----------------|-------------------------|
| `llm_service.call_llm` | Replace internals with provider router; same function signature |
| `get_system_prompt` | Load from `ai/capabilities/*/prompt.md*.yaml` or synced copy |
| `parse_llm_response` | Unchanged — TOON contract preserved |
| `llm_key_manager` | Grok fallback only; Ollama needs no keys |
| `model_version` | Include Ollama tag + prompt version |
| `local_bulk_parser` | Auto-benefits from `call_llm` adapter change |
| `ats_service` | No change in M5; optional LLM rerank in M6 |

---

## Files with no LLM but AI-adjacent

| File | Note |
|------|------|
| `backend/services/candidate_notification_service.py` | ATS spec notifications (SHORTLISTED, etc.) |
| `frontend/src/utils/parsingApi.js` | Normalizes LLM output quirks for UI |
| `docs/ARCHITECTURE.md` | Architecture reference |
| `docs/ENGINEERING.md` | API and module reference |

---

## Verification checklist (M1)

- [x] All `call_llm` call sites identified: `parsing_routes.py`, `local_bulk_parser.py`
- [x] Key manager usage traced to `call_xai_grok` only
- [x] ATS path confirmed rule-based (no LLM in `ats_service.py`)
- [x] Frontend parsing integration mapped
- [x] TOON contract documented
- [x] No backend/frontend files modified in M1
