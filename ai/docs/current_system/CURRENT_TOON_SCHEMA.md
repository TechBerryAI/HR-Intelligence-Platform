# Current TOON Schema — Technical Specification

**Status:** Reverse-engineered from production code  
**Canonical implementation:** `backend/toon.py` (serialize/parse)  
**Type definitions:** `shared/types/toon.ts`, `shared/types/toon.d.ts`  
**Validation:** `backend/parsing_utils.validate_toon_format()`

---

## What Is TOON?

**TOON** (Token-Oriented Object Notation) is the HRMS exclusive structured format for resumes, job descriptions, and ATS results.

### Wire Format Rules (`toon.py`)

| Rule | Description |
|------|-------------|
| Line-oriented | One entry per line: `key.path: value` |
| Nesting | Dot-separated paths: `person.email` |
| Scalar lists | Pipe-delimited: `skills: Python\|React\|AWS` |
| Object arrays | Indexed paths: `experience.0.title: Engineer` |
| Empty arrays | `key[0]:` with empty value |
| Quoting | Strings with `\|`, newlines, or edge cases quoted |
| Null | Omitted on serialize; `null` token on parse |
| Legacy JSON | `toon_loads_flex()` accepts `{...}` JSON at boundaries |

### Storage Format

Database columns `parsed_resumes.toon` and `parsed_jds.toon` store **`toon_dumps()` text**, not JSON.

---

## Resume TOON Schema

### Root Object

| Field | Type | Required (validation) | Required (confidence) | Default | Notes |
|-------|------|----------------------|----------------------|---------|-------|
| `type` | string | **Yes** = `"resume"` | — | — | Mismatch → validation fail |
| `person` | object | **Yes** (key exists) | Yes | — | See below |
| `skills` | string[] | **Yes** (key exists) | Yes | `[]` if missing in LLM | May be pipe-parsed string |
| `experience` | object[] | **Yes** (key exists) | Yes | — | May be empty list |
| `education` | object[] | **Yes** (key exists) | Yes | — | May be empty list |
| `summary` | string | No | Optional (+15% conf) | `""` | |
| `certifications` | string[] or object[] | No | Optional (+15% conf) | — | Frontend normalizes both |
| `languages` | string[] | No | No | — | In TS types only |
| `total_experience_years` | number | No | No | — | Used by ATS experience scoring |

### `person` Object

| Field | Type | Required (validation) | Optional URLs |
|-------|------|----------------------|---------------|
| `name` | string | **Key required** | |
| `email` | string | **Key required** | |
| `phone` | string | **Key required** | |
| `location` | string | No | Post-processed from raw text if missing |
| `linkedin` | string | No | Must be string or null if present |
| `github` | string | No | Same |
| `portfolio` | string | No | Same |
| `website` | string | No | Same |
| `twitter` | string | No | Same |
| `otherUrls` | string[] | No | Must be array or null if present |

**Normalization (frontend `mapResumeTOONToForm`):**

- `person.current_location`, `person.city`, `person.address` → `currentLocation`
- `person.preferred_location` → `preferredLocation`
- Experience `[0].location` fallback for location

### `experience[]` Items

| Field | Type | Prompt Example | Frontend Maps |
|-------|------|----------------|---------------|
| `title` | string | Yes | `role` |
| `company` | string | Yes | `company` |
| `from` | string | `2020-01` | `startMonth` (normalized to YYYY-MM) |
| `to` | string | `2023-12` or `Present` | `endMonth`, `isCurrent` |
| `years` | number | `3.9` | Not mapped to form |
| `description` | string | No | In TS types |
| `role` | string | Alias | Accepted as title |
| `start` / `end` / `start_date` / `end_date` | string | Aliases | Date normalization |

### `education[]` Items

| Field | Type | Prompt Example | Frontend Maps |
|-------|------|----------------|---------------|
| `degree` | string | Yes | `degree` |
| `field` | string | Yes | Fallback for `institution` |
| `institution` | string | Yes | `institution` |
| `year` | string | Yes | `endMonth` |
| `gpa` | string | No | `cgpa` |
| `start` / `from` | string | Aliases | `startMonth` |

### `certifications[]` Items

- **LLM prompt:** pipe-delimited strings (`cert1|cert2`)
- **Frontend:** accepts `string` or `{name, issuer, validTill, url, status}`

---

## Job Description TOON Schema

### Root Object

