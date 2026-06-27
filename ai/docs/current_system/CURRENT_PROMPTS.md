# Current Prompts — Technical Specification

**Status:** Reverse-engineered from production code  
**Runtime source of truth:** `backend/llm_service.py` → `get_system_prompt()`  
**Note:** `ai/capabilities/*/prompt.md*.yaml.example` mirrors prompts for training/docs but is **not loaded at runtime**.

---

## Prompt Inventory

| ID | Doc Type | Location | Invoked By |
|----|----------|----------|------------|
| `resume_system` | Resume | `llm_service.get_system_prompt('resume')` | `call_xai_grok`, `call_openai`, `call_anthropic` |
| `jd_system` | Job Description | `llm_service.get_system_prompt('jd')` | Same |
| `resume_user` | Resume | Raw extracted text (implicit) | `call_llm(prompt=raw_text, ...)` |
| `jd_user` | JD | Raw extracted text (implicit) | Same |

There are **no other production parsing prompts** in the repository. Classification uses keyword heuristics, not LLM prompts.

---

## Prompt 1: Resume System Prompt

### Source

```220:250:backend/llm_service.py
def get_system_prompt(doc_type: str) -> str:
    """Get system prompt for LLM. Required output format is TOON (Token-Oriented Object Notation)."""
    if doc_type == 'resume':
        return """You are an expert resume parser. Extract ALL information from the resume including EVERY URL. Return ONLY valid TOON (Token-Oriented Object Notation): one key-value per line, key: value, nested keys with dots, scalar lists with pipe. Example:
...
```

### Purpose

Instruct the LLM to extract a complete resume into **TOON** format with emphasis on URLs and location.

### Variables

| Variable | Value | Notes |
|----------|-------|-------|
| None in template | — | Prompt is a static string |
| User content | `{raw_text}` | Passed as separate `user` message, not interpolated into system prompt |

### LLM Parameters (by provider)

| Provider | Temperature | Max Tokens | Response Format |
|----------|-------------|------------|-----------------|
| X.AI Grok | 0.2 | 2048 | Free text (TOON or JSON) |
| OpenAI | 0.3 | 2000 | `json_object` |
| Anthropic | 0.3 | 2000 | Free text |

### Expected Output

- Primary: TOON text block (one `key: value` per line)
- Alternate: Valid JSON object (accepted via `toon_loads_flex`)

### Expected Structure (from prompt example)

```
type: resume
person.name: Full Name
person.email: email@example.com
person.phone: +1234567890
person.location: City, State/Country
person.linkedin: https://linkedin.com/in/username
person.github: 
person.portfolio: 
person.website: 
person.twitter: 
person.otherUrls[0]:
summary: Professional summary
skills: skill1|skill2
experience.0.title: Job Title
experience.0.company: Company Name
experience.0.from: 2020-01
experience.0.to: 2023-12
experience.0.years: 3.9
education.0.degree: Bachelor of Science
education.0.field: Computer Science
education.0.institution: University Name
education.0.year: 2020
certifications: cert1|cert2
total_experience_years: 3.9
```

### Mapping to Validated Schema

Post-LLM validation (`validate_toon_format`) additionally requires:

- `person.name`, `person.email`, `person.phone` (keys must exist; values may be empty strings)
- `skills`, `experience`, `education` top-level keys

Fields in prompt but **not validated**: `summary`, `certifications`, `total_experience_years`, URL fields.

### Weaknesses

1. **No JSON schema enforcement** for Grok (primary provider) — relies on post-hoc `toon_loads_flex`.
2. **Ambiguous list encoding** — pipe lists vs indexed objects (`experience.0.*`); parser must handle both.
3. **Date format unspecified** — examples use `YYYY-MM` but validation does not enforce format.
4. **Empty URL fields** — prompt shows blank values; model may omit keys, causing validation gaps for optional URLs only.
5. **No instruction for certifications as objects** — prompt shows scalar pipe list; frontend accepts both strings and objects.
6. **No languages field** in prompt despite TypeScript schema (`ai/toon/v1/types/toon.ts`).
7. **Truncation message** — if `LLM_MAX_INPUT_CHARS` set, appended text may confuse smaller models.
8. **India-centric location fallback** exists in route post-processing, not in prompt.

### Possible Improvements (documentation only)

- Add explicit JSON schema or structured output mode for Grok.
- Specify canonical date formats and `Present` for current roles.
- Distinguish mandatory vs optional fields in prompt to align with `validate_toon_format`.
- Include `languages`, `experience.description`, education `gpa`.
- Version prompts externally (`ai/capabilities/*/prompt.mdresume_parser.yaml`) and load at runtime.
- Add few-shot examples for edge cases (multi-column resumes, tables).

---

## Prompt 2: Job Description System Prompt

### Source

