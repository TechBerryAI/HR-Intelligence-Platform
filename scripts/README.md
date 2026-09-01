# Scripts

Operational utilities for development and database diagnostics.

## What is this?

Root-level scripts that support local development, CI preflight, and database connectivity checks.

## Scripts

| Script | Purpose |
|--------|---------|
| `../start.js` | Local stack: env, venv, npm, backend + frontend + Ollama |
| `../start-vm.js` | Full VM stack: DB (Hyper-V / Docker) + backend + frontend + Ollama |
| `clear-cache.js` | Wipe local bytecode / pytest / Vite caches (`npm run clear-cache`) |
| `db-preflight.js` | PostgreSQL connectivity diagnostics (reads `apps/backend/.env`, WSL-aware) |
| `database/test_db_connection.py` | Python DB connection test |
| `ensure_media_assets.py` | Ensure durable media dirs + seed hero |
| `release-verify.sh` | Production release checks (processes / alembic head / health / db-sessions). No secrets. |
| `inspect_db_sessions.py` | Read-only `pg_stat_activity` / lock report. Never kills backends. |
| Backend module `python -m app.database.scripts.offload_blobs` | BYTEA → media + checksum verify |

Full media docs: **[docs/OPERATIONS.md](../docs/OPERATIONS.md)**.

## What belongs here?

- Cross-cutting dev utilities used from repo root
- Database and environment diagnostics

## What should never be placed here?

- AI platform CLIs → `ai/runtime/cli/`, `ai/dataset/*/cli/`
- Backend one-offs tied to Flask → prefer `apps/backend/` or document here explicitly
- Production **deploy/start** scripts → wrap the commands in [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md#production-release) under your supervisor; `release-verify.sh` is the check helper only

## Quick start

```bash
# Clear local caches (__pycache__, .pytest_cache, Vite .vite, etc.)
npm run clear-cache
# Preview only: npm run clear-cache:dry
# Also drop frontend dist/: node scripts/clear-cache.js --dist

# Release verification (no secrets)
scripts/release-verify.sh pre-deploy
scripts/release-verify.sh db-sessions
scripts/release-verify.sh post-start

# Database preflight (Node)
node scripts/db-preflight.js

# Database test (Python)
cd apps/backend && source venv/bin/activate
python ../../scripts/database/test_db_connection.py
```

## Resume parsing smoke test (Ollama)

Primary model: **hardware-adaptive** when `OLLAMA_MODEL` is unset (`gpu_high`→14b, `gpu_mid`/`unknown`→7b, `cpu`→3b). Pin `OLLAMA_MODEL` to override.

`node start.js` now:
1. Installs backend deps from `requirements.txt` (includes **RapidOCR** via `rapidocr-onnxruntime`, pymupdf, Pillow)
2. Verifies OCR Python imports
3. Health-checks `OLLAMA_HOST` (default `http://192.168.1.200:11434`). Pulls the selected model onto that host (local `ollama serve` only when the host is loopback)
4. Normalizes `OLLAMA_HOST` (also accepts legacy `OLLAMA_BASE_URL`) — does not rewrite keys already present in `.env`

```bash
# Prerequisites: central Ollama at OLLAMA_HOST (default http://192.168.1.200:11434),
# or a local daemon if you set OLLAMA_HOST=http://127.0.0.1:11434
# Then from repo root:
node start.js

# Optional local daemon (only if OLLAMA_HOST is loopback):
ollama pull qwen2.5:7b-instruct
ollama serve

cd apps/backend && source venv/bin/activate
pip install -r requirements.txt   # OCR is pip-only (rapidocr-onnxruntime); no apt tesseract required

# Unit tests (no Ollama required)
pytest tests/test_resume_parsing_unit.py tests/test_jd_parsing_unit.py \
  tests/test_resume_text_inference.py tests/test_text_extraction_ocr.py -v

# Integration smoke (requires Ollama)
pytest tests/test_resume_ollama_smoke.py -v -m integration
```

OCR env knobs (optional): `OCR_ENABLED=true`, `OCR_DPI=250`, `PDF_MAX_PAGES=0`.
System Tesseract is optional; RapidOCR from requirements is the primary OCR engine.

## Related documentation

- [Development guide](../docs/DEVELOPMENT.md)
- [Docs index](../docs/README.md)
- [Backend README](../apps/backend/README.md)
