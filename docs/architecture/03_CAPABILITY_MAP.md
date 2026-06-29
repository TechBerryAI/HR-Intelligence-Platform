# Capability Map

**Document ID:** ARCH-03  
**Status:** Constitutional — all AI implementations must conform to this map  
**Related:** [04_AI_PLATFORM.md](04_AI_PLATFORM.md) · [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md) · [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md)

---

## Purpose

This document defines every **AI capability** in the Human Capital Intelligence Platform. Each capability is a governed, versioned intelligence service with defined responsibilities, inputs, outputs, dependencies, and TOON entity usage.

Capabilities are implemented in `ai/capabilities/` and invoked through `ai/runtime/`.

---

## Capability Registry

| ID | Name | Status | Domain | Output Mode |
|----|------|--------|--------|-------------|
| `resume_parsing` | Resume Intelligence | **Active** | Recruitment | JSON → TOON |
| `jd_parsing` | Job Intelligence | **Active** | Recruitment | JSON → TOON |
| `bulk_resume_parsing` | Bulk Resume Intelligence | **Active** | Recruitment | JSON → TOON |
| `candidate_matching` | Matching Intelligence | **Active** | Recruitment | JSON → TOON |
| `resume_summary` | Resume Summary | **Active** | Recruitment | Text |
| `interview_generation` | Interview Intelligence | **Active** | Hiring | JSON |
| `hr_chat` | HR Copilot | **Active** | Cross-domain | Text |
| `offer_intelligence` | Offer Intelligence | Planned | Hiring | JSON |
| `employee_intelligence` | Employee Intelligence | Planned | Employee | JSON → TOON |
| `onboarding_intelligence` | Onboarding Intelligence | Planned | Employee | JSON |
| `learning_intelligence` | Learning Intelligence | Planned | Learning | JSON |
| `performance_intelligence` | Performance Intelligence | Planned | Performance | JSON → TOON |
| `career_intelligence` | Career Intelligence | Planned | Employee | JSON |
| `organization_intelligence` | Organization Intelligence | Planned | Organization | JSON |
| `workforce_planning` | Workforce Planning | Planned | Organization | JSON |
| `skill_intelligence` | Skill Intelligence | Planned | Learning / Organization | JSON |
| `analytics_intelligence` | Analytics Intelligence | Planned | Analytics | JSON |
| `succession_intelligence` | Succession Intelligence | Planned | Organization | JSON |

---

## Active Capabilities

### resume_parsing — Resume Intelligence

**Responsibilities:**
- Extract structured candidate data from unstructured resume documents
- Normalize skills, titles, education, and experience via knowledge bases
- Produce validated TOON resume document with confidence score

**Inputs:**

| Input | Type | Required |
|-------|------|----------|
| Document text | string (extracted from PDF/DOC/DOCX) | Yes |
| Document metadata | filename, mime type, page count | Yes |
| Parsing options | language, strict mode | No |

**Outputs:**

| Output | Type | Storage |
|--------|------|---------|
| TOON resume document | TOON text | `parsed_resumes.toon` |
| Confidence score | float (0–1) | `parsed_resumes.confidence` |
| Full extracted text | string | `parsed_resumes.full_text` |
| Model version | string | `parsed_resumes.model_version` |

**Dependencies:**
- Provider: X.AI Grok (production), Ollama (platform runtime)
- Text extraction: `ai/dataset/extraction/`
- Validation: `backend/parsing_utils.py` → `validate_toon_format()`

**TOON entities used:**
- Document type: `resume`
- Entities: `person`, `experience_item`, `education_item`
- Fields: `skills`, `certifications`, `languages`, `summary`, `total_experience_years`

**Knowledge packs used:**
- `skills/` — skill alias normalization
- `job_titles/` — title normalization
- `degrees/` — education credential normalization
- `certifications/` — certification name normalization
- `companies/` — employer normalization
- `locations/` — geographic normalization

**Future models:** `hrms-parsing-v1` (fine-tuned, Ollama-deployed)

**Benchmark:** `BENCH-PARSE-v1`

---

### jd_parsing — Job Intelligence

**Responsibilities:**
- Extract structured job requirements from unstructured job descriptions
- Identify mandatory vs. preferred skills, experience range, qualifications
- Produce validated TOON job description document

**Inputs:**

