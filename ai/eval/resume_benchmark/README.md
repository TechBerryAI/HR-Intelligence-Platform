# Resume Parsing Benchmark

A closed improvement loop for the production resume parser, driven by a
human-authored spreadsheet of expected values and the matching resume files.

```
spreadsheet + resume files
        │  ingest.py
        ▼
   gold corpus  ──►  predict.py (production pipeline)  ──►  scoring.py
        │                                                        │
        │                                                  triage.py
        ▼                                                        ▼
  gold QA warnings                                   report.md: scorecard +
                                                     ranked "fix next" list
                                                             │
                                          fix parser ────────┘
                                                             │
                                          re-run ──► thresholds ratchet
```

The spreadsheet is the definition of "correct". Nothing else in the loop gets a
vote: when a score is low, either the parser is wrong or the spreadsheet cell
is wrong, and the report tells you which to suspect.

## One-time setup

```bash
python ai/eval/resume_benchmark/ingest.py \
  --xlsx "actual resume result.xlsx" \
  --resumes "resume testing"
```

Reads every row, matches it to a resume file by the `File Name` column, and
writes one case folder per row under
`ai/dataset/lake/benchmark/resume_gold/v1/cases/`. Re-run it whenever the
spreadsheet gains rows or a cell is corrected — it is idempotent.

Expected columns:

| Column | Form field | Compared as |
|---|---|---|
| `File Name` | — | case key |
| `Full Name` | `fullName` | name token set |
| `Email` | `email` | address set |
| `Phone` | `phone` | last 10 digits |
| `Current location` | `currentLocation` | place tokens |
| `Preferred location` | `preferredLocation` | place tokens |
| `LinkedIn URL` | `linkedinUrl` | URL handle |
| `Portfolio` | `portfolioUrl` | URL handle |
| `GitHub URL` | `githubUrl` | URL handle |
| `Experience level` | `experienceLevel` | enum |
| `Skills (comma-separated)` | `skills` | set F1 |
| `Professional summary` | `summary` | coverage |
| `Education` | `education[]` | fact recall + row precision |
| `Experience` | `experiences[]` | fact recall + row precision |
| `Certifications` | `certifications[]` | fact recall + row precision |

## Measure

**Run it with the backend's own interpreter.** Some resumes in the corpus are
scanned or image-only and yield text only through OCR, and the OCR engine
(RapidOCR) lives in `apps/backend/venv` — a WSL virtualenv on this machine, not
the Windows Python:

```bash
wsl -d Ubuntu -- bash -lc 'cd /mnt/d/Projects/HR-Intelligence-Platform && PYTHONPATH=apps/backend ./apps/backend/venv/bin/python ai/eval/resume_benchmark/run_benchmark.py --workers 4'
```

The runner probes for an OCR engine before doing any work and **exits rather
than producing a silently degraded score** if none is found. `--allow-no-ocr`
overrides that and stamps the run (and its report) as OCR-degraded; such a run
is refused as a baseline or threshold source.

Extracted text is cached per case alongside `extract_meta.json`, which records
whether OCR was available when the text was produced. Text cached without OCR is
discarded automatically once an engine exists — otherwise a scanned resume
cached as an empty string would score zero forever.

| Flag | Effect |
|---|---|
| `--workers N` | parse cases in N processes |
| `--llm` | allow the semantic residual pass (default: deterministic only) |
| `--case <id>` | one case, repeatable — use with `--show` while debugging |
| `--show` | print every field that is not a clean match |
| `--reextract` | ignore the cached extracted text |
| `--allow-no-ocr` | score without an OCR engine, marking the run degraded |
| `--gate` | exit non-zero if any locked threshold regressed |
| `--set-baseline` | record this run as the comparison point for later runs |
| `--write-thresholds` | rewrite `thresholds.yaml` from this run |

Artifacts land in `ai/eval/reports/resume_benchmark/`:

- `<timestamp>/report.md` — the scorecard and the ranked fix list
- `<timestamp>/results.json` — every field result, machine readable
- `<timestamp>/predictions.jsonl` — raw pipeline output per case
- `LATEST_REPORT.md`, `latest.json` — stable paths to the newest run
- `baseline.json` — the run every report diffs against

## The improvement loop

1. **Run** the benchmark. Read the *Fix next* table — it ranks failure modes by
   weighted score recoverable, not by how many cases they touch, so the top row
   is genuinely the best next hour of work.
2. **Reproduce** one case in isolation:
   `run_benchmark.py --case <case_id> --show`. The case folder holds
   `source.pdf`, `extracted.txt` and `gold.json` side by side, so you can see
   whether the loss happened in extraction, sectioning or field mapping.
3. **Fix** the parser under `apps/backend/app/ai/`.
4. **Re-run.** The report's `vs baseline` column shows whether the fix moved the
   number and, just as important, whether it broke another field.
5. **Ratchet** once the gain is real:
   `run_benchmark.py --set-baseline --write-thresholds`. Future runs with
   `--gate` fail if anything drops back below the new floor.

## Why sections are scored as facts, not rows

The `Education` / `Experience` / `Certifications` cells are hand-written. The
same degree appears as one numbered entry in one row and as two in another; a
company and a role share a line here and sit on separate lines there. Aligning
predicted rows to gold rows would score that authoring style rather than the
parser.

So each gold cell is reduced to the **entities** it names — degrees,
institutions, companies, roles, certificate names, issuers, years — and the
section scores as:

- **fact recall** — did every gold entity reach some form row?
- **row precision** — did any emitted row match nothing in gold? (this is what
  catches one section bleeding into another)
- **date recall** — did the years survive?

`score = 0.65 × F1(precision, recall) + 0.2 × recall + 0.15 × date_recall`.

Row-count drift is still reported as `*_rows_merged` / `*_rows_split` tags, so
splitting problems stay visible without dominating the score.

## Blank gold

A field the spreadsheet leaves blank is not scored for accuracy — it is tracked
separately:

- prediction also blank → `blank_ok`
- prediction has a value → `false_positive`, tagged `<field>_invented`

False-positive rate is reported per field. One exception is encoded in
`config.py`: `preferredLocation` mirroring `currentLocation` is designed
behaviour (`VALIDATION_FIX_preferred_location_fallback`), so that echo scores as
`blank_ok` rather than as a hallucination.

## Benchmark quality warnings

`ingest.py` audits every row and records what looks mis-authored — a skills
string pasted into the location cell, a full postal address where a city
belongs, a non-LinkedIn URL in the LinkedIn column, a section cell that cannot
be split. These surface in `manifest.json` and in a section of every report.

Fix those cells before chasing the corresponding parser "failures": each one
caps the score the parser can possibly reach.

## Known corpus gaps

| File | Gap |
|---|---|
| `Vishal Goel Mongodb.doc` | Legacy binary `.doc` — `text_extraction.py` rejects the format outright, and no converter (`antiword`, `catdoc`, LibreOffice) is installed. Not an OCR problem: the file is a Word document, not an image. Fixing it means either a converter in the backend image or asking for a `.docx`/PDF. |

## Tests

```bash
# fast — guards the comparators themselves
pytest ai/eval/resume_benchmark/tests/test_scoring.py -q

# full regression gate (minutes; needs the ingested corpus + an OCR engine)
RESUME_BENCHMARK_GATE=1 pytest ai/eval/resume_benchmark/tests/test_regression_gate.py -v
```

## Data handling

The corpus contains real candidate documents. `ai/dataset/lake/benchmark/
resume_gold/` and `ai/eval/reports/resume_benchmark/` are git-ignored; only the
harness code and `thresholds.yaml` are tracked. Keep it that way.
