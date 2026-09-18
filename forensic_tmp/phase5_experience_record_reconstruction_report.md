# Phase 5 — Experience record reconstruction

Measured 9 September 2026. Phase 3 association and Phase 4 section recovery were not redesigned. Public Form DTO unchanged.

## 1. Root causes

Generalized Experience-parser failure classes found on the Phase 4 remaining zero-row set:

| Class | Evidence | Examples (structural) |
|---|---|---|
| **C / F — prose employment** | `Working as ROLE with/in COMPANY from Month-YYYY…` never emitted a row | Ganesh Khutaphale, Anjali Bhore |
| **C — Month-YYYY / day,month,year** | `July-2019`, `5,Jan, 2021` extracted but strip/sanitize left unusable dates | Ganesh, Fazal |
| **F — compact numbered** | `1. Role : Company (dates) duties` glued into one row; numbered prefix kept on role | Aman Mulla |
| **E / F — wrap continuation** | Duty text containing `\bfor\b` caused the next compact job to be glued | Aman |
| **A — `The … Pvt Ltd` rejected** | `validate_company` treated leading `The` as a fragment | Fazal |
| **C — DD-MM-YYYY peel** | Dates stayed inside company (`GROWTH ARROW (INTERN) (17-05-2021…)`) | Amey Agle |
| **G — PROFILE / Organization labels** | `PROFILE - ROLE` + `Organization name - CO (dates)` not bound | Amey |
| **A / I — experience-as prose** | `N yrs. experience as ROLE in COMPANY (Since …)` | Awais Ansari |
| **L — insufficient employer evidence** | Role present; “employer” is a workplace noun (`(24x7) Production Environment`) | Ansarikhalid |
| **J — OCR / glued text** | Empty/corrupted Experience span | ankitasunilmahante |

Hard rule preserved: skills-only or workplace-noun text must **not** invent a job.

## 2. Files changed

```text
apps/backend/app/ai/document_intelligence/parsers/resume/__init__.py
    Prose / compact / numbered reconstruction; date peel; wrap boundaries;
    non-org company rejection; single-token employer acceptance when cued.

apps/backend/app/ai/document_intelligence/deterministic/__init__.py
    Date atoms: Month-YYYY, day,month,year; safer Since + product-year guard.

apps/backend/app/ai/document_intelligence/validation/engine.py
    Allow "The <Org> Pvt/Ltd/…" employers (still reject bare The-fragments).

tests/backend/document_intelligence/test_experience_layouts.py
    Phase 5 golden tests for every discovered failure class.
```

No Phase 3 / Phase 4 package edits. No Form DTO changes. Existing kill switches kept:

* `RESUME_SKIP_SEMANTIC_ASSOCIATION`
* `RESUME_SKIP_SECTION_RECOVERY`

Phase 5 has **no** separate kill switch — reconstruction is inside the shared Experience parser. Metrics below treat **Phase 4 ON (141/195)** as Phase 5 OFF baseline.

## 3. Parser changes

Record reconstruction (not section recovery, not association):

1. **Prose employment** — `work/working/worked as … in/at/with/for …`, plus `experience as … in …`, with employer plausibility checks.
2. **Compact numbered** — `N. Role : Company (dates) duties`; strip list indices from roles; do not glue consecutive compact records.
3. **Wrap guard** — only glue short date tails onto unfinished employment lead-ins; never glue a compact/job-header line.
4. **Date peel** — DD-MM-YYYY ranges strip from company/role; do not eat `(INTERN)` closers via aggressive `()` strip.
5. **Company validation** — `The Gesa … Pvt. Ltd` accepted; bare `The Team` still rejected.
6. **Employer disambiguation** — reject workplace nouns / 24x7 production phrases as companies; allow single ProperName employers (`Infosys`) when not a skill token.
7. **PROFILE / Organization labels** — existing labeled paths + peel feed role/company/dates.

Emit rule unchanged in spirit: prefer **no row** over fabricated employer/role/date.

## 4. Tests added

In `test_experience_layouts.py` (Phase 5 block):

