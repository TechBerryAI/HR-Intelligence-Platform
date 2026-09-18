# Phase 5.1 — Duties accuracy + remaining Experience failure audit

**Diagnostic only.** No Phase 3 / Phase 4 / Phase 5 rewrites. No Education changes. Measured 9 September 2026.

Artifacts:

* `_forensic_tmp/phase5_1_duties_audit/duties_on.json`
* `_forensic_tmp/phase5_1_duties_audit/duties_off.json`
* `_forensic_tmp/phase5_1_duties_audit/duties_paired.json`
* `_forensic_tmp/phase5_1_duties_audit/duties_stage_probe.json`
* `_forensic_tmp/phase5_1_duties_audit/duty_span_dumps.json`
* `_forensic_tmp/phase5_1_duties_audit/experience_remaining_trace.json`
* `forensic_tmp/phase5_1_duty_goldens/*.json`

---

## Scorer definition (critical)

Public eval marks `description` as:

* **pass** if the **first** experience row has a non-empty `description`
* **fail** if experience rows exist **and** the extract has duty cues (`responsible for|developed|managed|…`) **and** the first description is empty

It does **not** require duties on every job, and it does **not** check whether duties are on the correct job.

---

## A. Duties failure table (Phase 5 ON — 11)

| Resume | Actual first-job duties | Duties elsewhere on form? | Dominant class | First incorrect stage |
|---|---|---|---|---|
| AmitKumarPradhan | empty (Sociodigit ×2) | no | **A + K** | Experience parser: span has VeriTech + 5 bullets; `parse_experience` emits 0; coverage invents thin rows |
| ArchanaTambe | empty | no | **L** (then A) | Source Experience is header-only; duty cues elsewhere fire scorer |
| AshokPandi | empty ×3 | no | **J / A** | No Experience section; coverage employers without duties |
| Ashwanth | empty ×3 | no | **L** (then A) | Title+date rows only; no duty bullets in extract |
| BhargaviDadi | empty | no | **J / E** | Experience heading empty; duties live in Preamble/Project Profile |
| BipinShivkumarDubey | empty (Virtusa) | yes on job[2] (misassociated prose) | **C/D + L** | Record/order + first-job scorer; employment prose attached under wrong company |
| ChiranjitSarkar | empty | no | **E / J** | Project duties labeled under Education/Project; thin Experience |
| DeelipuDoppalapudi | empty | no | **J / A** | Experience = employment prose only; duty line in Summary/Projects |
| Deepshikhachak | empty | no | **J / A** | Experience bullet is employment sentence; real bullets in Summary |
| GaneshWKhuaphale | empty ×2 | no | **L exposure + A** | Phase 5 built jobs correctly; no duty bullets in Experience (one project line outside) |
| GangarajuD | empty ×2 | no | **L** (then A) | Compact headers only; no duty bullets in extract |

Quality buckets (semantic, not whitespace):

```text
Duty exact/usable in Experience span but missing on form:     1  (Amit)
Duty present on form but misassociated / wrong job:           1  (Bipin)
Duty outside Experience (section boundary):                   4  (Bhargavi, Chiranjit, Deelipu, Deepshikha)
Resume has no real duty bullets (scorer still fails):         4  (Archana, Ashwanth, Gangaraju, Ashok≈)
Phase 5 exposure (jobs now exist → description scored):       1  (Ganesh) + Bipin scorer effect
OCR-corrupted duties among the 11:                            0
```

---

## B. Phase 5 impact on Duties

Paired run (association ON, section recovery ON):

* **OFF** = HEAD resume/deterministic/validation modules (pre–Phase 5 reconstruction) + Phase 3/4 layers
* **ON** = current Phase 5 parser

```text
Phase 5 OFF: 9 description fails, acceptable 141, experience fails 10
Phase 5 ON:  11 description fails, acceptable 150, experience fails 2
```

| Set | Files |
|---|---|
| Unchanged fails (both) | Amit, Archana, Ashok, Ashwanth, Bhargavi, Chiranjit, Deelipu, Deepshikha, Gangaraju (**9**) |
| Fixed by Phase 5 | **none** |
| New on ON only | **BipinShivkumarDubey**, **GaneshWKhuaphale** |

Exact reason for **9 → 11**:

1. **GaneshWKhuaphale** — Phase 5 reconstruction created 2 valid jobs (was an Experience zero-row / not description-scored the same way). Experience now passes; description fails because the Experience span has employment prose only (no duty bullets). **Scoring exposure**, not duty deletion.
2. **BipinShivkumarDubey** — jobs exist with duties on a **later** row only; first row description empty → scorer fail. Marked `scoring_effect_candidate`. Employment prose also lands under the wrong company (**misassociation**), but the metric flip is first-job emptiness.

Phase 5 did **not** remove duties from the prior 9. It also did **not** improve them.

---

## C. First incorrect pipeline stage (representatives)

### AmitKumarPradhan (parser / record)

