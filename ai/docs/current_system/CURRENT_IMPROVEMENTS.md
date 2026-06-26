# Potential Improvements — Analysis Only

**Status:** Recommendations derived from code review  
**Scope:** Documentation only — **not implemented**

These items are ordered by relevance to training and deploying an Ollama replacement model.

---

## A. Model Integration & Prompts

1. **Externalize prompts** — Load `get_system_prompt()` from versioned YAML (`ai/prompts/`) with hash recorded in `parsed_*.model_version`.

2. **Unify output contract** — Choose JSON Schema or strict TOON; reject dual-format in `parse_llm_response` for eval consistency.

3. **Add Ollama provider branch** — Extend `call_llm()` with `LLM_PROVIDER=ollama` calling local `/api/chat` with same message structure as Grok.

4. **Structured output for all providers** — Request JSON mode where supported; validate against schema before `validate_toon_format`.

5. **Enrich user message template** — Wrap `raw_text` with `user_template` from YAML: filename, doc_type, language hint.

6. **Record actual model ID** — Store `XAI_MODEL` or Ollama tag in `model_version` for regression analysis.

7. **LLM output retry** — On `toon_loads_flex` failure, single retry with "return valid JSON only" nudge (not implemented today).

---

## B. TOON Schema & Validation

8. **Deep schema validation** — Validate `experience[]` / `education[]` item shapes with pydantic or jsonschema.

9. **Align prompt, validator, and TypeScript** — Single source of truth document; fix JD `company` / `location` inconsistencies.

10. **Non-empty list rules** — Require at least one skill and one experience OR education entry for resume pass.

11. **Email/phone format checks** — Soft warnings in confidence; hard fail only on completely missing keys.

12. **JD mandatory/preferred skills in prompt** — Extract for ATS `mandatory_skills_match_pct` gate.

13. **Normalize on ingest** — Central `normalize_resume_toon()` before store: coerce lists, dates, phone formats.

---

## C. Pipeline Unification

14. **Shared parse core** — Extract `parse_document(file_data, filename, doc_type)` used by single and bulk paths.

15. **Apply bulk validation** — Run `validate_toon_format` and resume post-processing in `local_bulk_parser`.

16. **Remove or wire `call_parsing_api`** — Either delete dead code or route single parse through microservice consistently.

17. **Bulk DB persistence option** — Optional flag to store bulk results in `parsed_resumes` for ATS reuse.

18. **Global content hash cache** — Dedupe parses across uploaders when policy allows (privacy permitting).

---

## D. Text Extraction

19. **OCR fallback** — Tesseract or cloud OCR when PyPDF2 yields &lt;30 chars.

20. **pdfplumber secondary pass** — Try alternate extractor before external API.

21. **True .doc support** — Use `antiword`, `textract`, or LibreOffice conversion for legacy Word.

22. **Extraction quality score** — Pass score to LLM/confidence; reject below threshold with clear error code.

23. **Language detection** — Select prompt locale or post-processing rules.

---

## E. Classification

24. **LLM or lightweight classifier** — Verify doc type before parse; block JD uploaded to resume endpoint.

25. **Use classification score in confidence** — Down-rank mismatched types.

---

## F. Performance & Operations

26. **Async parse jobs** — Return `job_id` for single parse; poll like bulk (reduces timeout UX issues).

27. **Parse queue (Redis/Celery)** — Decouple upload from LLM for scale.

28. **Rate limit bulk workers** — Tie `BULK_PARSE_MAX_WORKERS` to available API keys automatically.

29. **Shared object storage** — S3/Azure for `raw_files` in multi-instance deployments.

30. **Export key manager metrics** — `/health` or `/metrics` with parse latency histograms.

31. **Token usage logging** — Capture prompt/completion tokens per provider for cost tracking.

---

## G. Security & Compliance

32. **Content-type verification** — Magic-byte check beyond extension.

33. **PII redaction in logs** — Structured logging without raw resume text.

34. **Role-based parse endpoints** — Separate candidate vs HR resume upload policies if needed.

35. **Encrypt `full_text` at rest** — If compliance requires.

---

## H. Downstream & Product

36. **Sync parsed TOON to profile tables** — Optional auto-populate `candidate_education` on parse save.

37. **Re-parse on low confidence** — Trigger second pass or human review queue below 0.75.

38. **Wire n8n or remove** — Call `trigger_n8n` from apply or delete dead integration.

39. **ATS feedback loop** — Log which missing skills caused disqualification → training hard negatives.

40. **Search index from TOON** — Index `parsed_resumes.toon` skills for recruiter search (not present today).

---

## I. Ollama Training Specific

41. **Match production prompt exactly** — Fine-tune on `get_system_prompt` + raw text → TOON pairs.

42. **Include post-process in training or remove post-process** — Avoid teaching model patterns that code overwrites (URLs, Indian cities).

43. **Train on validation failures** — Collect 400 responses from `validate_toon_format` for hard example mining.

44. **Benchmark bulk flatten fields** — Ensure model fills columns used in `_flatten_toon` Excel export.

45. **Freeze evaluation set** — Use `ai/datasets/benchmark/` unrelated uploads from production hash samples.

46. **TOON-only training target** — Disable JSON acceptance in training pipeline even if production still accepts JSON during migration.

47. **Quantization regression tests** — Compare q4 vs q8 Ollama models against Grok baseline on same benchmark.

48. **Context length tests** — Validate against `LLM_MAX_INPUT_CHARS` truncation behavior.

---

## J. Documentation & Governance

49. **Link `model_version` to prompt registry entry** — Traceability for audits.

50. **ADR for Ollama cutover** — Define rollback to Grok via `LLM_PROVIDER` toggle (already env-driven).

---

## Prioritized Short List for Ollama Milestone

| Priority | Item | Rationale |
|----------|------|-----------|
| P0 | #3 Ollama provider in `call_llm` | Drop-in replacement hook |
| P0 | #1 Externalize prompts | Train/serve same prompt |
| P0 | #9 Schema alignment | Reduce validation failures |
| P1 | #14 Unified parse core | Bulk/single parity |
| P1 | #8 Deep validation | Catch model regressions |
| P1 | #6 Model version metadata | Compare Grok vs Ollama |
| P2 | #19 OCR fallback | Extraction ceiling independent of model |
| P2 | #26 Async single parse | UX at scale |

---

*None of the above are implemented in this milestone. This document is input for future engineering work only.*
