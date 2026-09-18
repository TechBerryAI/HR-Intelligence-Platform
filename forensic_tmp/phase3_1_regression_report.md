# Phase 3.1 — Semantic association regression investigation

Measured 9 September 2026. Parser extractors, OCR, and section detection were not rewritten. Two-column handling was not implemented.

## A. Phase 3 regression table

### A1. Original 16 → 17 (system Python, RapidOCR missing, before conservative guards)

This is the measurement that produced the experience-section regression.

```text
Metric              | OFF | ON  | Delta
Accepted            | 130 | 131 | +1
Rejected            |  65 |  64 | -1
Experience section  |  16 |  17 | +1 fail
Company             |  13 |  11 | -2 fail
Role                |  20 |  20 |  0
Start date          |   5 |   5 |  0
End date            |   5 |   5 |  0 (pass 149 → 148; n/a +1)
Duties              |  15 |  14 | -1 fail
Education           |   7 |   7 |  0
Certifications      |   0 |   0 |  0
Skills              |   4 |   4 |  0
Summary             |   0 |   0 |  0
Location            |  17 |  17 |  0
```

Acceptance improved on three resumes and regressed on two (net +1). The experience-section fail is one resume (below).

### A2. Apples-to-apples after OCR venv + conservative association guards

Same 195-file corpus. `apps/backend/venv` Python. `rapidocr_onnxruntime` imports. Extract once, parse twice (`RESUME_SKIP_SEMANTIC_ASSOCIATION=true` vs `false`).

```text
Metric              | OFF | ON  | Delta
Accepted            | 129 | 132 | +3
Rejected            |  66 |  63 | -3
Experience section  |  17 |  17 |  0
Company             |  14 |  12 | -2 fail
Role                |  21 |  21 |  0
Start date          |   5 |   5 |  0 (pass 170 → 171)
End date            |   5 |   5 |  0
Duties              |  15 |  13 | -2 fail
Education           |   7 |   7 |  0
Certifications      |   0 |   0 |  0
Skills              |   4 |   4 |  0
Summary             |   0 |   0 |  0
Location            |  18 |  18 |  0
```

Experience pass→fail after the guards: **none**. Acceptance pass→fail: **none**.

Frozen historical HTTP **142/195 was not reproduced** (see D).

## B. Experience regression details (the 16 → 17)

Exactly one resume: **`Naukri_DevashishPanchmatia[6y_0m].pdf`**.

```text
Resume: Naukri_DevashishPanchmatia[6y_0m].pdf
Expected (from the PDF, not the scorer): Oterra / Courtyard by Marriott / Aditya Birla
         jobs live in Unclassified, not in the Experience span.

Association OFF:
  1 job row
  company=""
  role="Associate (Sales and Marketing)"
  start=2023-11  end=2024-08
  duties present (Oterra-period bullets)
  Class C role_without_company_no_company_cue
  experience field PASS
  acceptable=True

Association ON (before 3.1 guards):
  0 job rows
  Class B job_cues_in_extract_but_no_rows
  experience field FAIL
  acceptable=False

Changed field: entire experience record deleted (not a field rewrite).
Root cause: thin Experience span (~10–12 chars) + full-text fallback
            captured the Summary body + document-order block 0
            filled company="Summary" + sanitize_candidate_profile dropped the row.
Association rule responsible: associate_experience empty-company fill
            + _fallback_section(kind=experience)
            + document-order _best_block_index fallback.
Why the rule changed the value: empty company was filled from junk block 0
            whose first header line was the word "Summary".
Whether that change is correct according to the resume: NO.
            "Summary" is not an employer. The real employers are still in
            Unclassified (two-column / sidebar reading order).

Classification: TRUE ASSOCIATION BUG
```

Second acceptance regression (experience *section* still passed):

```text
Resume: Naukri_AnantVijaySharma[16y_0m].pdf
Expected: two jobs (parser already inverted first company/role as DEVOPS & QE / PROJECT LEAD).
Association OFF: 2 jobs; first description kept ("FIS Global Pvt Ltd…").
Association ON (before 3.1 guards): 2 jobs; first description wiped to empty.
Changed field: duties / description on job 0.
Root cause: CROSS_RECORD_LEAK strip with empty owning-block duty_text
            cleared the only description.
Association rule responsible: _rebind_entry leaked-description wipe.
Whether the wipe is correct: NO. The inverted company/role is an existing
            parser issue; emptying duties is an association bug.

Classification: TRUE ASSOCIATION BUG (duties) + EXISTING PARSER ISSUE (company/role pairing)
```

