# Current Call Graph — Function-Level Trace

**Status:** Reverse-engineered from production code  
**Convention:** `module.function()` → callees

---

## 1. Resume Parse Call Graph

```
parse_resume_upload()                          [parsing_routes.py]
├── authenticate_token                         [utils.py] (decorator)
├── allowed_file()
├── get_mime_type()
├── secure_filename()                          [werkzeug]
├── compute_file_hash()                        [parsing_utils]
├── get_cached_parsing_result()                [parsing_utils]
│   ├── db_get()
│   └── toon_loads_flex()                      [toon]
├── store_raw_file()                           [parsing_utils]  (cache miss)
│   ├── compute_file_hash()
│   ├── db_get()
│   ├── save_file_to_storage()
│   └── db_run()
├── extract_text()                             [text_extraction]
│   ├── extract_text_from_pdf()                [if .pdf]
│   │   └── PyPDF2.PdfReader
│   └── extract_text_from_docx()               [if .doc/.docx]
│       └── docx.Document
│   └── [PDF fallback] extract_text_from_pdf_via_api()
│       └── requests.post(PARSING_API_URL/...)
├── classify_document()                        [llm_service]
├── call_llm(raw_text, 'resume')               [llm_service]
│   ├── [optional] prompt truncation LLM_MAX_INPUT_CHARS
│   └── call_xai_grok() | call_openai() | call_anthropic()
│       ├── get_system_prompt('resume')
│       ├── get_key_for_service()              [llm_key_manager] (xai only)
│       ├── requests.post(provider URL)
│       ├── report_result()                    [llm_key_manager] (xai only)
│       └── parse_llm_response()
│           └── toon_loads_flex()
│               ├── json.loads()               [if JSON]
│               └── toon_loads()
├── [post-process] re.findall URL patterns     [inline parsing_routes]
├── validate_toon_format(toon, 'resume')     [parsing_utils]
├── calculate_confidence(toon, 'resume')     [parsing_routes]
├── store_parsed_resume()                      [parsing_utils]
│   ├── toon_dumps()                           [toon]
│   └── db_run()
└── jsonify(response)
```

---

## 2. JD Parse Call Graph

```
parse_jd_upload()                              [parsing_routes.py]
├── authenticate_token
├── allowed_file(), get_mime_type(), secure_filename
├── compute_file_hash()
├── get_cached_parsing_result(..., 'job_description')
├── store_raw_file()
├── extract_text()
├── call_llm(raw_text, 'jd')
│   └── get_system_prompt('jd')
│   └── [same provider chain as resume]
├── validate_toon_format(toon, 'job_description')
├── calculate_confidence(toon, 'jd')
├── store_parsed_jd()
│   ├── toon_dumps()
│   └── db_run()
└── jsonify(response)
```

**Omitted vs resume:** `classify_document`, URL/location post-processing.

---

## 3. TOON Serialization Call Graph

```
toon_dumps(obj)                                [toon.py]
├── walk(prefix, o)                            [nested]
│   ├── enc_val()                              [scalar encoding]
│   └── recurse dict / list / indexed objects

toon_loads(text)                               [toon.py]
├── strip markdown fences
├── per line: path, value
├── _parse_val()
├── pipe → list split
└── _set_by_path()

toon_loads_flex(text)                          [toon.py]
├── if starts with '{': json.loads()
└── else toon_loads()
```

---

## 4. LLM Service Call Graph

```
call_llm(prompt, doc_type)
├── [branch] LLM_PROVIDER
│   ├── 'xai' → call_xai_grok(prompt, doc_type, 'parsing')
│   ├── 'openai' → call_openai()
│   └── 'anthropic' → call_anthropic()
│
call_xai_grok()
├── KeyManager.get_instance()._registry.count
├── loop keys_tried < max_keys_to_try:
│   ├── get_key_for_service('parsing')
│   ├── _get_session().post(api.x.ai)
│   ├── report_result(slot_id, ok, status, latency)
│   └── parse_llm_response(content)
│
call_openai() / call_anthropic()
├── get_system_prompt(doc_type)
├── requests.post (retry loop max 3)
└── parse_llm_response()
```

---

## 5. Bulk Parse Call Graph

