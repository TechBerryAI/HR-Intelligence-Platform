# TOON Architecture

**Document ID:** ARCH-05  
**Status:** Constitutional — all structured human-capital data flows through TOON  
**Related:** [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) · [04_AI_PLATFORM.md](04_AI_PLATFORM.md) · [06_DATA_MODEL.md](06_DATA_MODEL.md)

---

## Purpose

This document defines the **TOON (Token-Oriented Object Notation)** architecture — the structured wire format that serves as the intelligence interchange layer between AI capabilities, business domains, and persistence. TOON is not an implementation; it is an ontology and format specification.

**Implementation locations (do not modify):**
- Specification: `ai/toon/v1/`
- Runtime serializer: `backend/toon.py`
- Validation: `backend/parsing_utils.py`

---

## What TOON Is

TOON is a **line-oriented, human-readable structured notation** designed for LLM generation and parsing. It serves as the canonical wire format for all AI-produced human-capital documents.

### Design goals

| Goal | Rationale |
|------|-----------|
| **LLM-friendly** | Line-oriented format is natural for LLM output; reduces JSON parsing errors |
| **Human-readable** | HR professionals can inspect TOON directly without tooling |
| **Token-efficient** | Compact representation vs. JSON; lower inference cost |
| **Versionable** | Independent semver with migration projections |
| **Validatable** | Schema rules enforceable without full parser complexity |
| **Extensible** | New document types and entities added without breaking existing consumers |

### What TOON is not

- Not a database schema (PostgreSQL stores TOON as text columns)
- Not a programming language or serialization protocol
- Not a replacement for JSON in API responses (APIs may expose JSON projected from TOON)
- Not a RAG document format (knowledge packs are separate)

---

## Scope

### Current document types (TOON-v1)

| Type | `type` field | Storage column | Domain |
|------|-------------|---------------|--------|
| **Resume** | `resume` | `parsed_resumes.toon` | Recruitment |
| **Job Description** | `job_description` | `parsed_jds.toon` | Recruitment |
| **ATS Result** | (envelope) | `applications.ats_analysis` | Recruitment |

### Future document types (TOON-v2+)

| Type | Domain | Planned version |
|------|--------|----------------|
| `employee` | Employee | TOON-v2 |
| `performance_review` | Performance | TOON-v2 |
| `learning_record` | Learning | TOON-v2 |
| `interview_feedback` | Hiring | TOON-v2 |
| `offer` | Hiring | TOON-v2 |
| `onboarding_plan` | Employee | TOON-v2 |
| `skill_assessment` | Learning | TOON-v2 |
| `organization_unit` | Organization | TOON-v2 |

New document types are added as TOON minor versions when backward compatible, major versions when breaking.

---

## Ontology Philosophy

### Principle: Documents, not tables

TOON represents **documents** — coherent structured artifacts produced by AI from unstructured input. A resume TOON is the AI's understanding of a resume, not a normalized database row.

### Principle: Projection, not duplication

Business domains store TOON as the AI artifact and may **project** TOON fields into normalized tables (e.g., `candidate_education`, `candidate_experiences`) for query efficiency. The TOON document remains the authoritative AI output; projections are derived views.

### Principle: Type-tagged documents

Every TOON document begins with a `type` field that determines schema validation rules:

```toon
type: resume
person.name: Jane Smith
person.email: jane@example.com
skills: Python|React|AWS
experience.0.title: Senior Engineer
experience.0.company: Acme Corp
experience.0.from: 2020
experience.0.to: 2024
education.0.degree: B.S. Computer Science
education.0.institution: MIT
education.0.year: 2018
```

### Principle: Flat with paths

TOON uses dot-notation paths for nesting and numeric indices for lists. There are no nested objects or arrays — everything is flat key-value:

| Pattern | Meaning | Example |
|---------|---------|---------|
| `key: value` | Scalar field | `person.name: Jane Smith` |
| `key.subkey: value` | Nested field | `person.email: jane@example.com` |
| `key: v1\|v2\|v3` | List of scalars | `skills: Python\|React\|AWS` |
| `key.N.field: value` | Indexed list item | `experience.0.title: Engineer` |

---

## Entity Philosophy

### Core entities (TOON-v1)

| Entity | Fields | Used in |
|--------|--------|---------|
| **person** | name, email, phone, location, linkedin, github | resume |
| **experience_item** | title, company, from, to, years, description | resume |
| **education_item** | degree, field, institution, year, gpa | resume |

### Entity aliases

TOON supports field aliases for LLM flexibility. The normalization layer maps aliases to canonical names:

| Canonical | Aliases |
|-----------|---------|
| `experience_item.title` | `role` |
| `experience_item.from` | `start`, `start_date` |
| `experience_item.to` | `end`, `end_date` |

