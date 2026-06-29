# Data Flows

**Document ID:** ARCH-08  
**Status:** Constitutional — defines canonical workflow sequences  
**Related:** [06_DATA_MODEL.md](06_DATA_MODEL.md) · [07_SYSTEM_ARCHITECTURE.md](07_SYSTEM_ARCHITECTURE.md) · [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md)

---

## Purpose

This document defines the **canonical data flows** for all platform workflows. Each flow is documented as a sequence diagram with actors, systems, data artifacts, and state transitions. These flows are the authoritative reference for API design, error handling, and async behavior.

---

## Flow Index

| # | Flow | Status | Domain |
|---|------|--------|--------|
| 1 | [Candidate Registration](#1-candidate-registration) | Active | Administration |
| 2 | [Resume Upload & Parsing](#2-resume-upload--parsing) | Active | Recruitment |
| 3 | [Bulk Resume Parsing](#3-bulk-resume-parsing) | Active | Recruitment |
| 4 | [Job Creation](#4-job-creation) | Active | Recruitment |
| 5 | [Application Submission](#5-application-submission) | Active | Recruitment |
| 6 | [Candidate Matching (ATS)](#6-candidate-matching-ats) | Active | Recruitment |
| 7 | [Interview Generation](#7-interview-generation) | Active | Hiring |
| 8 | [Offer Management](#8-offer-management) | Planned | Hiring |
| 9 | [Hiring Confirmation](#9-hiring-confirmation) | Planned | Hiring |
| 10 | [Employee Onboarding](#10-employee-onboarding) | Planned | Employee |
| 11 | [Performance Review](#11-performance-review) | Planned | Performance |
| 12 | [Learning Enrollment](#12-learning-enrollment) | Planned | Learning |
| 13 | [AI Copilot (HR Chat)](#13-ai-copilot-hr-chat) | Active | AI |

---

## 1. Candidate Registration

**Actors:** Candidate, Frontend, Backend, Email (SMTP)  
**Preconditions:** None  
**Postconditions:** Candidate Account in Active state with valid JWT

```mermaid
sequenceDiagram
    participant C as Candidate
    participant FE as Frontend
    participant BE as Backend
    participant DB as PostgreSQL
    participant EM as Email (SMTP)

    C->>FE: Enter email, phone, password
    FE->>BE: POST /api/candidate/signup
    BE->>BE: Validate password strength
    BE->>DB: Check email uniqueness
    BE->>DB: Insert candidate_signup (pending)
    BE->>DB: Insert CandidateAuth (OTP)
    BE->>EM: Send OTP email
    BE-->>FE: 201 Created (pending verification)
    FE-->>C: Show OTP verification screen

    C->>FE: Enter OTP code
    FE->>BE: POST /api/candidate/verify-otp
    BE->>DB: Validate OTP (match, not expired)
    BE->>DB: Activate candidate_signup
    BE->>DB: Delete CandidateAuth staging
    BE->>BE: Generate JWT (access + refresh)
    BE->>DB: Insert login_history (success)
    BE-->>FE: 200 OK (tokens + candidate profile)
    FE->>FE: Store tokens (localStorage)
    FE-->>C: Redirect to profile setup
```

**Error paths:**
- Duplicate email → 409 Conflict
- Invalid OTP → 400 Bad Request (3 attempts before lockout)
- Expired OTP → 400 with resend option
- Weak password → 400 with requirements

---

## 2. Resume Upload & Parsing

**Actors:** Candidate, Frontend, Backend, LLM Provider  
**Preconditions:** Authenticated candidate  
**Postconditions:** Parsed Resume (TOON) stored; profile updated  
**Capability:** `resume_parsing`

```mermaid
sequenceDiagram
    participant C as Candidate
    participant FE as Frontend
    participant BE as Backend
    participant DB as PostgreSQL
    participant LLM as LLM Provider

    C->>FE: Upload resume file (PDF/DOC/DOCX)
    FE->>BE: POST /api/parsing/resume (multipart)
    BE->>BE: Validate file (type, size)
    BE->>DB: Compute hash, check dedup
    BE->>DB: Insert raw_files (uuid, hash)
    BE->>BE: Extract text (parsing_utils)
    BE->>LLM: Send text + parse prompt
    LLM-->>BE: Structured output (JSON)
    BE->>BE: Validate output (schema)
    BE->>BE: Serialize to TOON (toon.py)
    BE->>BE: Validate TOON format
    BE->>DB: Insert parsed_resumes (toon, confidence, model_version)
    BE->>DB: Update candidate_profiles (from TOON projection)
    BE->>DB: Upsert candidate_education, experiences, certifications
    BE->>DB: Store resume binary in candidate_profiles
    BE-->>FE: 200 OK (parsed data + confidence)
    FE-->>C: Display parsed profile for review/edit
```

**Error paths:**
- Invalid file type → 400 Bad Request
- Text extraction failure → 422 with message
- LLM failure → Retry with fallback provider; if all fail → 503
- TOON validation failure → Retry; if persistent → 422 with partial data
- Duplicate file (same hash) → Reference existing parse

---

## 3. Bulk Resume Parsing

**Actors:** HR Admin, Frontend, Electron (optional), Backend, Bulk Parser  
**Preconditions:** Authenticated HR with admin access  
**Postconditions:** Batch results available for Excel download  
**Capability:** `bulk_resume_parsing`

```mermaid
sequenceDiagram
    participant HR as HR Admin
    participant FE as Frontend
    participant EL as Electron
    participant BE as Backend
    participant BP as Bulk Parser API
    participant DB as PostgreSQL

    HR->>FE: Open bulk parser page
    alt Desktop (Electron)
        FE->>EL: IPC: select folder
        EL-->>FE: Folder path
        FE->>BE: POST /api/admin/bulk-parse (folder path)
    else Web
        HR->>FE: Upload file batch (zip/files)
        FE->>BE: POST /api/admin/bulk-parse (multipart)
    end

    BE->>BE: Validate files, create batch job
    BE->>DB: Insert batch record (status: processing)

    alt External Bulk Parser available
        BE->>BP: POST batch (files/URLs)
        loop Poll progress
            FE->>BE: GET /api/admin/bulk-parse/status
            BE->>BP: GET progress
            BP-->>BE: Progress percentage
            BE-->>FE: Status update
        end
        BP-->>BE: Batch results
    else Local fallback
        loop For each file
            BE->>BE: Extract text
            BE->>BE: resume_parsing capability
            BE->>DB: Store individual parsed_resumes
        end
    end

    BE->>DB: Update batch record (status: complete)
    BE->>BE: Generate Excel export
    BE-->>FE: 200 OK (download URL)
    FE-->>HR: Download Excel with parsed results
```

**Error paths:**
- Individual file failure → Logged; batch continues; failure noted in export
- Batch timeout → Status: partial; completed files available
- External API unavailable → Automatic fallback to local processing

---

## 4. Job Creation

**Actors:** HR, Frontend, Backend, LLM Provider (optional)  
**Preconditions:** Authenticated HR  
**Postconditions:** Job created; optional Parsed JD stored  
**Capability:** `jd_parsing` (if JD document uploaded)

```mermaid
sequenceDiagram
    participant HR as HR Recruiter
    participant FE as Frontend
    participant BE as Backend
    participant DB as PostgreSQL
    participant LLM as LLM Provider

    HR->>FE: Fill job form (title, description, requirements)
    FE->>BE: POST /api/jobs

    opt JD document uploaded
        BE->>BE: Extract text from JD file
        BE->>LLM: Send text + JD parse prompt
        LLM-->>BE: Structured JD output
        BE->>BE: Serialize to TOON, validate
        BE->>DB: Insert raw_files + parsed_jds
    end

    BE->>DB: Insert jobs (jdid, title, company, location, salary, description, enabled)
    BE-->>FE: 201 Created (job details)
    FE-->>HR: Job listed on dashboard

    opt JD parsed
        FE-->>HR: Show parsed skills/requirements for review
    end
```

**State after creation:** Job → Active (enabled=true), visible to candidates.

---

## 5. Application Submission

**Actors:** Candidate, Frontend, Backend  
**Preconditions:** Authenticated candidate with completed profile and parsed resume  
**Postconditions:** Application created; ATS triggered asynchronously  
**Capability:** `candidate_matching` (triggered async)

```mermaid
sequenceDiagram
    participant C as Candidate
    participant FE as Frontend
    participant BE as Backend
    participant DB as PostgreSQL

    C->>FE: Click "Apply" on job listing
    FE->>BE: Pre-check: GET profile completion status
    BE->>DB: Check candidate_profiles.completed
    BE->>DB: Check parsed_resumes exists (latest)

    alt Profile incomplete or no parsed resume
        BE-->>FE: 400 (profile incomplete)
        FE-->>C: Redirect to profile completion
    end

    FE->>BE: POST /api/applications (job_id)
    BE->>DB: Check duplicate application
    BE->>DB: Insert applications (status: submitted)
    BE->>BE: Trigger ATS matching (background thread)
    BE-->>FE: 201 Created (application_id, status: submitted)
    FE-->>C: Application confirmation

    Note over BE: ATS runs asynchronously (see Flow 6)
```

**Business rules:**
- One application per candidate per job
- Profile must be marked complete
- Latest parsed resume used at time of apply

---

## 6. Candidate Matching (ATS)

**Actors:** Backend (background), LLM/ATS Service, n8n (optional)  
**Preconditions:** Application in submitted state; parsed resume and JD exist  
**Postconditions:** Application scored with match_score, shortlist tier, and reasoning  
**Capability:** `candidate_matching`

```mermaid
sequenceDiagram
    participant BE as Backend
    participant DB as PostgreSQL
    participant ATS as ATS Service
    participant LLM as LLM Provider
    participant N8N as n8n (optional)

    BE->>DB: Load application
    BE->>DB: Load latest parsed_resumes.toon
    BE->>DB: Load parsed_jds.toon for job

    alt n8n workflow configured
        BE->>N8N: Webhook trigger (resume TOON, JD TOON)
        N8N->>N8N: External workflow processing
        N8N->>BE: POST /api/applications/ats/result (callback)
        Note over N8N,BE: Secured with N8N_CALLBACK_SECRET
    else In-process ATS
        BE->>ATS: Score(resume_toon, jd_toon)
        ATS->>ATS: Weighted scoring (skills 60%, exp 25%, edu 10%, loc 5%)
        ATS->>ATS: Mandatory skills gate (60% min)
        ATS->>LLM: Generate reasoning (optional)
        LLM-->>ATS: Reasoning text
        ATS-->>BE: Score + breakdown + reasoning
    end

    BE->>BE: Determine shortlist tier (≥75 high, 60-74 medium, <60 low)
    BE->>DB: Update applications (match_score, shortlisted, ats_reasoning, ats_analysis, status: scored)
```

**Scoring weights:**
- Skills: 60% (mandatory 40%, preferred 20%)
- Experience: 25%
- Education: 10%
- Location: 5%

---

## 7. Interview Generation

**Actors:** HR, Frontend, Backend, LLM Provider  
**Preconditions:** Application with parsed resume and JD  
**Postconditions:** Interview questions generated (transient or stored)  
**Capability:** `interview_generation`

```mermaid
sequenceDiagram
    participant HR as HR Recruiter
    participant FE as Frontend
    participant BE as Backend
    participant LLM as LLM Provider
    participant DB as PostgreSQL

    HR->>FE: Request interview questions for application
    FE->>BE: POST /api/interview/generate (application_id)
    BE->>DB: Load parsed resume TOON + JD TOON
    BE->>LLM: Send resume + JD + interview prompt
    LLM-->>BE: JSON (questions, categories, criteria)
    BE->>BE: Validate output schema
    BE-->>FE: 200 OK (interview questions)
    FE-->>HR: Display questions for review/use

    Note over HR,FE: Future: store as Interview entity
```

---

## 8. Offer Management

**Status:** Planned  
**Domain:** Hiring  
**Capability:** `offer_intelligence` (future)

```mermaid
sequenceDiagram
    participant HR as HR Recruiter
    participant FE as Frontend
    participant BE as Backend
    participant AI as AI Runtime
    participant DB as PostgreSQL
    participant C as Candidate

    HR->>FE: Initiate offer for application
    FE->>BE: POST /api/offers (application_id)
    BE->>DB: Load application, resume TOON, JD TOON
    BE->>AI: offer_intelligence (profile, role, market data)
    AI-->>BE: Recommended range + draft letter
    BE->>DB: Insert offer (status: draft)
    BE-->>FE: Offer draft for HR review

    HR->>FE: Review and finalize offer
    FE->>BE: PUT /api/offers/{id} (final terms)
    BE->>DB: Update offer (status: extended)
    BE->>BE: Send offer notification to candidate
    BE-->>FE: 200 OK

    C->>FE: View and respond to offer
    FE->>BE: POST /api/offers/{id}/respond (accept/decline)
    BE->>DB: Update offer (status: accepted/declined)

    alt Accepted
        BE->>BE: Trigger hiring confirmation (Flow 9)
    end
```

---

## 9. Hiring Confirmation

**Status:** Planned  
**Domain:** Hiring → Employee  
**Trigger:** Offer accepted

```mermaid
sequenceDiagram
    participant BE as Backend
    participant DB as PostgreSQL
    participant AI as AI Runtime

    Note over BE: Triggered by offer acceptance (Flow 8)

    BE->>DB: Create hire_record (application, offer, start_date)
    BE->>DB: Update application (status: hired)
    BE->>DB: Create employee (from candidate profile)
    BE->>DB: Create employment_record (title, department, start_date)
    BE->>DB: Link employee.candidate_id → candidate_signup.cid

    BE->>AI: onboarding_intelligence (employee, role, department)
    AI-->>BE: Onboarding plan
    BE->>DB: Insert onboarding_plan

    BE->>BE: Emit hire_event (future event bus)
    Note over BE: Triggers Flow 10 (Onboarding)
```

---

## 10. Employee Onboarding

**Status:** Planned  
**Domain:** Employee  
**Capability:** `onboarding_intelligence`

```mermaid
sequenceDiagram
    participant E as Employee
    participant FE as Frontend
    participant BE as Backend
    participant DB as PostgreSQL
    participant AI as AI Runtime

    Note over BE: Triggered by hire confirmation (Flow 9)

    BE->>DB: Load onboarding_plan for employee
    BE-->>FE: Onboarding tasks (via employee portal)

    loop For each onboarding task
        E->>FE: Complete task (document upload, form, training)
        FE->>BE: PUT /api/onboarding/tasks/{id} (complete)
        BE->>DB: Update task status
        BE->>DB: Check all required tasks complete
    end

    BE->>DB: Update onboarding_plan (status: complete)
    BE->>DB: Update employee (status: active)

    opt AI-assigned learning
        BE->>AI: learning_intelligence (employee, role)
        AI-->>BE: Recommended courses
        BE->>DB: Create enrollments
        Note over E,BE: Triggers Flow 12 (Learning)
    end
```

---

## 11. Performance Review

**Status:** Planned  
**Domain:** Performance  
**Capability:** `performance_intelligence`

```mermaid
sequenceDiagram
    participant M as Manager
    participant E as Employee
    participant FE as Frontend
    participant BE as Backend
    participant AI as AI Runtime
    participant DB as PostgreSQL

    Note over BE: HR initiates review cycle
    BE->>DB: Create review_cycle (period, status: active)

    E->>FE: Complete self-assessment
    FE->>BE: POST /api/performance/self-assessment
    BE->>DB: Store self-assessment

    M->>FE: Write performance review
    FE->>BE: POST /api/performance/review/generate
    BE->>DB: Load employee goals, self-assessment, history
    BE->>AI: performance_intelligence (data, rubric)
    AI-->>BE: Review draft + bias check
    BE-->>FE: Draft for manager editing

    M->>FE: Finalize review
    FE->>BE: PUT /api/performance/review/{id}
    BE->>DB: Store finalized review

    BE->>AI: Suggest development plan
    AI-->>BE: Development recommendations
    BE->>DB: Create development_plan
    BE-->>FE: Review complete + development plan
```

---

## 12. Learning Enrollment

**Status:** Planned  
**Domain:** Learning  
**Capability:** `learning_intelligence`

```mermaid
sequenceDiagram
    participant E as Employee
    participant FE as Frontend
    participant BE as Backend
    participant AI as AI Runtime
    participant DB as PostgreSQL

    alt Self-enrollment
        E->>FE: Browse learning catalog
        FE->>BE: GET /api/learning/courses
        E->>FE: Enroll in course
        FE->>BE: POST /api/learning/enroll (course_id)
    else AI-recommended
        BE->>AI: learning_intelligence (employee skills, role requirements)
        AI-->>BE: Recommended learning path
        BE->>DB: Create enrollments from path
        BE-->>FE: Notify employee of assigned learning
    end

    BE->>DB: Insert enrollment (status: enrolled)
    BE-->>FE: 201 Created

    loop Course progress
        E->>FE: Complete module/assessment
        FE->>BE: PUT /api/learning/enrollments/{id}/progress
        BE->>DB: Update progress
    end

    BE->>DB: Update enrollment (status: completed)
    BE->>DB: Issue certification (if applicable)
    BE->>AI: Update skill profile
```

---

## 13. AI Copilot (HR Chat)

**Actors:** HR, Frontend, Backend, LLM Provider  
**Preconditions:** Authenticated HR  
**Postconditions:** Conversational response (transient)  
**Capability:** `hr_chat`

```mermaid
sequenceDiagram
    participant HR as HR Recruiter
    participant FE as Frontend
    participant BE as Backend
    participant LLM as LLM Provider

    HR->>FE: Type message in chat interface
    FE->>BE: POST /api/chat (message, history, context)

    BE->>BE: Sanitize user input (prompt injection defense)
    BE->>BE: Assemble system prompt (immutable) + context
    BE->>BE: Append conversation history
    BE->>BE: Append user message (sandboxed)

    BE->>LLM: Send assembled prompt
    LLM-->>BE: Response text

    BE->>BE: Sanitize output (PII check, content filter)
    BE-->>FE: 200 OK (response, no persistence)
    FE-->>HR: Display assistant response

    Note over HR,FE: Future: RAG over tenant data for contextual answers
```

**Security controls:**
- System prompt immutable at runtime
- User content sandboxed in template
- Output sanitized before display
- No conversation persistence (future: opt-in with audit)

---

## Cross-Flow Dependencies

```
Registration (1) ──► Profile + Resume Parse (2) ──► Application (5) ──► ATS (6)
                                                                          │
Job Creation (4) ─────────────────────────────────────────────────────────┘
                                                                          │
                                    Interview Gen (7) ◄───────────────────┘
                                          │
                                    Offer (8) ──► Hire (9) ──► Onboard (10)
                                                                    │
                                              Performance (11) ◄────┤
                                              Learning (12) ◄───────┘

Bulk Parse (3) ── independent (admin workflow)
HR Chat (13) ── independent (conversational)
```

---

## Cross-References

| Topic | Document |
|-------|----------|
| Entity lifecycle states | [06_DATA_MODEL.md](06_DATA_MODEL.md) |
| System components | [07_SYSTEM_ARCHITECTURE.md](07_SYSTEM_ARCHITECTURE.md) |
| AI capabilities | [03_CAPABILITY_MAP.md](03_CAPABILITY_MAP.md) |
| Security controls | [09_SECURITY_MODEL.md](09_SECURITY_MODEL.md) |
| API catalog | `docs/TECHNICAL_DOCUMENTATION.md` |