| Field | Type | Required (validation) | Confidence Weight | ATS Usage |
|-------|------|----------------------|-------------------|-----------|
| `type` | string | **Yes** = `"job_description"` | — | — |
| `title` | string | **Yes** | 23.3% × 3 | Experience role match |
| `location` | string | **Yes** | 10% optional | Location score 5% |
| `skills` | string[] | **Yes** | 23.3% | Legacy skills list → mandatory if no split |
| `responsibilities` | string[] | **Yes** | 23.3% | Fallback text in `_jd_toon_from_job_row` |
| `company` | string | No | 10% optional | Display |
| `qualifications` | string[] | No | 10% optional | Education scoring |
| `keywords` | string[] | No | No | Not used downstream |
| `salary_range` | string | No | No | Mapped to job `salary` in UI |
| `min_experience_years` | number | No | No | ATS experience |
| `max_experience_years` | number | No | No | ATS experience |
| `employment_type` | string | No | No | TS types only |
| `mandatory_skills` | string[] | No | No | ATS gate (60% min) |
| `preferred_skills` | string[] | No | No | ATS weighted 20% of skills |

### Synthetic JD TOON (`applications._jd_toon_from_job_row`)

When no `parsed_jds` row exists, a minimal TOON is built from `jobs` table:

- Parses `**Required Skills:**`, `**Responsibilities:**`, `**Qualifications:**` from markdown description
- Populates `mandatory_skills`, `preferred_skills`, `skills`, `responsibilities`, `qualifications`
- Extracts experience years from `jobs.experience` string via regex

---

## ATS Result TOON (`ATSResultTOON`)

Not produced by resume/JD parsing, but part of TOON ecosystem:

| Field | Type | Storage |
|-------|------|---------|
| `json_output` | object | `applications.ats_analysis` (serialized via `toon_dumps`) |
| `json_output.final_score` | number | → `applications.match_score` |
| `json_output.decision` | string | Shortlist logic |
| `json_output.verdict` | string | UI display |
| `json_output.evaluation_report` | object | Recruiter report |
| `toon_output` | string | Reasoning text |

---

## Serialization Examples

### Resume → TOON Text

Input dict:
```python
{
  "type": "resume",
  "person": {"name": "Jane", "email": "j@x.com", "phone": "+1"},
  "skills": ["Python", "SQL"],
  "experience": [{"title": "Dev", "company": "Acme", "from": "2020-01", "to": "2023-12"}],
  "education": [{"degree": "BS", "field": "CS", "institution": "MIT", "year": "2020"}]
}
```

Output (conceptual):
```
type: resume
person.name: Jane
person.email: j@x.com
person.phone: +1
skills: Python|SQL
experience.0.title: Dev
experience.0.company: Acme
experience.0.from: 2020-01
experience.0.to: 2023-12
education.0.degree: BS
...
```

### Parse Ambiguity: Pipe Lists

If value contains `|` and is not quoted, `toon_loads` splits into **array of strings**.

---

## Validation Rules Summary

See `CURRENT_VALIDATION.md` for full flow. Schema-level rules:

1. Root must be `dict`
2. `type` must match document class
3. Resume: keys `person`, `skills`, `experience`, `education` must exist
4. Resume: `person.name`, `person.email`, `person.phone` keys must exist
5. JD: keys `title`, `location`, `skills`, `responsibilities` must exist
6. **No validation** of non-empty values for list fields
7. **No validation** of nested object shapes inside `experience` / `education`

---

## Relationships

```
raw_files (1) ──→ (N) parsed_resumes
raw_files (1) ──→ (N) parsed_jds

parsed_resumes.candidate_id ──→ candidate_signup.cid (optional)
parsed_jds.job_id ──→ jobs.jdid (optional)

applications (apply) ──reads──→ latest parsed_resumes + parsed_jds (no FK)
```

---

## TypeScript vs Runtime Gaps

| Field | In `toon.ts` | Enforced at Runtime |
|-------|--------------|---------------------|
| `employment_type` (JD) | Required in interface | Not validated |
| `summary` (resume) | Required in interface | Optional |
| `languages` | Optional | Not in LLM prompt |
| `mandatory_skills` (JD) | Not in interface | Used by ATS |

---

## Bulk Excel Flattening (Non-TOON Export)

`local_bulk_parser._flatten_toon()` maps subset to columns:

`Filename`, `Name`, `Email`, `Phone`, `LinkedIn`, `GitHub`, `Summary`, `Skills`, `Experience`, `Education`, `Certifications`, `Total Experience Years`

Truncation: summary 500 chars, skills 30 items, experience 10 entries, etc.