Alias mappings: `ai/toon/v1/dictionary/`

### Entity linking via knowledge packs

Entity values (skills, titles, companies, locations) are normalized against knowledge packs before persistence:

```
LLM output: "React.js" → knowledge/skills/ → canonical: "React"
LLM output: "Sr. Software Eng" → knowledge/job_titles/ → canonical: "Senior Software Engineer"
```

Normalization is applied at the capability output validation stage, not in TOON itself.

### Entity composition rules

| Document type | Composed entities |
|--------------|-------------------|
| `resume` | person, experience_item*, education_item*, skills, certifications, languages |
| `job_description` | skills, company, location, responsibilities, qualifications |
| ATS result | json_output (score, decision), toon_output (reasoning) |

Composition rules: `ai/toon/v1/ontology/ontology.yaml`

---

## TOON Package Structure

```
ai/toon/v1/
├── ontology/
│   └── ontology.yaml          # Document types, entity definitions, relationships
├── dictionary/
│   └── field glossary         # Canonical names, aliases, descriptions
├── vocabulary/
│   └── wire datatypes         # String, number, date, list, indexed
├── validation/
│   └── wire-format rules      # Required fields, type constraints per document type
├── normalization/
│   └── projection transforms  # TOON → domain entity projections
├── mappings/
│   ├── resume.yaml            # Resume field mapping
│   ├── job_description.yaml   # JD field mapping
│   └── candidate.yaml         # Candidate profile projection
├── types/
│   └── toon.ts                # TypeScript contracts
├── examples/
│   └── sample .toon files     # Reference documents
├── benchmarks/
│   └── conformance tests      # TOON format compliance
└── tests/
    └── ontology tests
```

Active version registry: `ai/toon/versions.yaml` → `TOON-v1` (semver 1.0.0)

---

## Versioning

### Version strategy

| Version | Scope | Breaking changes |
|---------|-------|-----------------|
| **TOON-v1** (current) | resume, job_description, ATS result | N/A (baseline) |
| **TOON-v2** (planned) | + employee, performance, learning, hiring documents | New document types only |
| **TOON-v3** (future) | Entity model evolution | Potential entity renames |

### Version rules

1. **Adding** a document type or optional field → MINOR version
2. **Renaming** or **removing** an entity or required field → MAJOR version
3. **Changing** validation rules on existing fields → MAJOR version
4. Each major version maintains a **projection layer** to convert from prior version

### Version in storage

Every parsed artifact records the TOON version used:

| Column | Purpose |
|--------|---------|
| `parsed_resumes.model_version` | AI model that produced the TOON |
| (future) `parsed_resumes.toon_version` | TOON schema version (e.g., `TOON-v1`) |

### Migration philosophy

When TOON-v2 ships:
- Existing TOON-v1 documents remain valid and readable
- New documents use TOON-v2
- Projection functions convert v1 → v2 on read (lazy migration)
- Bulk migration runs as background job, not blocking

---

## Relationship with Knowledge Packs

```
┌──────────────┐     normalize      ┌──────────────┐
│  LLM Output  │ ──────────────────►│  TOON Document│
│  (raw text)  │                    │  (validated)  │
└──────────────┘                    └──────┬───────┘─┘
                                           │
                                    entity values
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │  Knowledge   │
                                    │  Packs       │
                                    │  (skills,    │
                                    │   titles,    │
                                    │   degrees,   │
                                    │   companies, │
                                    │   locations) │
                                    └──────────────┘
```

| Aspect | TOON | Knowledge Packs |
|--------|------|-----------------|
| **Purpose** | Structured document format | Reference vocabulary for normalization |
| **Ownership** | `ai/toon/v1/` | `ai/knowledge/` |
| **Versioning** | TOON-v1, TOON-v2 | Independent per pack |
| **Relationship** | TOON fields reference knowledge pack entities | Knowledge packs do not define TOON structure |
| **Updates** | Schema changes require TOON version bump | Alias additions are non-breaking |

Knowledge packs normalize **values** within TOON fields. TOON defines **structure**.

---

## Relationship with Runtime

```
Capability (prompt.md) ──► LLM ──► Raw output
                                      │
                                      ▼
                              Output Validator (schema.json)
                                      │
                                      ▼
                              TOON Serializer (backend/toon.py)
                                      │
                                      ▼
                              TOON Validator (parsing_utils.py)
                                      │
                                      ▼
                              Persist (PostgreSQL text column)
```