```
bulk_parse_upload()                            [admin/routes.py]
├── authenticate_token, require_hr
├── secure_filename per file
└── bulk_upload(files_list)                    [bulk_parsing_service]
    ├── [try] requests.post(BULK_PARSER_URL/api/upload)
    └── [fallback] start_local_job()           [local_bulk_parser]
        ├── threading.Thread(_worker)
        └── return job_id

_worker(job_id, files_list)
└── ThreadPoolExecutor
    └── _process_one_file((filename, data))
        ├── extract_text()
        ├── call_llm(raw_text, 'resume')
        └── _flatten_toon(toon, filename)

bulk_parse_progress(job_id)
└── get_local_progress() | requests.get(external)

bulk_parse_download(job_id)
└── get_local_download()
    └── _build_excel_bytes() → openpyxl
    | requests.get(external stream)
```

---

## 6. Apply + ATS Consumer Call Graph

```
apply_job()                                    [applications.py]
├── authenticate_token, require_candidate
├── db_get(jobs), db_get(applications), db_get(candidate_profiles)
├── db_get(parsed_resumes) + fallback join raw_files
├── db_get(parsed_jds) OR _jd_toon_from_job_row(job)
├── toon_loads_flex(resume toon)
├── db_run(INSERT applications)
└── threading.Thread(_run_ats_and_update_application)

_run_ats_and_update_application()
├── match_candidate_to_job()                   [ats_service]
│   ├── [if ATS_API_URL] requests.post(/api/match)
│   └── [else] _internal_match()
│       ├── _get_jd_skill_lists()
│       ├── _compute_skills_scores()
│       ├── _compute_experience_score()
│       ├── _compute_education_score()
│       ├── _compute_location_score()
│       ├── _verdict_from_score()
│       └── _build_recruiter_report()
├── toon_dumps(ats_result)
└── db_run(UPDATE applications)
```

---

## 7. Frontend Call Graph

```
ResumeUploadWithParsing.processFile()
├── tokenService.getToken()
├── validateFileForParsing()                   [parsingApi.js]
├── onFileSelect(file)                         [parent callback]
├── uploadAndParseResume(file)
│   └── fetch(POST /api/parse/resume)
├── mapResumeTOONToForm(result.toon)
└── onAutofill({...formData, _parsedId, ...})

JDUploadWithParsing.processFile()
├── validateFileForParsing()
├── uploadAndParseJD(file, jobId)
├── mapJDTOONToForm(result.toon)
└── onAutofill()

BulkResumeParser.startUpload()
├── uploadBulkResumes(files)                   [bulkParsingService]
│   └── apiRequest(POST /api/admin/bulk-parse/upload)
├── poll getBulkProgress(jobId)
└── downloadBulkResult(jobId)
```

---

## 8. Retrieval Call Graph

```
get_parsed_resume(parsed_id)
├── db_get(SELECT ... FROM parsed_resumes)
└── toon_loads_flex(result['toon'])

get_parsed_jd(parsed_id)
├── db_get(SELECT ... FROM parsed_jds)
└── toon_loads_flex(result['toon'])
```

---

## 9. Unused / Latent Functions

| Function | Module | Called By |
|----------|--------|-----------|
| `call_parsing_api()` | parsing_utils | **Nothing in repo** |
| `trigger_n8n()` | applications | **Not called from apply_job** (defined, optional integration) |

---

## 10. Call Graph Summary Table

| Entry Point | Depth | Leaf Operations |
|-------------|-------|-----------------|
| `POST /api/parse/resume` | ~4 levels | Grok API, PostgreSQL, disk I/O |
| `POST /api/parse/jd` | ~4 levels | Same |
| `POST /api/admin/bulk-parse/upload` | ~5 levels | N × Grok, openpyxl |
| `POST /api/applications` | ~3 levels | ATS math or external API |
| `GET /api/parsed/resume/:id` | 2 levels | DB read, toon parse |

---

## Critical Path for Ollama Replacement

Functions that must be replicated or hooked for a local model:

1. **`call_llm(prompt, doc_type)`** — single integration point for all parse modes
2. **`get_system_prompt(doc_type)`** — prompt source
3. **`parse_llm_response(content)`** — output normalization
4. **`validate_toon_format()`** — downstream contract
5. **`toon_dumps` / `toon_loads_flex`** — storage round-trip

Bulk path additionally calls `call_llm` directly without validation wrapper.
