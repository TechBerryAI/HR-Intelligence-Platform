# Phase 4 — Experience section recovery & reading order

Measured 9 September 2026. Section detection, Experience parser, OCR, and Phase 3 association were not rewritten.

## A. Files changed

```text
apps/backend/app/ai/document_intelligence/section_recovery/__init__.py
apps/backend/app/ai/document_intelligence/section_recovery/evidence.py
apps/backend/app/ai/document_intelligence/pipeline.py
tests/backend/document_intelligence/test_section_recovery.py
```

Kill switch: `RESUME_SKIP_SECTION_RECOVERY=true` (default: recovery on).
Phase 3 kill switch `RESUME_SKIP_SEMANTIC_ASSOCIATION` is unchanged.

## B. Exact recovery architecture

```text
PDF/OCR
→ text/layout
→ detect_sections()                    # unchanged
→ recover_resume_sections()            # NEW
→ existing section parsers
→ coverage recovery
→ semantic association                 # frozen
→ sanitize
→ Form DTO
```

Recovery rebinds **section ownership** only. It does not create company/role/date records.

If evidence is ambiguous, the blob stays Unclassified (or on its original label).

Explainable report is stored on `profile.field_meta['section_recovery']` (internal; not on the Form DTO).

## C. Recovery rules / evidence

Trigger: Experience missing or existing Experience body is weak (`< 80` chars **and** ownership score `< 0.45`). Strong existing Experience spans are left alone.

Donors (only when Experience heading exists in the document or a nested heading maps to Experience via the existing header taxonomy):

* Unclassified, Summary, Projects, Certifications, Languages, Skills

A donor is moved only if:

* employment ownership score ≥ 0.45
* at least two positive signals (or an explicit Experience heading)
* employment score beats the donor’s native-label score

Signals: `experience_heading`, `employment_date_density`, `role_pattern_density`, `employer_pattern_density`, `duty_density`, `paired_title_date`, `record_structure`, `repeated_record_format`, `document_order`.

Negative signals: certification-like, education-like, skill-list-like blobs without employment structure.

Split paths:

* Nested heading (`A. Work Experience:` after enum-prefix strip → existing `normalize_section_header`)
* Summary-prose prefix then employment-record start
* Contiguous employment windows inside a donor (duty lines included; other section headings stop the window)

No company names, no resume filenames, no hardcoded coordinates.

## D. New tests

`tests/backend/document_intelligence/test_section_recovery.py`

| Case | What it asserts |
|---|---|
| 1 | Experience heading + body recovered from Unclassified/Skills dump |
| 2 | Nested Experience heading inside Summary; summary prose stays Summary |
| 3 | Body recovered from Projects |
| 4 | Body recovered from Certifications (two-column header crumbs) |
| 5 | Two-column: Experience header then Certifications then jobs |
| 6 | Compact valid Experience is **not** rewritten |
| 7 | Multiple job records in the recovered column |
| 8 | Experience beside Skills/Languages |
| 9 | OCR-interleaved leftover after a short Skills span |
| 10 | No Experience heading → no recovery (jobs stay Unclassified) |
| report | Internal evidence list |
| kill switch | `RESUME_SKIP_SECTION_RECOVERY` skips the layer |

DI suite with recovery on: **587 passed, 4 skipped, 5 failed**. The 5 failures are the pre-existing Berlin location + `parse_summary` length cases. Association tests **12/12**. Recovery tests **12/12**. Section-detection tests **unchanged**.

## E. Before vs after metrics

Same 195 corpus, venv RapidOCR, **association ON** for both sides.

```text
Metric             | Recovery OFF | Recovery ON | Delta
Accepted           | 132          | 141         | +9
Rejected           |  63          |  54         | -9
Experience section |  17 fail     |  10 fail    | -7
Company            |  12 fail     |   7 fail    | -5
Role               |  21 fail     |  15 fail    | -6
Start date         |   5 fail     |   4 fail    | -1
End date           |   5 fail     |   4 fail    | -1
Duties             |  13 fail     |   9 fail    | -4
Education          |   7 fail     |   7 fail    |  0
Certifications     |   0 fail     |   0 fail    |  0
Skills             |   4 fail     |   4 fail    |  0
Summary            |   0 fail     |   0 fail    |  0
Location           |  18 fail     |  18 fail    |  0
Acceptance regress |  —           |   0         |
Experience regress |  —           |   0         |
```

## F. Recovered resumes (acceptance fail → pass)

```text
Naukri_AdarshJaiprakashSingh[1y_0m].pdf
Naukri_AniketNavnathPakhare[0y_0m].pdf
Naukri_AnshikKushwah[1y_6m].docx
Naukri_AnushkaGohil[4y_0m] - Copy.pdf
Naukri_BhimRaj[3y_5m].pdf
Naukri_DeepakPravinJadhav[3y_0m].pdf
Naukri_DevendraDilipJaiswal[2y_7m].docx
Naukri_DipeshNarkar[1y_3m].pdf
Naukri_GaneshRameshGaonkar[7y_0m].pdf
```

Experience-section pass→fail: **none**.

Experience-section fail→pass (may already have been accepted on other fields):

```text
ABRARRAFIKKUMBHARLIKAR (jobs recovered; still rejected on another field)
AniketNavnathPakhare
AnushkaGohil
DeepakPravinJadhav
DevendraDilipJaiswal
DipeshNarkar
GaneshRameshGaonkar
```

Devashish Panchmatia: Experience span recovered (~2232 chars, 7 job rows, accepted). It was already accepted with a thin recovered row under Phase 3.1; Phase 4 restored section ownership rather than inventing jobs in association.

## G. Regressions

None on acceptance. None on the experience section field.

Education, skills, summary, certifications, and location fail counts are unchanged.

## H. Remaining Experience failures

Ten experience-section fails remain (recovery ON). Inventory classification:

| Resume | After recovery | Class |
|---|---|---|
| Aman Mulla docx/pdf | span ~280 chars, 0 jobs | existing parser |
| Amey Agle | span ~340, 0 jobs | existing parser / reading order |
| Anjali Bhore docx | span ~533, 0 jobs (PDF twin passes) | existing parser |
| ankitasunilmahante | span 0 (glued OCR text) | OCR |
| Ansarikhalid | span ~827, 0 jobs | existing parser |
| Awais Ansari | span ~1302, 0 jobs | existing parser |
| Fazal Shaikh | span ~1989, 0 jobs | existing parser |
| Ganesh Khutaphale | span ~194, 0 jobs | existing parser |
| ABRAR (exp pass, still rejected) | 5 jobs | other field / existing parser |

These are **not** association bugs. Recovery often delivered a real Experience span; `parse_experience` still emitted zero rows.

## I. Historical 142 comparison

```text
Frozen HTTP snapshot:     142 / 195
Phase 3.1 venv OCR:       132 / 195 (association on, recovery off)
Phase 4 venv OCR:         141 / 195 (association on, recovery on)
```

**142 is not reproduced.** Location is still 18 fails (not an open miss on the freeze). Role is 15 fails vs freeze remaining 6. The last step from 141 → 142 is not claimed.

## J. Recommendation for next phase

Do **not** expand association or add resume-specific rules.

Next bottleneck is the **existing Experience parser** on recovered-but-empty spans (Aman, Amey, Anjali docx, Ansari, Awais, Fazal, Khutaphale): the section is now owned, records are not built.

Separately: location allowlist / OCR page failures vs the historical 142 snapshot.

Keep recovery conservative. Keep both kill switches.