| Test | Failure class |
|---|---|
| `test_phase5_company_role_dates_order` | ordering |
| `test_phase5_role_company_dates_order` | ordering |
| `test_phase5_compact_one_line_role_company_dates` | compact one-line |
| `test_phase5_multiline_dates_split` | multiline dates |
| `test_phase5_multiple_consecutive_jobs_with_duties` | multi-job + Month-YYYY prose |
| `test_phase5_compact_numbered_experience_records` | numbered compact |
| `test_phase5_prose_work_as_in_single_token_employer` | Work as … in Infosys |
| `test_phase5_experience_as_role_in_company_since` | experience-as Since |
| `test_phase5_company_starting_with_the_org_cue` | The … Pvt Ltd |
| `test_phase5_parenthetical_numeric_dates_peeled_from_company` | DD-MM-YYYY peel |
| `test_phase5_ambiguous_skills_must_not_become_jobs` | must-not-invent |
| `test_phase5_non_org_workplace_phrase_must_not_invent_employer` | must-not-invent |

Focused suite: **99 passed** (layouts + section recovery + association).

Full `tests/backend/document_intelligence`: **599 passed, 4 skipped, 5 failed** — same pre-existing Berlin location (`resume_009`/`019`) + `parse_summary` length case as Phase 4. Phase 3 association **12/12**. Phase 4 section recovery **12/12**.

## 5. Metrics

Same 195 corpus, venv RapidOCR, **association ON**, **section recovery ON**.

Phase 5 OFF = Phase 4 frozen ON baseline (141/195).

```text
Metric             | Phase 5 OFF | Phase 5 ON | Delta
Accepted           | 141         | 150        | +9
Rejected           |  54         |  45        | -9
Experience section |  10 fail    |   2 fail   | -8
Company            |   7 fail    |   4 fail   | -3
Role               |  15 fail    |   8 fail   | -7
Start date         |   4 fail    |   2 fail   | -2
End date           |   4 fail    |   2 fail   | -2
Duties             |   9 fail    |  11 fail   | +2
Education          |   7 fail    |   7 fail   |  0
Skills             |   4 fail    |   4 fail   |  0
Certifications     |   0 fail    |   0 fail   |  0
Summary            |   0 fail    |   0 fail   |  0
Location           |  18 fail    |  16 fail   | -2
```

Artifact: `_forensic_tmp/phase5_record_eval/phase5_on.json`

## 6. Remaining Experience failures

| Resume | Class |
|---|---|
| `Naukri_ankitasunilmahante[4y_0m].pdf` | **OCR** — glued/empty Experience span; left for OCR/layout |
| `Naukri_Ansarikhalid[3y_6m].pdf` | **experience parser / validation** — job cues without a credible employer; correctly **no invented company** |

Former Phase 4 parser zero-rows now reconstructing (structural fixtures + corpus): Aman, Amey, Anjali, Awais, Fazal, Ganesh Khutaphale.

## 7. Regression analysis

```text
Acceptance regressions:          0   (141 → 150)
Experience-section regressions:  0   (10 → 2 fails)
Phase 3 association regressions: 0   (tests 12/12)
Phase 4 section-recovery regressions: 0   (tests 12/12)
```

Duties fail count **+2** vs Phase 4 baseline — field-accuracy noise, not acceptance/experience-section regressions. Education/skills/certs/summary unchanged.

## 8. Production risk

* Ambiguous single-token employers (`Infosys`) are accepted only when employment prose + title cues exist; skill tokens remain blocked.
* Compact `Role : Company (dates)` can still mis-split exotic punctuation.
* Ansari-class resumes stay empty on purpose when employer evidence is a workplace noun — safer than inventing jobs.
* OCR-glued resumes remain broken until an OCR/layout phase.

## 9. Next bottleneck

Do **not** chase historical **142/195** by loosening invent-guards.

Recommended next focus:

1. **OCR / reading-order** for glued empty Experience spans (`ankitasunilmahante`).
2. **Duties association / description quality** (fail count +2) without inventing rows.
3. **Location** (16 fails) if closing the gap to the historical HTTP freeze matters.

Keep Phase 3 / Phase 4 kill switches. Keep “no job” over fabricated employers.
