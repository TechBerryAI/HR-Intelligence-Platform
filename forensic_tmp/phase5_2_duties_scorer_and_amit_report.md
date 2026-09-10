# Phase 5.2 — Duties scorer hygiene + narrow Experience fixes

Measured 9 September 2026. Phase 3 / Phase 4 frozen. Phase 5 frozen except narrowly demonstrated defects. No Education / OCR work.

## 1. Scorer changes

File: `ai/eval/apply_public_eval/score.py`

**Before:** `description` failed when *any* extract-wide duty cue existed and the **first** experience row had an empty description.

**After:**

* `experience_section_text()` — Experience / Employment body only (stops at bare `Projects` / Education / Skills…; does **not** stop at nested `Project N | Title`).
* `experience_has_duty_evidence()` — True only for Experience-section duty bullets / duty verbs. Ignores:
  * employment prose (`Working as ROLE for COMPANY`)
  * Project/Skills dumps outside Experience
* Scoring:
  * any job has description → **pass**
  * Experience has duty evidence but no descriptions → **fail**
  * no Experience duty evidence → **n/a** (not a parser failure)

This turns header-only Experience (Archana, Ashwanth, Gangaraju, Ganesh, …) into correct `n/a`.

## 2. Amit diagnosis

**Root cause (two parser bugs + one date bug):**

1. `_is_bullet_or_duty_line`: `Role | Company, Internship` matched “comma + len>40 ⇒ duty” and returned `None` from `_parse_experience_line`.
2. Nested `Project 1 | Title` under an open job entered project-skip mode and dropped Responsibility bullets.
3. `extract_date_range('(09/2022) – (06/2023)')` stripped outer parens incorrectly (two parenthesized atoms) → end date lost.
4. Singular `Responsibility:` was not in `_BARE_DUTY_HEADER` / `_EXP_META_LINE` → fake second row.

**Minimal generalized fix:**

* Treat `Role | Company[, employment-type]` as a header in `_is_bullet_or_duty_line`.
* Strip employment-type suffixes (`Internship`, `Contract`, …) from company.
* Nested `Project N | Title` under `pending_jobs` keeps duties (still isolates standalone `Project #1` + Client/Duration).
* Parenthesized date atoms in `extract_date_range`.
* Singular `responsibility` in duty-header regexes.

Result: VeriTech internship + 5 bullets + dates reconstructed. Sociodigit remains a separate later job from the same resume.

## 3. Bipin diagnosis

```text
Job A Virtusa — description empty
Job B+ — employment prose / one duty blob on a later row
```

**Verdict: Case 1 + Case 3 (scorer), not a Phase 5.2 parser change.**

* Source Experience is mostly `Working/Worked as ROLE for COMPANY` employment lines (not bullet duties).
* First-job-empty is legitimate when later rows carry text.
* Old scorer failed because it required the **first** description.
* New scorer: **pass** (any-job description).
* Residual quality: some employment prose may still sit under the wrong company (misassociation). Left for a future narrow association pass — **not** fixed here per “do not change until proven.”

## 4. Duties classification (prior 11 after hygiene)

| Resume | Old | New | Classification |
|---|---|---|---|
| AmitKumarPradhan | fail | **pass** | REAL duties extracted (parser fix) |
| ArchanaTambe | fail | **n/a** | EXPECTED N/A |
| AshokPandi | fail | **n/a** | EXPECTED N/A |
| Ashwanth | fail | **n/a** | EXPECTED N/A |
| BhargaviDadi | fail | **n/a** | EXPECTED N/A (duties outside Experience) |
| BipinShivkumarDubey | fail | **pass** | SCORER (any-job); residual misassoc risk |
| ChiranjitSarkar | fail | **n/a** | EXPECTED N/A / section |
| DeelipuDoppalapudi | fail | **n/a** | EXPECTED N/A / section |
| Deepshikhachak | fail | **n/a** | EXPECTED N/A / section |
| GaneshWKhuaphale | fail | **n/a** | EXPECTED N/A |
| GangarajuD | fail | **n/a** | EXPECTED N/A |

Corpus description field after Phase 5.2: **fail 0**, pass 178, n/a 17.

Semantic buckets:

```text
Actual duties present + correctly extracted:   Amit (+ Bipin partial)
Actual duties present + missing:               0 (corpus description fail)
Actual duties present + misassociated:         Bipin residual (not scored fail)
Actual duties absent + correctly n/a:          9 of prior 11 + others → 17 n/a
OCR/layout unavailable:                        ankitasunilmahante (Experience fail)
```

## 5. Metrics

Same 195 corpus, venv RapidOCR, association ON, recovery ON.

```text
Metric             | Phase 5 (before) | Phase 5.2 | Delta
Accepted           | 150              | 159       | +9
Experience         |   2 fail         |   2 fail  |  0
Company            |   4 fail         |   4 fail  |  0
Role               |   8 fail         |   8 fail  |  0
Start date         |   2 fail         |   2 fail  |  0
End date           |   2 fail         |   2 fail  |  0
Duties             |  11 fail         |   0 fail  | -11
Education          |   7 fail         |   7 fail  |  0
Skills             |   4 fail         |   4 fail  |  0
Certifications     |   0 fail         |   0 fail  |  0
Summary            |   0 fail         |   0 fail  |  0
Location           |  16 fail         |  16 fail  |  0
```

Artifact: `_forensic_tmp/phase5_2_eval/phase5_2_results.json`

## 6. Regression report

```text
Acceptance regressions: 0   (150 → 159)
Experience regressions: 0   (still 2)
Phase 3 regressions: 0      (association tests green)
Phase 4 regressions: 0      (section recovery tests green)
Phase 5 regressions: 0      (layouts + structural boundaries green)
```

DI suite: **603 passed**, 4 skipped, **5 failed** (pre-existing Berlin location + `parse_summary` length only).

Focused: Phase 5.2 unit tests + experience layouts + structural boundaries + association + section recovery — green.

## 7. Remaining OCR issue (Ankita)

Unchanged. Glued OCR, no usable Experience section, letter-spaced crumbs. **OCR/layout backlog.** Parser not modified for this resume.

**Ansari:** still valid no-invention (`(24x7) Production Environment`).

## 8. Next bottleneck

Recommended order:

1. **Education reconstruction** (7 fails, independent) — now the clearest structured-parser bottleneck.
2. **OCR/layout** for Ankita-class glued extracts.
3. Optional later: **narrow Bipin-style employment-prose misassociation** (not scorer).

Do **not** chase historical 142; current reproducible acceptance is **159/195**.