```text
OCR: OK
Section detection: Experience present (~612 chars) with VeriTech + Project bullets
Section recovery: no change needed
Experience parser: INCORRECT — 0 jobs from span despite bullets
Coverage: invents Sociodigit rows without duties
Association / sanitize: N/A on duties
DTO: empty descriptions → scorer fail
```

### BhargaviDadi (section ownership)

```text
OCR: OK
Section detection: Experience ≈ empty heading; duties in Preamble/Project Profile
Section recovery: did not move duty block into Experience
Experience parser: nothing to attach
DTO: company/role from coverage, duties empty
```

### BipinShivkumarDubey (record order + scorer)

```text
OCR: OK
Experience span: Role skill-lines + “Working/Worked as …” employment prose
Parser: multiple jobs
Duties/prose: attached under Clover (wrong) while Virtusa/Wipro first rows empty
Scorer: fail because first description empty (even though some description exists later)
```

### GaneshWKhuaphale (exposure)

```text
OCR: OK
Experience span: two employment sentences (Wipro, DXC) — Phase 5 correct
Duties: not in Experience (optional project line under Projects)
Scorer: fail — jobs exist + duty cues in extract + first description empty
```

### Headers-only (Archana / Ashwanth / Gangaraju)

```text
First wrong stage: SOURCE / SCORER EXPECTATION
Resume Experience has no duty bullets; public scorer still fails on global duty cues.
```

---

## D. Remaining Experience failures

### ankitasunilmahante — **OCR / layout**

Evidence:

* **No Experience section** after detection (Career content dumped into Summary).
* **75+ glued lines** (`ContactNo.7304620028`, `RecruitingAgentslikehousewife`, letter-spaced `K e y D e l i v e r a b l e s`).
* Words merged; event crumbs (`1Day`, `CorporateEvent`) look like fake employers.
* Correct representation needs de-glued tokens, real line breaks, and an Experience heading/body before any parser work.

**Do not** add Experience-parser hacks for this resume.

### Ansarikhalid — **valid no-invention**

Experience span (~235 chars):

```text
Working as an Oracle Database Administrator in (24x7) Production Environment. …
```

* Role evidence: yes (Oracle DBA)
* Employer evidence: **no** (workplace noun, not an org)
* Dates: none in span
* `parse_experience` → `[]` (correct)

Keep refusing to invent a company. Not an automatic defect.

---

## E. Regression status

Relative to Phase 4 / Phase 5 acceptance benchmarks:

```text
Acceptance regression: 0          (141 → 150 under Phase 5 ON)
Experience regression: 0          (10 → 2)
Phase 3 regression: 0             (frozen; not modified)
Phase 4 regression: 0             (frozen; not modified)
```

Duties **count** worsened +2 for the reasons in §B (exposure + first-job scorer), not because prior duties were stripped.

---

## F. Recommended next implementation phase

**Do not start Education yet** as the primary duties fix — Education’s 7 fails are independent.

Recommended order after this audit:

1. **Targeted duties / record attachment (narrow)** — highest value true bug: **AmitKumarPradhan**-class (internship / `Role | Company` + project `Responsibility:` bullets inside Experience). Optionally fix **Bipin** first-job empty + misassociated employment prose. Do **not** rewrite Phase 5 wholesale.
2. **Section ownership for duty blocks** — Bhargavi / Deepshikha / Deelipu / Chiranjit: duties live outside Experience. Prefer a **careful** Phase 4.1 / duty-block recovery **only if** evidence is strong; do not reopen Phase 4 casually.
3. **Scorer hygiene (eval-only)** — consider scoring “any job has duties” or “duties on the job that owns them,” and treat header-only resumes without duty bullets as `n/a`. This would remove false Duties fails (Archana, Ashwanth, Gangaraju, Ganesh exposure) without parser changes.
4. **OCR / layout phase** — ankitasunilmahante (and similar glued extracts). Separate from Experience parser.
5. **Education reconstruction** — still a separate bottleneck (7 fails); start only after duties/OCR priority is chosen.

### Outcome summary

| Option | Verdict |
|---|---|
| No change required | **No** — at least Amit (and optionally Bipin) are real parser/attachment defects |
| Duties parser improvement | **Yes, narrow** — project/internship duty attachment + misassociated prose |
| OCR/layout phase | **Yes, separate** — ankitasunilmahante |
| Education reconstruction | **Later, independent** |
| Rewrite Phase 5 / touch Phase 3 | **No** |

---

## Phase 5 over-aggressive duty handling check

Inspected Phase 5 paths against these 11:

* Did **not** find Phase 5 stripping bullets from the prior 9 fails.
* **Did** find wrap/record reconstruction creating jobs where none existed (Ganesh) → description becomes scoreable.
* **Did** find employment-prose lines acting as both headers and duty text (Bipin) → wrong-job attachment + empty first row.
* Compact/prose paths do not consume the next record in the Ganesh case; duties were simply never in the span.

---

## Hard constraints followed

No Phase 3/4/5 rewrite, no Education edits, no invented employers, no chase of historical 142, no LLM-fabricated duties.
