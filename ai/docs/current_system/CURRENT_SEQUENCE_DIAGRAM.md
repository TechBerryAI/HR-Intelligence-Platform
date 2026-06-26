# Current Sequence Diagrams

**Status:** Reverse-engineered from production code  
**Format:** Mermaid sequence diagrams

---

## 1. Single Resume Parse (Happy Path)

```mermaid
sequenceDiagram
    autonumber
    actor User as Candidate
    participant FE as ResumeUploadWithParsing
    participant API as parsing_routes
    participant PU as parsing_utils
    participant TE as text_extraction
    participant LLM as llm_service
    participant KM as llm_key_manager
    participant XAI as X.AI Grok API
    participant DB as PostgreSQL
    participant Disk as uploads/

    User->>FE: Select PDF/DOCX
    FE->>FE: validateFileForParsing()
    FE->>API: POST /api/parse/resume (JWT, multipart)
    API->>API: allowed_file(), size check
    API->>PU: compute_file_hash()
    API->>PU: get_cached_parsing_result()
    alt Cache miss
        API->>PU: store_raw_file()
        PU->>Disk: write file
        PU->>DB: INSERT raw_files
        API->>TE: extract_text()
        TE-->>API: raw_text
        API->>LLM: classify_document() [advisory]
        API->>LLM: call_llm(raw_text, 'resume')
        LLM->>KM: get_key_for_service('parsing')
        KM-->>LLM: (slot_id, api_key)
        LLM->>XAI: POST /v1/chat/completions
        XAI-->>LLM: TOON/JSON content
        LLM->>LLM: parse_llm_response() / toon_loads_flex
        LLM-->>API: toon dict
        API->>API: post-process URLs, location
        API->>PU: validate_toon_format()
        API->>API: calculate_confidence()
        API->>PU: store_parsed_resume()
        PU->>DB: INSERT parsed_resumes
        API-->>FE: 200 {toon, parsed_id, confidence}
    else Cache hit
        PU-->>API: cached toon
        API->>DB: UPDATE candidate_id (if candidate)
        API-->>FE: 200 {is_duplicate: true}
    end
    FE->>FE: mapResumeTOONToForm(toon)
    FE->>User: Autofill profile form
```

---

## 2. Single Resume Parse (Failure Paths)

```mermaid
sequenceDiagram
    autonumber
    participant API as parsing_routes
    participant TE as text_extraction
    participant PAPI as Parsing API :4000
    participant LLM as llm_service
    participant PU as parsing_utils

    Note over API: After store_raw_file (raw file may exist)

    API->>TE: extract_text() PDF
    TE-->>API: ValueError insufficient text
    TE->>PAPI: POST /api/v1/parse/resume
    alt API fallback OK
        PAPI-->>TE: raw_text
        TE-->>API: raw_text
    else API fallback fail
        API-->>API: HTTP 400 text extraction failed
    end

    API->>LLM: call_llm()
    alt LLM HTTP / key exhaustion
        LLM-->>API: ValueError
        API-->>API: HTTP 500 LLM parsing failed
    else Unparseable response
        LLM-->>API: ValueError parse failed
        API-->>API: HTTP 500
    end

    API->>PU: validate_toon_format()
    alt Invalid TOON
        PU-->>API: (False, error_msg)
        API-->>API: HTTP 400 Invalid TOON format
    end
```

---

## 3. Job Description Parse

```mermaid
sequenceDiagram
    autonumber
    actor HR as HR User
    participant FE as JDUploadWithParsing
    participant API as parsing_routes
    participant PU as parsing_utils
    participant TE as text_extraction
    participant LLM as llm_service
    participant DB as PostgreSQL

    HR->>FE: Upload JD file
    FE->>API: POST /api/parse/jd (JWT)
    API->>PU: hash + cache check
    API->>PU: store_raw_file()
    API->>TE: extract_text()
    Note over API: No classify_document()
    API->>LLM: call_llm(raw_text, 'jd')
    LLM-->>API: toon dict
    Note over API: No URL/location post-process
    API->>PU: validate_toon_format('job_description')
    API->>API: calculate_confidence('jd')
    API->>PU: store_parsed_jd()
    PU->>DB: INSERT parsed_jds
    API-->>FE: 200 {toon, parsed_id}
    FE->>FE: mapJDTOONToForm()
    FE->>HR: Autofill job form
```

---

## 4. Apply to Job (Parsed Data Consumer)