| Input | Type | Required |
|-------|------|----------|
| Document text | string | Yes |
| Job metadata | title hint, company | No |

**Outputs:**

| Output | Type | Storage |
|--------|------|---------|
| TOON JD document | TOON text | `parsed_jds.toon` |
| Confidence score | float | `parsed_jds.confidence` |
| Model version | string | `parsed_jds.model_version` |

**Dependencies:** Same provider and extraction stack as `resume_parsing`.

**TOON entities used:**
- Document type: `job_description`
- Fields: `title`, `location`, `skills`, `mandatory_skills`, `preferred_skills`, `responsibilities`, `qualifications`, `min_experience_years`, `max_experience_years`, `salary_range`

**Knowledge packs used:** `skills/`, `job_titles/`, `locations/`, `companies/`

**Future models:** `hrms-parsing-v1` (shared with resume parsing)

**Benchmark:** `BENCH-PARSE-v1`

---

### bulk_resume_parsing — Bulk Resume Intelligence

**Responsibilities:**
- Process large batches of resume files (100–10,000+)
- Apply `resume_parsing` per document with progress tracking
- Aggregate results for export (Excel, CSV)

**Inputs:**

| Input | Type | Required |
|-------|------|----------|
| File batch | array of file paths or uploads | Yes |
| Batch configuration | concurrency, timeout, output format | No |

**Outputs:**

| Output | Type | Storage |
|--------|------|---------|
| Batch results | array of TOON resume documents | Export file |
| Progress status | percentage, success/failure counts | Polling endpoint |
| Error log | per-file failure reasons | Export metadata |

**Dependencies:**
- `resume_parsing` capability (per-file)
- External bulk parser API (optional) or in-process fallback
- Electron native folder dialog (desktop)

**TOON entities used:** Same as `resume_parsing`.

**Knowledge packs used:** Same as `resume_parsing`.

**Future models:** Same as `resume_parsing` with batch-optimized routing.

**Benchmark:** `BENCH-PARSE-v1` (per-file quality); batch throughput measured separately.

---

### candidate_matching — Matching Intelligence

**Responsibilities:**
- Score candidate–job fit based on skills, experience, education, and location
- Apply mandatory skills gate and weighted scoring
- Produce explainable match result with reasoning

**Inputs:**

| Input | Type | Required |
|-------|------|----------|
| Resume TOON | TOON text | Yes |
| JD TOON | TOON text | Yes |
| Matching configuration | weight overrides, threshold | No |

**Outputs:**

| Output | Type | Storage |
|--------|------|---------|
| Match score | float (0–100) | `applications.match_score` |
| Shortlist tier | enum (high/medium/low) | `applications.shortlisted` |
| ATS reasoning | TOON/text | `applications.ats_reasoning` |
| ATS analysis | TOON envelope | `applications.ats_analysis` |
| Score breakdown | skills/experience/education/location | Within ATS analysis |

**Scoring weights (current):**
- Skills: 60% (mandatory 40%, preferred 20%)
- Experience: 25%
- Education: 10%
- Location: 5%
- Mandatory skills gate: 60% minimum

**Dependencies:**
- Parsed resume and JD (TOON)
- In-process ATS service or n8n webhook workflow

**TOON entities used:**
- Input: `resume` + `job_description` document types
- Output: ATS result envelope (`json_output`, `toon_output`)

**Knowledge packs used:** `skills/` (for skill matching and normalization)

**Future models:** `hrms-matching-v1` (dedicated matching model)

**Benchmark:** `BENCH-MATCH-v1` (planned)

---

### resume_summary — Resume Summary

**Responsibilities:**
- Generate concise human-readable summary of a candidate's resume
- Highlight key skills, experience, and qualifications

**Inputs:**

| Input | Type | Required |
|-------|------|----------|
| Resume TOON or text | TOON text or raw text | Yes |
| Summary options | length, focus areas | No |

**Outputs:**

| Output | Type | Storage |
|--------|------|---------|
| Summary text | string | Transient (display only) |

**Dependencies:** Provider (text generation mode)

**TOON entities used:** Reads `resume` document type.

**Knowledge packs used:** None (reads structured TOON directly).

**Future models:** General-purpose LLM sufficient; no dedicated model planned.

**Benchmark:** `BENCH-SUMMARY-v1` (planned)

---

