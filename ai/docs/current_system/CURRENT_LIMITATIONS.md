# Current Architectural Limitations

**Status:** Reverse-engineered analysis — factual observations from code  
**Purpose:** Baseline for Ollama model integration planning

---

## 1. LLM Integration

### Single hardcoded prompt source

- Prompts live as inline strings in `llm_service.get_system_prompt()`.
- `ai/capabilities/*/prompt.md*.yaml.example` is not loaded at runtime.
- No prompt versioning tied to `model_version` stored in DB (`{provider}-v1` only).

### Provider asymmetry

- Primary path (X.AI): no `response_format: json_object`, no content retry on parse failure.
- OpenAI path requests JSON but Grok path accepts ambiguous TOON text.
- Temperature differs: 0.2 (X.AI) vs 0.3 (OpenAI/Anthropic).

### User message is raw text only

- No metadata envelope (filename, locale, page count).
- Truncation appends English suffix that may not match document language.

### No structured output validation at LLM boundary

- `parse_llm_response` only checks for non-empty dict.
- Malformed nested structures pass until `validate_toon_format` (shallow check).

---

## 2. TOON Format

### Dual-format ambiguity

- Models may return TOON lines or JSON; `toon_loads_flex` accepts both.
- Training a single-format Ollama model requires explicit contract decision.

### Schema drift

- TypeScript (`ai/toon/v1/types/toon.ts`) does not match Python validation.
- JD: `company` CRITICAL in prompt but not validated.
- JD: `location` required by validator but not marked CRITICAL in prompt.
- ATS uses `mandatory_skills` / `preferred_skills` not in JD prompt.

### Weak nested validation

- Empty `experience: []` passes validation.
- No shape checks on experience/education objects.
- List fields may be strings instead of arrays depending on LLM output.

### Serialization round-trip loss

- `toon_dumps` skips `None` values; re-parse may omit keys that validation expects to exist.

---

## 3. Parsing Pipeline Consistency

### Three divergent parse paths

| Path | Validation | Post-process | DB |
|------|------------|--------------|-----|
| Single resume | Yes | Yes | Yes |
| Single JD | Yes | No | Yes |
| Bulk local | No | No | No |

Bulk and single parse can produce **different TOON quality** for the same file.

### Dead code path

- `parsing_utils.call_parsing_api()` never invoked by `parsing_routes`.
- Suggests incomplete migration to in-process LLM or abandoned microservice architecture.

### External dependencies not in repo

- `PARSING_API_URL` (port 4000) — PDF fallback only.
- `BULK_PARSER_URL` (port 8001) — opaque behavior when external.

---

## 4. Text Extraction

### No OCR in local path

- Image/scanned PDFs fail unless external Parsing API available.
- 30-character minimum is heuristic; may accept garbage or reject short valid resumes.

### DOC vs DOCX

- `.doc` extension routed to `extract_text_from_docx()` — legacy `.doc` binary format may fail.

### PDF library limitations

- PyPDF2 only; no pdfplumber/tabula despite `ai/docs/DATA_PIPELINE.md` mentioning them for training pipeline.

---

## 5. Classification

### Non-LLM heuristics only

- Keyword counting with threshold ≥2.
- Resume endpoint ignores `unknown` classification.
- JD endpoint skips classification entirely.
- Wrong document type can still be forced through wrong parser.

---

## 6. Caching & Idempotency

### Per-uploader duplicate cache

- Same file uploaded by different users triggers full re-parse (cost duplication).
- Cache hit skips re-validation against updated rules.
- No global content-addressed cache across tenants.

### Raw file dedup vs parse dedup

- `raw_files` deduped by `(hash, uploader_id)`.
- New parse row only skipped via cache join, not automatic on raw_file duplicate alone.

---

## 7. Database & Data Model

### Parsed TOON decoupled from profile

- `mapResumeTOONToForm` fills UI; user must save to `candidate_profiles`.
- `candidate_education`, `candidate_experiences` tables are independent of `parsed_resumes`.

### Optional foreign keys

- `parsed_resumes.candidate_id` and `parsed_jds.job_id` often null.
- Apply flow must fallback-query via `raw_files.uploader_id`.

### No audit trail for bulk

- In-memory job store lost on process restart.
- No record of which model parsed which bulk file.

### `model_version` granularity

- Does not record actual model name (`grok-4-fast-reasoning`).
- Cannot compare parse quality across model upgrades from DB alone.

---

## 8. Performance & Scalability

### Synchronous single parse

- HTTP request blocked for full LLM latency (up to 45s default).
- No job queue for single uploads.

### Bulk parallelism unbounded risk

- `BULK_PARSE_MAX_WORKERS` up to 24; can exhaust API rate limits.
- All workers share same key rotation pool.

### In-memory bulk state

- Not horizontally scalable across multiple Flask workers/instances.

### File storage local disk

- `file://` URLs not suitable for multi-instance cloud without shared storage.

---

## 9. Security

### Authentication gaps

- Parse endpoints require JWT but no per-role separation on resume endpoint (candidates and HR both use `/parse/resume` with different uploader resolution).
- Bulk endpoints correctly gated with `@require_recruiter`.

### File content trust

- No malware scanning.
- `secure_filename` only; no content-type magic-byte verification.

### API keys in environment

- Standard pattern but no runtime key health dashboard exposed to ops (metrics exist in `llm_key_manager` but not HTTP endpoint in parsing routes).

### PII in logs

- Print statements may include filenames; LLM errors may leak to client as 500 message.

---

## 10. Observability

### Limited metrics

- Key manager has internal metrics; not exported via `/health`.
- No parse latency, token usage, or extraction failure counters in application code.
- No distributed tracing across LLM → validate → store.

### Error granularity

- Generic `"LLM parsing failed: {str(e)}"` to client.
- No error codes for training feedback loops.

---

## 11. Downstream Consumer Limitations

### ATS depends on parse completeness

- `_internal_match` uses `skills`, `experience`, `education`, `person.location`.
- Missing fields silently reduce scores (caps at 50% without evidence).
- No feedback loop to re-parse low-confidence resumes.

### Synthetic JD TOON quality

- `_jd_toon_from_job_row` uses regex on markdown — fragile vs LLM-parsed JD.

### n8n integration dormant

- `trigger_n8n()` defined but not called in `apply_job` current code path.

---

## 12. Training Pipeline Alignment

### AI workspace vs production divergence

- `ai/dataset/` pipeline (extract → clean → normalize → validate) is **not** the production path.
- Production: extract → LLM → validate (shallow) → store.
- Risk: training data distribution differs from production behavior.

---

## Summary Matrix

| Area | Severity | Impact on Ollama Migration |
|------|----------|---------------------------|
| Shallow TOON validation | High | Model must be highly reliable or validation must be extended |
| Bulk path skips validation | High | Training eval must cover bulk use case separately |
| Prompt not externalized | Medium | Need injection point for Ollama prompts |
| `call_llm` as sole hook | Low | Clean swap point if interface preserved |
| No OCR | Medium | Model cannot fix extraction failures |
| Schema drift TS/Python/prompt | Medium | Single schema contract needed |
| In-memory bulk jobs | Medium | Operational concern, not model concern |
