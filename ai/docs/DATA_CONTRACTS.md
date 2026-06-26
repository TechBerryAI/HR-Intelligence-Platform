# Data Contracts

Conceptual schema definitions for the HRMS AI platform. These contracts exist **before** JSON Schema implementation (M2) and define what the platform agrees on across preprocessing, training, evaluation, and HRMS integration.

**Authority chain:** Data Contract → Normalized JSON → JSONL training record → TOON (HRMS production format)

---

## Contract layers

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Domain Contracts (this document)                      │
│  Resume, JD, Candidate, Skill, Experience, etc.                 │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: Normalized Record (datasets/normalized/)              │
│  Domain contracts + provenance + artifact metadata              │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: Training Record (datasets/jsonl/)                     │
│  instruction + input + output (TOON serialization)              │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: TOON (HRMS production — backend/toon.py)            │
│  Serialized format consumed by parsing API and ATS pipeline     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Resume

**Purpose:** Canonical representation of a candidate's resume after parsing.

### Responsibilities

- Identity the candidate (`person`)
- Capture career narrative (`summary`, `experience`, `education`)
- List capabilities (`skills`, `certifications`, `languages`)
- Support ATS matching and ranking downstream

### Core fields (conceptual)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `type` | literal `resume` | Yes | Discriminator |
| `person` | Person | Yes | See Person contract |
| `summary` | string | No | Professional summary |
| `skills` | Skill[] | Yes | May be raw strings initially |
| `experience` | Experience[] | Yes | Employment history |
| `education` | Education[] | No | |
| `projects` | Project[] | No | |
| `certifications` | Certification[] | No | |
| `languages` | Language[] | No | |
| `total_experience_years` | number | No | Derived or explicit |

### Evolution to TOON

Resume contract maps 1:1 to HRMS Resume TOON. `validate_toon_format('resume')` in `backend/parsing_utils.py` enforces production subset.

---

## 2. Job Description (JD)

**Purpose:** Structured job posting for matching, ranking, and interview generation.

### Responsibilities

- Define role requirements
- Separate mandatory vs preferred skills (future normalization)
- Feed ATS weighted matching in `ats_service.py`

### Core fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `type` | literal `job_description` | Yes | |
| `title` | string | Yes | |
| `company` | string | Yes | |
| `location` | string | No | |
| `skills` | Skill[] | Yes | Legacy: all skills |
| `mandatory_skills` | Skill[] | No | ATS gate (60% min) |
| `preferred_skills` | Skill[] | No | ATS preferred weight |
| `qualifications` | string[] | No | |
| `responsibilities` | string[] | No | |
| `min_experience_years` | number | No | |
| `max_experience_years` | number | No | |
| `salary_range` | string | No | Future: Salary Intelligence |
| `keywords` | string[] | No | Search indexing |

### Evolution to TOON

JD contract maps to HRMS JD TOON. ATS reads `skills`, `mandatory_skills`, `preferred_skills`, experience years, `location`.

---

## 3. Candidate Profile

**Purpose:** Platform-level view of a candidate beyond a single resume parse. Combines resume TOON with HRMS portal data (future).

### Responsibilities

- Link resume artifact to `candidate_id`
- Hold preferences (location, salary expectations)
- Aggregate multiple resume versions over time

### Core fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `candidate_id` | UUID | Yes | HRMS candidate PK |
| `primary_resume` | Resume ref | No | Latest parsed resume |
| `resume_history` | Resume ref[] | No | Versioned parses |
| `preferences` | object | No | Location, remote, salary |
| `application_history` | ref[] | No | Future: ranking features |

### Relationship to Resume

Candidate Profile **references** Resume contract; does not duplicate fields. Populated in M9+ from HRMS read-only export.

---

## 4. Person

**Purpose:** Contact and identity block within Resume.

### Fields

| Field | Type | Required |
|-------|------|----------|
| `name` | string | Yes |
| `email` | string | Yes |
| `phone` | string | No |
| `location` | string | No |
| `linkedin` | URL string | No |
| `github` | URL string | No |
| `portfolio` | URL string | No |
| `website` | URL string | No |
| `twitter` | URL string | No |
| `otherUrls` | URL[] | No |

**HRMS alignment:** Post-processing in `parsing_routes.py` extracts URLs and location from raw text if LLM misses them.

---

## 5. Skills

**Purpose:** Capability representation for matching, normalization, and search.

### Stages of skill data