### interview_generation — Interview Intelligence

**Responsibilities:**
- Generate role-specific interview questions from resume and job description
- Categorize questions by competency area
- Provide suggested evaluation criteria

**Inputs:**

| Input | Type | Required |
|-------|------|----------|
| Resume TOON | TOON text | Yes |
| JD TOON | TOON text | Yes |
| Interview configuration | question count, difficulty, focus areas | No |

**Outputs:**

| Output | Type | Storage |
|--------|------|---------|
| Questions | array of {question, category, evaluation_criteria} | Transient or Interview entity (future) |

**Dependencies:** Provider (JSON generation mode)

**TOON entities used:** Reads `resume` + `job_description`.

**Knowledge packs used:** `skills/`, `job_titles/`

**Future models:** General-purpose LLM; potential fine-tune for domain-specific questions.

**Benchmark:** `BENCH-GEN-v1` (planned)

---

### hr_chat — HR Copilot

**Responsibilities:**
- Answer HR/recruiter questions about candidates, jobs, and platform features
- Provide contextual assistance during recruitment workflows
- Ground responses in platform data (future: RAG over tenant data)

**Inputs:**

| Input | Type | Required |
|-------|------|----------|
| User message | string | Yes |
| Conversation history | array of messages | No |
| Context | current page, selected candidate/job | No |

**Outputs:**

| Output | Type | Storage |
|--------|------|---------|
| Assistant response | string | Transient (conversation) |

**Dependencies:** Provider (text generation mode)

**TOON entities used:** May reference any TOON document type in context.

**Knowledge packs used:** Platform documentation (future: tenant-specific knowledge).

**Future models:** General-purpose LLM with RAG augmentation.

**Benchmark:** `BENCH-GEN-v1` (planned); safety benchmarks for prompt injection resistance.

---

## Planned Capabilities

### offer_intelligence — Offer Intelligence

**Domain:** Hiring  
**Responsibilities:** Recommend compensation packages based on role, market data, and candidate profile. Generate offer letter drafts.  
**Inputs:** Application, JD TOON, market benchmarks, company compensation bands  
**Outputs:** Recommended offer range, offer letter draft, acceptance probability  
**TOON entities:** `job_description`, future `offer` document type  
**Knowledge packs:** `job_titles/`, `companies/`, future market data packs  
**Future models:** `hrms-offer-v1`

### employee_intelligence — Employee Intelligence

**Domain:** Employee  
**Responsibilities:** Enrich employee records from documents, generate employee summaries, detect data quality issues.  
**Inputs:** Employee documents, employment records  
**Outputs:** Structured employee TOON, data quality report  
**TOON entities:** Future `employee` document type  
**Knowledge packs:** All knowledge bases  
**Future models:** `hrms-employee-v1`

### onboarding_intelligence — Onboarding Intelligence

**Domain:** Employee  
**Responsibilities:** Generate personalized onboarding plans based on role, department, and employee background.  
**Inputs:** Employee record, role, department, hire date  
**Outputs:** Onboarding task list, timeline, resource recommendations  
**TOON entities:** Future `onboarding_plan` document type  
**Knowledge packs:** `job_titles/`, `skills/`

### learning_intelligence — Learning Intelligence

**Domain:** Learning  
**Responsibilities:** Recommend learning paths, assess skill gaps, match courses to development needs.  
**Inputs:** Employee skill profile, role requirements, available courses  
**Outputs:** Learning path, skill gap analysis, course recommendations  
**TOON entities:** Future `learning_record`, `skill_assessment` document types  
**Knowledge packs:** `skills/`, `certifications/`, `degrees/`

### performance_intelligence — Performance Intelligence

**Domain:** Performance  
**Responsibilities:** Assist review writing, detect rating bias, suggest development actions.  
**Inputs:** Performance data, goals, feedback history  
**Outputs:** Review draft, bias analysis, development recommendations  
**TOON entities:** Future `performance_review` document type  
**Knowledge packs:** `skills/`, `job_titles/`

### career_intelligence — Career Intelligence

**Domain:** Employee  
**Responsibilities:** Map career trajectories, recommend internal opportunities, identify high-potential employees.  
**Inputs:** Employee history, skills, performance, org structure  
**Outputs:** Career path recommendations, mobility matches, potential assessment  
**Knowledge packs:** `skills/`, `job_titles/`, `companies/`