Both bugs are closed by conservative guards (do not use experience fallback; skip thin Experience spans; no document-order block fallback; do not fill company from section headings; never wipe a filled description to empty). Post-fix spot check: both files experience PASS, acceptable True, OFF and ON.

## C. Experience root cause (why 16 → 17)

The scorer marks `experience` fail when the extract has job cues but the form has **zero** experience rows (`job_cues_in_extract_but_no_rows`).

Devashish already had a weak Experience **section** (header only). Association OFF kept the one recovered job (empty company, Class C — still acceptable). Association ON rebound that empty company to `"Summary"` from the fallback Summary body. Sanitization then dropped the row → 0 jobs → section fail.

That is **not** a valid association change that merely exposed a weak section check. The value `"Summary"` is unsupported by the resume as an employer. The weak section is real (jobs are in Unclassified) and remains a Phase 4/5 layout problem; association must leave the existing row alone when the Experience span is empty.

After the guards, OCR-enabled paired eval: **experience 17 = 17**, **exp_regressed = []**.

## D. OCR status

```text
OCR dependency:          rapidocr-onnxruntime  (Python < 3.13)
                         rapidocr + onnxruntime (Python >= 3.13)
Expected version:        rapidocr-onnxruntime>=1.3.24 from apps/backend/requirements.txt
                         Python 3.10–3.12 (3.11 recommended). Tesseract is optional fallback only.
Current status:          System python (C:\Program Files\Python312\python.exe): RapidOCR NOT importable.
                         Backend venv (apps/backend/venv): rapidocr_onnxruntime imports OK.
Why OCR is unavailable
on system python:        Packages were never installed into that interpreter.
                         docs/DEVELOPMENT.md and node start.js are fail-closed on the venv.
How 142/195 was enabled: HTTP Apply eval (POST /api/parse/resume/public) with in-process
                         parity 195/195, using the backend venv RapidOCR path.
                         Freeze remaining misses did not include location as an open field.
Minimal change to
reproduce the baseline:  Run the 195 eval with apps/backend/venv (already the intended setup).
                         Do not pip-install into system Python.
```

venv + RapidOCR still scored **OFF 129 / ON 132**, not 142. Remaining gap vs freeze:

- Location 18 fails here; freeze did not list location among remaining misses.
- Role 21 fails here; freeze remaining role misses were **6**.
- Some pages still log `RapidOCR returned empty text` or `no OCR engine available` (page workers / empty OCR). Tesseract is not on PATH.
- Freeze was HTTP + a frozen parser snapshot. This run is in-process on current code (Phase 3 present).

**Do not treat 129 vs 142 as a Phase 3 regression.** Association OFF with RapidOCR is 129. The 142 number is historical HTTP, not this environment.

CI already probes `import rapidocr_onnxruntime` (`.github/workflows/ci.yml`).

## E. Apples-to-apples baseline (venv RapidOCR)

```text
Association OFF: 129 / 195
Association ON:  132 / 195
Delta:           +3 accepted, 0 experience-section regressions, 0 acceptance regressions
```

Improved (fail → pass acceptance):

- `Naukri_AkankshaJha[6y_6m] - Copy.pdf` (company fail → pass)
- `Naukri_AnujSushantHegishte[1y_6m].pdf` (company fail → pass)
- `Naukri_BipinShivkumarDubey[7y_0m].docx` (duties fail → pass)

Unchanged: 192 resumes at the acceptance bit. Regressed: none after the 3.1 guards.

## F. Field-level impact (venv OCR, OFF → ON)

```text
Company:        IMPROVED  (14 → 12 fails). Two empty companies rebound from owning blocks.
Role:           UNCHANGED (21 fails). Bottleneck is parser/layout, not this layer.
Dates:          NEUTRAL   (start +1 pass from n/a; end unchanged). No date moves between jobs on the regression cases.
Duties:         IMPROVED  (15 → 13 fails). Leak repair on some rows; wipe-to-empty bug fixed.
Education:      UNCHANGED fails (7). Many n/a → pass on degree/institution (fill from owning block, not new rows).
Certification:  UNCHANGED (0 fails). Drops skill-like names; does not invent titles from tokens.
Skills:         UNCHANGED (4 fails).
Summary:        UNCHANGED (0 fails). Contact stripping only.
Experience:     UNCHANGED (17 fails) after the Devashish fix. Those 17 are empty-row / compact layouts.
Location:       UNCHANGED (18 fails). OCR/layout, not association.
```