| Stage | Form | Owner |
|-------|------|-------|
| Raw extraction | `string` or `string[]` on Resume/JD | Parsing |
| Normalized | `{ name, canonical_id?, confidence }` | Skill normalization (M10) |
| Ontology-linked | `{ canonical_id, category, synonyms }` | Platform skill registry (future) |

### Responsibilities

- Support fuzzy matching in ATS (`_skill_match` in `ats_service.py`)
- Enable skill normalization without re-parsing resume
- Feed AI Search indexing

### Contract (normalized form — future)

| Field | Type | Required |
|-------|------|----------|
| `name` | string | Yes |
| `canonical_name` | string | No |
| `category` | enum | No | e.g. `language`, `framework`, `tool` |
| `years_experience` | number | No |
| `proficiency` | enum | No | `beginner`, `intermediate`, `expert` |

---

## 6. Education

**Purpose:** Academic credentials on a resume.

### Fields

| Field | Type | Required |
|-------|------|----------|
| `degree` | string | No |
| `field` | string | No |
| `institution` | string | No |
| `year` | string/number | No |
| `from` | YYYY-MM | No |
| `to` | YYYY-MM | No |
| `gpa` | string | No |

**ATS use:** `_compute_education_score` compares JD `qualifications` against candidate education.

---

## 7. Experience (Employment History)

**Purpose:** Work history entries — primary signal for experience scoring.

### Fields

| Field | Type | Required |
|-------|------|----------|
| `title` | string | No |
| `company` | string | No |
| `from` | YYYY-MM | No |
| `to` | YYYY-MM or `present` | No |
| `years` | number | No |
| `description` | string | No |
| `skills_used` | Skill[] | No | Future extraction |
| `location` | string | No |

**ATS use:** `_compute_experience_score` compares against JD title and `min_experience_years`.

**Note:** Experience is the employment history contract. "Employment History" is the collection `experience[]` on Resume — not a separate top-level contract.

---

## 8. Projects

**Purpose:** Portfolio and side projects not captured as formal employment.

### Fields

| Field | Type | Required |
|-------|------|----------|
| `name` | string | No |
| `description` | string | No |
| `url` | string | No |
| `technologies` | Skill[] | No |
| `from` | YYYY-MM | No |
| `to` | YYYY-MM | No |

**Future use:** Interview question generation, skill extraction enrichment.

---

## 9. Certifications

**Purpose:** Professional certifications and licenses.

### Fields

| Field | Type | Required |
|-------|------|----------|
| `name` | string | Yes |
| `issuer` | string | No |
| `year` | string/number | No |
| `expiry` | YYYY-MM | No |
| `credential_id` | string | No |

**ATS use:** Part of education/certifications score component (10% weight).

---

## 10. Languages

**Purpose:** Spoken/written language proficiency.

### Fields

| Field | Type | Required |
|-------|------|----------|
| `language` | string | Yes |
| `proficiency` | enum | No | `native`, `fluent`, `professional`, `basic` |

---

## Contract evolution path

| Milestone | Deliverable |
|-----------|-------------|
| M2 | This document finalized; field ownership agreed |
| M3 | JSON Schema files in `governance/schemas/` (future) |
| M4 | Validation in `preprocessing/validate/` against schemas |
| M9 | HRMS TOON validated as Layer 4 projection of Layer 2 |

### TOON projection rules

1. **No field invention** — TOON fields must exist in domain contract or be explicitly marked `toon_extension: true`.
2. **Type coercion** — pipe-separated strings in TOON become arrays in normalized JSON.
3. **Empty vs missing** — TOON uses empty string; normalized JSON uses `null` or omit.
4. **Round-trip** — `toon_dumps(toon_loads_flex(toon))` must preserve semantics.

---

## Cross-feature contract usage

| Feature | Primary contracts |
|---------|-------------------|
| Resume parsing | Resume, Person, Experience, Education, Skills |
| JD parsing | JD, Skills |
| Bulk parsing | Resume (batch) |
| Resume matching | Resume + JD |
| Candidate ranking | Candidate Profile + JD + match scores |
| Summarization | Resume (input), Summary (output — future contract) |
| Interview questions | Resume + JD |
| AI Search | Resume + JD + Skills (indexed) |
| Chat assistant | Candidate Profile + JD + conversation (future) |

---

## Related documents

- [DATA_PIPELINE.md](DATA_PIPELINE.md)
- [VERSIONING.md](VERSIONING.md)
- [HRMS_DEPENDENCY_MAP.md](HRMS_DEPENDENCY_MAP.md)
- [adr/ADR-002-dataset-pipeline.md](adr/ADR-002-dataset-pipeline.md)
