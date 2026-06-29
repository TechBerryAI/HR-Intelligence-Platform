# Domain Model

**Document ID:** ARCH-02  
**Status:** Constitutional — all schemas, APIs, and capabilities derive from this model  
**Related:** [06_DATA_MODEL.md](06_DATA_MODEL.md) · [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) · [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md)

---

## Purpose

This document defines every **business domain** in the Human Capital Intelligence Platform. Each domain has clear ownership of actors, entities, relationships, and lifecycle rules. Domains compose into the complete employee lifecycle without overlapping responsibilities.

---

## Domain Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    HUMAN CAPITAL INTELLIGENCE PLATFORM                   │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────┤
│ Recruitment │   Hiring    │  Employee   │  Learning   │  Performance    │
│  (Active)   │  (Active)   │  (Planned)  │  (Planned)  │   (Planned)     │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│Organization │    Admin    │  Analytics  │     AI      │   Integration   │
│  (Partial)  │  (Active)   │  (Planned)  │  (Active)   │    (Partial)    │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘
```

**Legend:** Active = implemented or in production; Partial = foundation exists; Planned = designed, not implemented.

---

## Domain: Recruitment

### Purpose

Manage the discovery, attraction, and application pipeline for external candidates. Recruitment is the entry point of the human capital lifecycle.

### Actors

| Actor | Responsibilities |
|-------|-----------------|
| **Candidate** | Register, build profile, upload resume, search jobs, apply, track status |
| **HR / Recruiter** | Post jobs, review applications, manage pipeline, run bulk parsing |
| **Head HR** | All HR responsibilities plus admin management |
| **Guest** | Browse public job listings |

### Entities

| Entity | Description | Owner |
|--------|-------------|-------|
| **Job** | Open position with title, description, requirements, location, salary, status | Recruitment |
| **Job Description (Parsed)** | Structured JD extracted via AI into TOON format | Recruitment |
| **Candidate Profile** | Personal information, contact, preferences | Recruitment |
| **Resume (Raw)** | Uploaded document (PDF/DOC/DOCX) | Recruitment |
| **Resume (Parsed)** | Structured resume in TOON format with confidence score | Recruitment |
| **Application** | Candidate–Job association with status, match score, ATS reasoning | Recruitment |
| **Saved Job** | Candidate bookmark of a job posting | Recruitment |

### Relationships

```
Candidate ──1:1──► Candidate Profile
Candidate Profile ──1:N──► Resume (Raw) ──1:1──► Resume (Parsed)
Job ──1:1──► Job Description (Parsed)
Candidate ──N:M──► Job  (via Application)
Application ──reads──► latest Resume (Parsed) + Job Description (Parsed)
```

### Ownership

- **Recruitment domain** owns all entities above.
- **AI domain** produces parsed artifacts but does not own them.
- **Hiring domain** reads Application state but does not mutate Recruitment entities directly.

### Future Expansion

- Job requisition workflow (approval chains)
- Talent pool and pipeline management
- Source tracking and recruitment marketing analytics
- Campus recruiting and event management
- Referral program management

### AI Capabilities

`resume_parsing`, `jd_parsing`, `bulk_resume_parsing`, `candidate_matching`, `resume_summary`, `interview_generation` — see [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md).

---

## Domain: Hiring

### Purpose

Manage the decision and transition from candidate to employee: interview coordination, offer management, background checks, and hire confirmation.

### Actors

| Actor | Responsibilities |
|-------|-----------------|
| **HR / Recruiter** | Schedule interviews, extend offers, confirm hire |
| **Hiring Manager** | Conduct interviews, provide feedback, approve hire |
| **Candidate** | Participate in interviews, accept/decline offers |

### Entities

| Entity | Description | Owner |
|--------|-------------|-------|
| **Interview** | Scheduled interaction with type, participants, feedback | Hiring |
| **Interview Feedback** | Structured evaluation from interviewer | Hiring |
| **Offer** | Compensation package, start date, conditions | Hiring |
| **Offer Response** | Candidate acceptance or decline | Hiring |
| **Hire Record** | Confirmed transition from candidate to employee | Hiring |

### Relationships

```
Application ──1:N──► Interview ──1:N──► Interview Feedback
Application ──0:1──► Offer ──1:1──► Offer Response
Offer Response (accepted) ──triggers──► Hire Record ──creates──► Employee (Employee domain)
```

### Ownership

- **Hiring domain** owns interview, offer, and hire entities.
- Reads Application from Recruitment; emits Hire Record to Employee domain.

### Future Expansion

- Interview panel coordination and calendar integration
- Structured scorecards and rubrics
- Offer letter generation and e-signature
- Background check and compliance verification
- Pre-boarding task management

### AI Capabilities

`interview_generation` (active), future: `offer_intelligence`, `interview_intelligence`, `hire_prediction`.

---

## Domain: Employee

### Purpose

Manage the employed workforce from hire through separation: identity, employment record, organizational assignment, and lifecycle events.

### Actors

| Actor | Responsibilities |
|-------|-----------------|
| **Employee** | View own record, update personal info, access self-service |
| **HR** | Manage employee records, process lifecycle events |
| **Manager** | View direct reports, approve changes |
| **Head HR / Super Admin** | Full employee administration |

### Entities

| Entity | Description | Owner |
|--------|-------------|-------|
| **Employee** | Core employment record linked to former Candidate | Employee |
| **Employment Record** | Job title, department, start date, employment type, status | Employee |
| **Organizational Assignment** | Reporting line, cost center, location | Employee |
| **Lifecycle Event** | Promotion, transfer, termination, leave of absence | Employee |
| **Onboarding Plan** | Structured tasks for new hire integration | Employee |

### Relationships

```
Hire Record ──creates──► Employee ──1:N──► Employment Record
Employee ──1:N──► Organizational Assignment
Employee ──1:N──► Lifecycle Event
Employee ──0:1──► Onboarding Plan
Employee ──1:1──► Candidate (historical link)
```

### Ownership

- **Employee domain** owns all post-hire entities.
- Receives Hire Record from Hiring domain.
- Provides Employee context to Learning, Performance, and Organization domains.

### Future Expansion

- Employee self-service portal
- Document management (contracts, policies)
- Offboarding workflow
- Internal directory and org chart
- Employee feedback and engagement surveys

### AI Capabilities

Future: `employee_intelligence`, `onboarding_intelligence`, `career_intelligence`.

---

## Domain: Learning

### Purpose

Manage workforce development: training programs, skill acquisition, certifications, and competency tracking.

### Actors

| Actor | Responsibilities |
|-------|-----------------|
| **Employee / Learner** | Enroll in courses, complete training, earn certifications |
| **L&D Administrator** | Create programs, assign training, track completion |
| **Manager** | Approve training, assess skill development |

### Entities

| Entity | Description | Owner |
|--------|-------------|-------|
| **Learning Program** | Structured curriculum with modules and objectives | Learning |
| **Course** | Individual learning unit with content and assessment | Learning |
| **Enrollment** | Employee–Course association with progress and completion | Learning |
| **Certification** | Earned credential with expiry and verification | Learning |
| **Skill Assessment** | Measured proficiency in a skill area | Learning |
| **Learning Path** | Recommended sequence of courses for a role or goal | Learning |

### Relationships

```
Learning Program ──1:N──► Course
Employee ──N:M──► Course (via Enrollment)
Employee ──1:N──► Certification
Employee ──1:N──► Skill Assessment
Learning Path ──N:M──► Course
Skill Assessment ──references──► Skill (Knowledge)
```

### Ownership

- **Learning domain** owns all training entities.
- References Employee from Employee domain and Skill from Knowledge.

### Future Expansion

- LMS integration (SCORM, xAPI)
- Microlearning and content marketplace
- Skill gap analysis and auto-recommendation
- Compliance training tracking
- Learning analytics and ROI measurement

### AI Capabilities

Future: `learning_intelligence`, `skill_intelligence`, `learning_path_generation`.

---

## Domain: Performance

### Purpose

Manage employee performance evaluation, goal setting, feedback cycles, and development planning.

### Actors

| Actor | Responsibilities |
|-------|-----------------|
| **Employee** | Set goals, self-assess, request feedback |
| **Manager** | Conduct reviews, provide feedback, approve goals |
| **HR** | Configure review cycles, calibrate ratings, generate reports |

### Entities

| Entity | Description | Owner |
|--------|-------------|-------|
| **Review Cycle** | Time-bounded performance evaluation period | Performance |
| **Goal** | Measurable objective with target and progress | Performance |
| **Performance Review** | Structured evaluation with ratings and narrative | Performance |
| **Feedback** | Peer, upward, or 360-degree input | Performance |
| **Development Plan** | Post-review growth actions linked to Learning | Performance |
| **Calibration Session** | HR-led rating normalization across teams | Performance |

### Relationships

```
Review Cycle ──1:N──► Performance Review ──1:1──► Employee
Performance Review ──1:N──► Goal
Performance Review ──1:N──► Feedback
Performance Review ──0:1──► Development Plan ──references──► Learning Program
Review Cycle ──1:N──► Calibration Session
```

### Ownership

- **Performance domain** owns all review entities.
- Links to Employee, Learning, and Organization domains.

### Future Expansion

- Continuous feedback (not just periodic reviews)
- OKR framework support
- 360-degree and peer review
- Performance improvement plans
- Succession readiness assessment

### AI Capabilities

Future: `performance_intelligence`, `feedback_generation`, `goal_recommendation`, `calibration_intelligence`.

---

## Domain: Organization

### Purpose

Model the organizational structure, hierarchy, departments, teams, and workforce composition.

### Actors

| Actor | Responsibilities |
|-------|-----------------|
| **Head HR / Super Admin** | Define org structure, manage departments |
| **HR** | View org chart, manage assignments |
| **Manager** | View team structure and headcount |
| **Workforce Planner** | Analyze composition, plan headcount |

### Entities

| Entity | Description | Owner |
|--------|-------------|-------|
| **Organization** | Top-level tenant entity (company) | Organization |
| **Department** | Functional unit within organization | Organization |
| **Team** | Sub-unit within department | Organization |
| **Position** | Defined role with title, level, and requirements | Organization |
| **Org Chart Node** | Hierarchical relationship between positions/people | Organization |
| **Headcount Plan** | Planned vs. actual workforce by unit | Organization |

### Relationships

```
Organization ──1:N──► Department ──1:N──► Team
Department ──1:N──► Position
Position ──N:1──► Employee (Organizational Assignment)
Org Chart Node ──maps──► Position hierarchy
Headcount Plan ──references──► Department + Position
```

### Ownership

- **Organization domain** owns structural entities.
- Currently partial: company field on HR signup represents Organization.
- Full org model is a future enterprise milestone.

### Future Expansion

- Multi-entity support (subsidiaries, divisions)
- Organization graph (not just tree)
- Workforce planning and scenario modeling
- Span of control analytics
- Diversity and inclusion metrics

### AI Capabilities

Future: `organization_intelligence`, `workforce_planning`, `succession_intelligence`, `org_graph_analysis`.

---

## Domain: Administration

### Purpose

Platform governance: user management, system configuration, support, feedback, and operational controls.

### Actors

| Actor | Responsibilities |
|-------|-----------------|
| **Super Admin** | System-wide management, admin CRUD, global settings |
| **Head HR** | Manage HR users within tenant |
| **Support Agent** | Handle support requests |
| **System** | Automated maintenance, health checks |

### Entities

| Entity | Description | Owner |
|--------|-------------|-------|
| **HR Account** | Recruiter/admin user with role and company | Administration |
| **Super Admin Account** | System-wide administrator | Administration |
| **Session** | Active authentication session with device info | Administration |
| **Login History** | Authentication audit trail | Administration |
| **Support Request** | Public contact form submission | Administration |
| **Employee Feedback** | Internal HRMS testing feedback with screenshots | Administration |
| **System Settings** | Platform configuration per tenant | Administration |

### Relationships

```
HR Account ──1:N──► Session
HR Account ──1:N──► Login History
Organization ──1:N──► HR Account
Support Request ──standalone (public)
Employee Feedback ──references──► HR Account (submitter, optional)
```

### Ownership

- **Administration domain** owns all platform governance entities.
- Cross-cuts all other domains for user management and audit.

### Future Expansion

- Tenant provisioning and configuration
- SSO/SAML integration management
- Role and permission customization
- Audit log viewer and export
- Platform health dashboard
- Billing and subscription management

---

## Domain: Analytics

### Purpose

Aggregate, visualize, and derive insights from cross-domain data for HR leaders and workforce planners.

### Actors

| Actor | Responsibilities |
|-------|-----------------|
| **HR Leader / CHRO** | View dashboards, export reports |
| **People Analytics Team** | Build custom analyses, configure metrics |
| **Manager** | View team-level analytics |

### Entities

| Entity | Description | Owner |
|--------|-------------|-------|
| **Metric Definition** | Named KPI with formula and data sources | Analytics |
| **Dashboard** | Composed visualization of metrics | Analytics |
| **Report** | Scheduled or on-demand data export | Analytics |
| **Insight** | AI-generated observation from data patterns | Analytics |
| **Benchmark Comparison** | Tenant metric vs. industry benchmark | Analytics |

### Relationships

```
Metric Definition ──N:M──► Dashboard
Dashboard ──1:N──► Report
Insight ──derived from──► cross-domain entities (read-only)
Benchmark Comparison ──references──► Metric Definition
```

### Ownership

- **Analytics domain** is read-only across all domains.
- Never mutates source domain entities.
- Insights are derived artifacts owned by Analytics.

### Future Expansion

- Real-time dashboards
- Predictive analytics (attrition, hiring velocity)
- Custom report builder
- Data warehouse integration
- Industry benchmarking network

### AI Capabilities

Future: `analytics_intelligence`, `insight_generation`, `workforce_forecasting`.

---

## Domain: AI

### Purpose

Provide governed intelligence services to all domains through a capability framework, runtime, ontology, and knowledge infrastructure.

### Actors

| Actor | Responsibilities |
|-------|-----------------|
| **AI Runtime** | Execute capabilities, route to providers, validate output |
| **AI Engineer** | Develop capabilities, train models, run evaluations |
| **ML Ops Engineer** | Deploy models, monitor drift, manage registry |
| **Domain Services** | Consume AI capabilities via runtime adapter |

### Entities

| Entity | Description | Owner |
|--------|-------------|-------|
| **Capability** | Versioned intelligence package (prompt, schema, validation) | AI |
| **Provider** | LLM backend (Ollama, Grok, OpenAI, Anthropic) | AI |
| **Model** | Trained or fine-tuned model artifact | AI |
| **Dataset** | Versioned training/evaluation data | AI |
| **Benchmark** | Frozen evaluation set with pass criteria | AI |
| **Evaluation Run** | Benchmark execution with metrics | AI |
| **Deployment** | Production model/capability configuration | AI |
| **Knowledge Base** | Reference vocabulary (skills, titles, degrees, etc.) | AI |
| **TOON Document** | Structured wire-format artifact | AI (format) / Domain (content) |
| **Inference Record** | Lineage log of a single AI execution | AI |

### Relationships

```
Capability ──uses──► Provider + Model + Prompt
Capability ──validates against──► Benchmark
Capability ──produces──► TOON Document
Capability ──references──► Knowledge Base (normalization)
Dataset ──feeds──► Model ──evaluated by──► Evaluation Run
Evaluation Run ──gates──► Deployment
Deployment ──serves──► Capability in production
Inference Record ──traces──► Capability + Provider + Model + Input
```

### Ownership

- **AI domain** owns all intelligence infrastructure.
- Domains consume AI output but own the business entities AI enriches.

Full AI platform specification: [04_AI_PLATFORM.md](04_AI_PLATFORM.md).

---

## Domain Interaction Rules

### Cross-domain communication

| Pattern | Rule | Example |
|---------|------|---------|
| **Read reference** | Domain A reads Domain B entity by ID | Hiring reads Application from Recruitment |
| **Event emission** | Domain A emits event; Domain B reacts | Hire Record triggers Employee creation |
| **AI enrichment** | AI domain produces artifact; owning domain persists | Resume parsing produces TOON; Recruitment stores it |
| **Analytics aggregation** | Analytics reads from all domains; never writes | Dashboard reads Application counts |
| **Direct mutation** | **Forbidden** across domain boundaries | Hiring must not UPDATE jobs table |

### Domain dependency graph

```
Administration ──supports──► all domains
AI ──enriches──► Recruitment, Hiring, Employee, Learning, Performance, Organization
Analytics ──reads──► all domains
Recruitment ──feeds──► Hiring ──feeds──► Employee
Employee ──feeds──► Learning, Performance
Organization ──structures──► Employee, Recruitment (job hierarchy)
```

---

## Cross-References

| Topic | Document |
|-------|----------|
| Conceptual entities and lifecycle | [06_DATA_MODEL.md](06_DATA_MODEL.md) |
| AI capabilities per domain | [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) |
| TOON document types | [05_TOON_ARCHITECTURE.md](05_TOON_ARCHITECTURE.md) |
| System components | [07_SYSTEM_ARCHITECTURE.md](07_SYSTEM_ARCHITECTURE.md) |
| Workflow sequences | [08_DATA_FLOWS.md](08_DATA_FLOWS.md) |
| Roadmap by domain | [11_PRODUCT_ROADMAP.md](11_PRODUCT_ROADMAP.md) |