No-invention audit (code): experience never appends jobs; education never inserts rows and clears generic unsupported degrees; certs may **reclassify** an extracted skill that already has credential evidence (`certified` / PMP-class abbrev) — not infer “AWS Certified” from “AWS”; summary only strips/clears.

Idempotence: `parse → association → association` matches `parse → association` on all three golden fixtures (`two_jobs_education`, `university_only_no_degree`, `summary_certs_boundary`).

## G. Two-column / compact failure inventory (do not fix here)

All of these fail `job_cues_in_extract_but_no_rows` with association **OFF** except Devashish (OFF pass / ON fail before 3.1; both pass after). They are the Phase 4/5 input.

```text
Resume: Naukri_ABRARRAFIKKUMBHARLIKAR[3y_5m] - Copy.pdf
Layout: compact numbered headings, not two-column
Current text order: CV → Summary swallows "A. WORK EXPERIENCE:" and the Datamatics job
Expected semantic order: Summary, then Experience (Datamatics …)
Affected section: Experience (span 0; body inside Summary 4247 chars)
Affected fields: company, role, dates, duties (no rows)
Root cause: section detection treats "A. WORK EXPERIENCE:" as summary prose

Resume: Naukri_AmanYunusMulla[2y_1m].docx
Layout: compact; jobs absent as an Experience section
Current text order: Preamble, Summary, Education, Skills, Projects, Certifications
Expected semantic order: Experience should exist as its own span
Affected section: Experience (span 0)
Affected fields: all job fields
Root cause: employment lines not labeled/split as Experience (likely in Summary/Projects)

Resume: Naukri_AmanYunusMulla[2y_1m].pdf
Layout: digital text with a short Experience span (291)
Current text order: header → Summary → Education → Skills → Projects → Experience
Expected semantic order: Experience before Projects if jobs are employment
Affected section: Experience present but no form rows
Affected fields: company/role/dates
Root cause: EXISTING PARSER ISSUE on that span, not association

Resume: Naukri_AmeyChandramaniAgle[0y_0m].pdf
Layout: two-column / stacked mini-headers
Current text order: Skills, Education (empty-ish), Unclassified 505, then Experience 351
Expected semantic order: Education and Experience bodies with their headers
Affected section: Experience/Education
Affected fields: job rows empty
Root cause: reading-order / header-only spans; jobs in Unclassified

Resume: Naukri_AniketNavnathPakhare[0y_0m].pdf
Layout: two-column sidebar
Current text order: Summary/Projects/Education/Skills as ~6–9 char headers, then Certifications dump, name in the other column
Expected semantic order: contact+name, then summary, education, experience
Affected section: Experience (span 0); content under Certifications/Languages
Affected fields: all job fields
Root cause: OCR_ORDER_ERROR / two-column reading order

Resume: Naukri_AnjaliBhore[0y_10m].docx
Layout: labeled sections; Experience span 544 still yields no rows
Current text order: Contact, Education, Expertise, Experience
Expected semantic order: same
Affected section: Experience
Affected fields: company/role
Root cause: EXISTING PARSER ISSUE (span exists, rows not built)

Resume: Naukri_ankitasunilmahante[4y_0m].pdf
Layout: smashed / no-space text (OCR or PDF encoding)
Current text order: contact, Summary (twice, 3583 chars), Education
Expected semantic order: spaced Experience records
Affected section: Experience (span 0)
Affected fields: all job fields
Root cause: OCR/LAYOUT ISSUE (tokens glued; jobs not sectioned)

Resume: Naukri_Ansarikhalid[3y_6m].pdf
Layout: Experience span is a duty paragraph (232 chars), not job headers
Current text order: Experience paragraph → Summary
Expected semantic order: employer + role + dates then duties
Affected section: Experience
Affected fields: company/role/dates
Root cause: EXISTING PARSER ISSUE (no record boundaries in the span)

Resume: Naukri_AnushkaGohil[4y_0m] - Copy.pdf
Layout: two-column
Current text order: Contact/Skills, Experience header (10 chars), Education header (9), then Summary 2142 holding the body
Expected semantic order: Experience body under Experience
Affected section: Experience
Affected fields: all job fields
Root cause: two-column; body bound to Summary

Resume: Naukri_AwaisAnsari[2y_0m] - Copy.pdf
Layout: Experience span 1314 still no rows
Current text order: Career Overview, Skills, Education, Experience
Expected semantic order: same
Affected section: Experience
Affected fields: company/role
Root cause: EXISTING PARSER ISSUE on a non-empty span

Resume: Naukri_DeepakPravinJadhav[3y_0m].pdf
Layout: two-column sidebar
Current text order: Summary/Experience/Education/Skills headers (~10 chars), then Certifications 2732 containing the biography
Expected semantic order: Experience body under Experience
Affected section: Experience
Affected fields: all job fields
Root cause: two-column reading order (same family as Aniket / Anushka)

Resume: Naukri_DevashishPanchmatia[6y_0m].pdf
Layout: two-column / sidebar
Current text order: education preamble, Experience header, Summary, then Unclassified 3067 with Oterra / Courtyard / Aditya Birla
Expected semantic order: Experience contains those three employers
Affected section: Experience (span ~10); jobs in Unclassified
Affected fields: company (missing), extra jobs missing
Root cause: OCR_ORDER_ERROR / two-column. Association must not invent companies from Summary.

Resume: Naukri_DevendraDilipJaiswal[2y_7m].docx
Layout: jobs inside Summary (Clover Infotech, Mphasis)
Current text order: Summary includes employer lines; no Experience section
Expected semantic order: those lines as Experience records
Affected section: Experience (span 0)
Affected fields: all job fields
Root cause: section mis-bind (employment in Summary)

Resume: Naukri_GaneshRameshGaonkar[7y_0m].pdf
Layout: Experience header 18 chars; body likely in Projects 1630
Current text order: Personal Information, Skills, Summary, Education, Experience, Projects
Expected semantic order: employment under Experience
Affected section: Experience
Affected fields: all job fields
Root cause: compact / mis-sectioned employment

Resume: Naukri_GaneshWKhuaphale[4y_2m].docx
Layout: duties in Summary (1576); Experience span 205
Current text order: Summary (WebLogic duties) then short Experience
Expected semantic order: those duties on the employment record
Affected section: Experience / Summary
Affected fields: company/role/duties
Root cause: EXISTING PARSER + section split; not association
```