### organization_intelligence — Organization Intelligence

**Domain:** Organization  
**Responsibilities:** Analyze org structure health, detect span-of-control issues, model reorganization scenarios.  
**Inputs:** Org chart, headcount data, attrition history  
**Outputs:** Structure analysis, scenario models, recommendations  
**Knowledge packs:** `job_titles/`, `companies/`

### workforce_planning — Workforce Planning

**Domain:** Organization  
**Responsibilities:** Forecast hiring needs, model workforce scenarios, align headcount to business plans.  
**Inputs:** Business plan, current headcount, attrition rates, growth projections  
**Outputs:** Hiring forecast, scenario comparison, budget impact  
**Knowledge packs:** `job_titles/`, `skills/`, market data (future)

### skill_intelligence — Skill Intelligence

**Domain:** Learning / Organization  
**Responsibilities:** Build and maintain organizational skill inventory, detect emerging skill needs, map skills to roles.  
**Inputs:** Employee profiles, job requirements, industry trends  
**Outputs:** Skill inventory, gap matrix, emerging skill alerts  
**Knowledge packs:** `skills/` (primary)

### analytics_intelligence — Analytics Intelligence

**Domain:** Analytics  
**Responsibilities:** Generate natural language insights from HR metrics, detect anomalies, recommend actions.  
**Inputs:** Aggregated metrics, dashboard data, historical trends  
**Outputs:** Insight narratives, anomaly alerts, action recommendations  

### succession_intelligence — Succession Intelligence

**Domain:** Organization  
**Responsibilities:** Identify succession candidates, assess readiness, model succession scenarios.  
**Inputs:** Key positions, employee performance, career data, org structure  
**Outputs:** Succession matrix, readiness scores, development gaps  
**Knowledge packs:** `skills/`, `job_titles/`

---

## Capability Architecture Pattern

Every capability follows this structure in `ai/capabilities/{capability_id}/`:

```
{capability_id}/
├── capability.yaml      # Metadata, version, dependencies
├── prompt.md            # System and user prompt templates
├── schema.json          # Output JSON schema
├── validation.yaml      # Post-inference validation rules
├── runtime.yaml         # Provider preferences, timeout, retry
├── examples/            # Input/output examples
├── benchmarks/          # Capability-specific benchmark data
└── tests/               # Unit and integration tests
```

### Capability lifecycle

```
Define → Schema → Prompt → Validate → Benchmark → Evaluate → Deploy → Monitor
  │                                                                    │
  └──────────── Human corrections ← Dataset ← Production ←──────────┘
```

Full lifecycle: [04_AI_PLATFORM.md](04_AI_PLATFORM.md) § Model Lifecycle.

---

## Knowledge Pack Reference

Knowledge packs are curated reference vocabularies in `ai/knowledge/`. They are **not** RAG document stores — they are normalization and entity-linking datasets.

| Pack | Path | Used by capabilities |
|------|------|---------------------|
| Skills | `ai/knowledge/skills/` | resume_parsing, jd_parsing, candidate_matching, skill_intelligence |
| Job Titles | `ai/knowledge/job_titles/` | resume_parsing, jd_parsing, interview_generation, career_intelligence |
| Degrees | `ai/knowledge/degrees/` | resume_parsing |
| Certifications | `ai/knowledge/certifications/` | resume_parsing, learning_intelligence |
| Companies | `ai/knowledge/companies/` | resume_parsing, jd_parsing, organization_intelligence |
| Locations | `ai/knowledge/locations/` | resume_parsing, jd_parsing, candidate_matching |

Each pack contains: `schema.yaml`, `aliases.json`, and sharded `entries/` (gitignored).

Manifest: `ai/knowledge/manifest.yaml`.

---

## Cross-References

| Topic | Document |
|-------|----------|
| AI platform architecture | [04_AI_PLATFORM.md](04_AI_PLATFORM.md) |
| TOON entity definitions | [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md) |
| Domain ownership | [02_DOMAIN_MODEL.md](02_DOMAIN_MODEL.md) |
| Workflow sequences | [08_DATA_FLOWS.md](08_DATA_FLOWS.md) |
| Capability deployment roadmap | [11_PRODUCT_ROADMAP.md](11_PRODUCT_ROADMAP.md) |