```252:267:backend/llm_service.py
    else:  # jd
        return """You are an expert job description parser. Extract information and return ONLY valid TOON ...
```

### Purpose

Extract structured job posting fields into TOON, with emphasis on **company name**.

### Variables

Same as resume: static system prompt; user message = raw JD text.

### Expected Structure (from prompt example)

```
type: job_description
title: Job Title
company: Company Name
location: City, Country
salary_range: 50000-80000
min_experience_years: 2
max_experience_years: 5
skills: skill1|skill2
responsibilities: resp1|resp2
qualifications: qual1|qual2
keywords: keyword1|keyword2
```

### Validated vs Prompted

| Field | In Prompt | Required by `validate_toon_format` | Required by `calculate_confidence` |
|-------|-----------|-----------------------------------|-----------------------------------|
| `type` | Yes | Yes (`job_description`) | — |
| `title` | Yes | Yes | Yes (70% weight) |
| `company` | Yes (CRITICAL) | **No** | Optional (30% weight) |
| `location` | Yes | **Yes** | Optional |
| `skills` | Yes | Yes | Yes |
| `responsibilities` | Yes | Yes | Yes |
| `qualifications` | Yes | No | Optional |
| `keywords` | Yes | No | No |
| `salary_range` | Yes | No | No |
| `min/max_experience_years` | Yes | No | No |
| `employment_type` | In TS types only | No | No |
| `mandatory_skills` / `preferred_skills` | No | No | Used by ATS if present |

### Weaknesses

1. **Company marked CRITICAL but not validated** — parse can pass without company.
2. **Location required by validator** but only listed in example, not CRITICAL line — common failure mode.
3. **No mandatory/preferred skill split** — ATS (`ats_service`) supports `mandatory_skills` / `preferred_skills` but prompt does not extract them.
4. **employment_type** missing from prompt despite frontend types.
5. **keywords** prompted but never validated or used in confidence.
6. **Same TOON/JSON dual-format ambiguity** as resume.

### Possible Improvements

- Align CRITICAL line with `validate_toon_format` requirements.
- Extract `mandatory_skills` and `preferred_skills` for ATS gating.
- Add `employment_type`, `remote/hybrid` flags.
- Structured output / schema validation at LLM layer.

---

## Prompt 3: User Message (Implicit)

### Construction

```python
# llm_service.call_xai_grok
payload = {
    "messages": [
        {"role": "system", "content": get_system_prompt(doc_type)},
        {"role": "user", "content": prompt},  # prompt == raw_text from extract_text()
    ],
}
```

### Purpose

Provide full document text to the model.

### Variables

| Name | Source |
|------|--------|
| `prompt` / `raw_text` | `text_extraction.extract_text(file_data, filename)` |
| Truncation suffix | `"\n\n[Document truncated for length. Extract from above.]"` if `LLM_MAX_INPUT_CHARS` > 0 |

### Expected Output

None directly — model responds with TOON/JSON in assistant message.

### Weaknesses

- No document metadata (filename, language, page count).
- No explicit instruction boundary between system and user roles beyond provider defaults.
- `ai/capabilities/*/prompt.mdresume_parser.yaml.example` defines `user_template: "{raw_text}"` but backend does not use this template file.

---

## Prompt 4: Training Mirror (`ai/capabilities/*/prompt.md*.yaml.example`)

### Files

- `ai/capabilities/*/prompt.mdresume_parser.yaml.example` — version `1.0.0`, documents `required_output_fields`
- `ai/capabilities/*/prompt.mdjd_parser.yaml.example` — version `1.0.0`

### Purpose

Future versioning / fine-tuning dataset contract; aligned with `get_system_prompt` content.

### Discrepancies vs Runtime

| Item | YAML Example | Runtime |
|------|--------------|---------|
| JD `required_output_fields` | includes `company` | Not enforced in `validate_toon_format` |
| Resume `required_output_fields` | `person.name`, `skills`, `experience` | Also requires `person.email`, `person.phone`, `education` |
| Parameters | `temperature: 0.2` | OpenAI uses 0.3; X.AI uses 0.2 |

---

## Response Parsing (Post-Prompt)

Not a prompt, but completes the contract:

```270:275:backend/llm_service.py
def parse_llm_response(content: str) -> Dict[str, Any]:
    parsed = toon_loads_flex(content)
    if not parsed:
        raise ValueError("Failed to parse LLM response as TOON or JSON")
    return parsed
```

**Failure handling:** Raises `ValueError` → HTTP 500 `"LLM parsing failed"` from route.

**No retry** on malformed LLM output for X.AI (only key rotation on HTTP errors).

---

## Classification (Non-LLM)

`classify_document(text)` uses fixed keyword lists — **not a prompt**. See `CURRENT_PARSING_PIPELINE.md`.