Also empty-experience-adjacent (Class B `coverage_missing_with_evidence`, not zero rows): `Naukri_DipeshNarkar[1y_3m].pdf`, `Naukri_FazalShaikh[1y_4m].pdf`.

## H. Recommended next phase

Do **not** add association keyword lists or two-column hacks inside `associate_experience`.

Next bottleneck is **reading order / section binding**: Experience headers with empty bodies while jobs sit in Unclassified, Summary, Certifications, or Projects. That is Phase 4/5 layout recovery — still generalized, still no resume-specific rules.

Do **not** chase 142/195 by changing association. Reproduce 142 only with a frozen HTTP eval on the freeze-era parser, or explain location (18) and role (21 vs freeze 6) drift as separate work.

Leave the kill switch. Leave Berlin / `parse_summary` ≥80 as pre-existing (they fail with association skipped).

## Association rule audit (STEP 9)

| Rule | Evidence required | Modifies | False-positive guard | Unrelated records |
|---|---|---|---|---|
| Duty rebind | ≥2 experience blocks; leak cues in other blocks | description only | skip if owning duty_text empty after strip; never wipe to empty | only the matched block |
| Empty company/role fill | owning block header + plausible label | company/role if empty | reject section headings / duty lines | one entry per block; no new jobs |
| Date fill | empty start/end + block dates | start/end/is_current | no overwrite of filled dates | owning block only |
| Thin experience skip | Experience span < 80 chars | nothing | skip whole associate_experience | prevents Summary-as-company |
| Education date/institution rebind | ≥1 edu block | dates/institution/degree if supported | generic degree cleared if unsupported; no new rows | document-order fallback still exists for education only (no corpus fail increase) |
| Cert drop / skill→cert | name classification cues | drop or reclassify existing names | uncertain certs kept; no invented titles | can drop misfiled certs |
| Summary contact strip | contact tokens / known contact fields | summary text | `is_valid_summary`; no new summary | summary only |

Only the demonstrated bugs above were changed. Education document-order fallback was **not** rewritten (institution fails stayed at 4).

## Test quality (STEP 10)

```text
tests/backend/document_intelligence collected: 584
Association tests: 12 passed (kill switch off)
Kill switch on: association goldens fail (expected); Berlin + parse_summary still fail
Pre-existing (association OFF and ON):
  test_e2e_parse_gold resume_009 / resume_019  (Berlin not in location allowlist)
  test_gold_form_regression resume_009 / resume_019  (same)
  test_heading_plus_body_keeps_body_only  (parse_summary requires len >= 80)
195-resume corpus: measured OFF vs ON as above. Known corpus failures are layout/parser, not dismissed.
```
