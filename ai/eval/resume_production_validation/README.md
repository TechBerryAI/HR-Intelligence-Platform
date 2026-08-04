# Resume Production E2E Validation

Validates that every supported resume in `Resumes/` autofills the application form via the **same production path** as ApplyJobModal (`ResumeUploadWithParsing` → public parse SSE → Form DTO → form state).

## Prerequisites

- Backend on `:3000` with:
  - `DOCUMENT_INTELLIGENCE_VALIDATION_PAYLOAD=true`
  - `DOCUMENT_INTELLIGENCE_VALIDATION_TOKEN=resume-e2e-validation-token`
- Frontend on `:5173` with:
  - `VITE_VALIDATION_HARNESS=true`
  - `VITE_VALIDATION_TOKEN=resume-e2e-validation-token`
- Playwright Chromium: `apps/backend/venv/bin/playwright install chromium`

## Commands

```bash
# Smoke (5 mixed files)
./apps/backend/venv/bin/python ai/eval/resume_production_validation/run_validation.py --smoke 5

# Full corpus + fix/rerun loop (invalidates Frontend/Timeout infra rows on --resume)
./apps/backend/venv/bin/python -u ai/eval/resume_production_validation/run_validation.py \
  --corpus Resumes \
  --out validation-report \
  --workers 2 \
  --fix-loop \
  --max-fix-iterations 5 \
  --resume \
  --invalidate-infra

# Tail progress
tail -f validation-report-run.log
wc -l validation-report/checkpoint.jsonl
```

## Report layout

```
validation-report/
├── summary.html
├── summary.csv
├── failures.csv
├── unsupported.csv
├── screenshots/{passed,failed}/
├── parsed-json/
├── logs/
└── grouped-failures/
```

Unsupported formats (`.doc`, `.zip`, `.xlsx`, empty, oversized) are listed separately and excluded from pass %.