| Stage | Component | TOON role |
|-------|-----------|-----------|
| Prompt | `prompt.md` | Instructs LLM to produce TOON-format output |
| Validation | `schema.json` + `validation.yaml` | Validates structure before serialization |
| Serialization | `backend/toon.py` | Converts validated JSON to TOON text |
| Storage | PostgreSQL | TOON stored as text in `parsed_resumes.toon`, `parsed_jds.toon` |
| Deserialization | `backend/toon.py` | Converts TOON text back to dict for application logic |
| Frontend | API responses | TOON projected to JSON for UI consumption |

The AI runtime never stores TOON directly — it returns validated output to the backend, which serializes and persists.

---

## Relationship with Specifications

### Authority chain

```
ai/contracts/          Domain contracts (YAML) — what entities exist
    ↓
ai/schemas/            Document schemas (YAML) — field definitions
    ↓
ai/knowledge/          Reference vocabularies — value normalization
    ↓
ai/toon/v1/            Wire format — how data is serialized
    ↓
backend/toon.py        Runtime — serialize/parse implementation
```

Each layer derives from the one above. No layer redefines entities from a lower layer.

### Contract → Schema → TOON mapping

| Contract entity | Schema field | TOON path |
|----------------|-------------|-----------|
| `skill` | `skills[]` | `skills: Python\|React` |
| `experience` | `experience[].title` | `experience.0.title: Engineer` |
| `education` | `education[].degree` | `education.0.degree: B.S.` |
| `person` | `person.name` | `person.name: Jane Smith` |

Mappings: `ai/toon/v1/mappings/resume.yaml`, `job_description.yaml`, `candidate.yaml`

### Specifications vs. TOON

| Document | Purpose | Format |
|----------|---------|--------|
| `ai/contracts/*.yaml` | Domain entity definitions | YAML |
| `ai/schemas/*.yaml` | Normalized document schemas | YAML |
| `ai/toon/v1/ontology/ontology.yaml` | Wire format ontology | YAML |
| TOON document | Stored artifact | Line-oriented text |

Contracts and schemas are **design-time** specifications. TOON documents are **runtime** artifacts.

---

## Relationship with Prompt Templates

### Prompt → TOON contract

Every capability's `prompt.md` includes explicit TOON output instructions:

1. **System prompt** defines the TOON document type and required fields (immutable at runtime)
2. **User prompt template** provides the input document and repeats format constraints
3. **Examples** in `examples/` show golden TOON output

### Prompt design rules for TOON

| Rule | Rationale |
|------|-----------|
| System prompt specifies exact TOON format | Prevents LLM format drift |
| Required fields listed explicitly | Enables validation gate |
| Examples included in prompt | Few-shot improves field completeness |
| User content sandboxed | Prevents prompt injection from affecting format |
| Output mode set to structured (JSON schema) | LLM produces JSON that serializes to TOON |

### Prompt versioning

Prompt changes that affect TOON output format require:
1. Updated `prompt.md`
2. Re-run benchmark (BENCH-*)
3. New prompt registry entry (PROMPT-NNNN)
4. Evaluation pass before deployment

Prompt changes that do not affect output schema (wording improvements) require benchmark re-run but not TOON version bump.

---

## Validation Rules

### Resume TOON (required)

| Field | Required | Type |
|-------|----------|------|
| `type` | Yes | `resume` |
| `person.name` | Yes | string |
| `person.email` | Yes | string |
| `person.phone` | Yes | string |
| `skills` | Yes | list |
| `experience` | Yes | indexed list (≥1 item) |
| `education` | Yes | indexed list (≥1 item) |

Optional: `summary`, `certifications`, `languages`, `total_experience_years`

### Job Description TOON (required)

| Field | Required | Type |
|-------|----------|------|
| `type` | Yes | `job_description` |
| `title` | Yes | string |
| `location` | Yes | string |
| `skills` | Yes | list |
| `responsibilities` | Yes | list |

Optional: `mandatory_skills`, `preferred_skills`, `min_experience_years`, `max_experience_years`, `qualifications`, `salary_range`

### ATS Result TOON

| Field | Required | Type |
|-------|----------|------|
| `json_output.final_score` | Yes | number |
| `json_output.decision` | Yes | string |
| `json_output.verdict` | Yes | string |
| `toon_output` | Yes | string (reasoning) |

Validation implementation: `backend/parsing_utils.py` → `validate_toon_format()`

---

## Cross-References

| Topic | Document |
|-------|----------|
| AI capabilities using TOON | [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) |
| AI platform | [04_AI_PLATFORM.md](04_AI_PLATFORM.md) |
| Conceptual data model | [06_DATA_MODEL.md](06_DATA_MODEL.md) |
| Domain entities | [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md) |
| Current TOON schema (production) | `ai/docs/current_system/CURRENT_TOON_SCHEMA.md` |
| TOON package | `ai/toon/v1/` |
| Versioning strategy | `ai/docs/VERSIONING.md` |