```mermaid
sequenceDiagram
    autonumber
    actor Cand as Candidate
    participant APP as applications.py
    participant DB as PostgreSQL
    participant ATS as ats_service
    participant EXT as HR-ATS-API

    Cand->>APP: POST /api/applications {jobId}
    APP->>DB: Validate job, profile, no duplicate
    APP->>DB: SELECT parsed_resumes (latest)
    alt No parse
        APP-->>Cand: 400 No parsed resume
    end
    APP->>DB: SELECT parsed_jds (optional)
    alt No parsed JD
        APP->>APP: _jd_toon_from_job_row(job)
    end
    APP->>APP: toon_loads_flex(stored toon)
    APP->>DB: INSERT applications (status=applied)
    APP->>ATS: match_candidate_to_job() [background thread]
    alt ATS_API_URL configured
        ATS->>EXT: POST /api/match
        EXT-->>ATS: match result
    else Internal matcher
        ATS->>ATS: _internal_match()
    end
    ATS-->>APP: success, result
    APP->>DB: UPDATE applications (score, shortlisted, ats_analysis)
    APP-->>Cand: 201 Application submitted
```

---

## 5. Bulk Resume Parse (Local Fallback)

```mermaid
sequenceDiagram
    autonumber
    actor Admin as HR Admin
    participant FE as BulkResumeParser
    participant AR as admin/routes
    participant BPS as bulk_parsing_service
    participant LBP as local_bulk_parser
    participant Pool as ThreadPoolExecutor
    participant TE as text_extraction
    participant LLM as llm_service

    Admin->>FE: Upload N files
    FE->>AR: POST /api/admin/bulk-parse/upload
    AR->>BPS: upload_files()
    alt BULK_PARSER_URL unreachable
        BPS->>LBP: start_local_job()
        LBP->>LBP: spawn daemon thread
        LBP-->>AR: {job_id, status: started}
        AR-->>FE: job_id
        loop Poll every 500ms
            FE->>AR: GET /bulk-parse/progress/{job_id}
            AR->>LBP: get_local_progress()
            LBP-->>FE: processed_files, status
        end
        par Per file (max BULK_PARSE_MAX_WORKERS)
            Pool->>TE: extract_text()
            Pool->>LLM: call_llm('resume')
            Pool->>LBP: _flatten_toon() → row
        end
        LBP->>LBP: status=completed, results[]
        FE->>AR: GET /bulk-parse/download/{job_id}
        AR->>LBP: get_local_download() → xlsx bytes
        AR-->>FE: Excel stream
    else External bulk service
        BPS->>BPS: POST external /api/upload
        Note over BPS: Opaque external flow
    end
```

---

## 6. LLM Provider Call (X.AI with Key Rotation)

```mermaid
sequenceDiagram
    autonumber
    participant LLM as call_xai_grok
    participant KM as KeyManager
    participant XAI as api.x.ai

    LLM->>LLM: get_system_prompt(doc_type)
    LLM->>KM: get_key_for_service('parsing')
    loop Until all keys tried
        KM-->>LLM: (slot_id, secret)
        LLM->>XAI: POST chat/completions
        alt 200 OK
            XAI-->>LLM: content
            LLM->>KM: report_result(success)
            LLM->>LLM: parse_llm_response()
        else 429 / 5xx / timeout
            LLM->>KM: report_result(fail) → cooldown
            Note over LLM: try next key
        else 4xx (not 429)
            LLM-->>LLM: raise immediately
        end
    end
```

---

## 7. PDF Text Extraction with Fallback

```mermaid
sequenceDiagram
    autonumber
    participant TE as extract_text
    participant PDF as extract_text_from_pdf
    participant PAPI as Parsing API

    TE->>PDF: PyPDF2 extract
    alt >= 30 chars
        PDF-->>TE: text
    else Insufficient
        PDF-->>TE: ValueError
        TE->>PAPI: POST /api/v1/parse/resume
        alt PAPI OK
            PAPI-->>TE: raw_text from JSON
        else PAPI fail
            TE-->>TE: ValueError combined error
        end
    end
```

---

## Timing & Async Notes

| Flow | Blocking? | Typical bottleneck |
|------|-----------|-------------------|
| Single parse | Fully synchronous in request | LLM call (45s timeout) |
| Apply | Returns 201 immediately | ATS in `threading.Thread` daemon |
| Bulk local | Upload returns immediately | Background thread + N × LLM |
| Bulk progress | Client polls 500ms | — |
