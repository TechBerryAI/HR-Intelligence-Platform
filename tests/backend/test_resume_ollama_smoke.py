"""End-to-end smoke tests for Ollama resume parsing pipeline."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "apps" / "backend"
AI_ROOT = REPO_ROOT / "ai"

if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SAMPLE_RESUME = """
Jane Doe
Email: jane.doe@example.com
Phone: +1 555-010-2000
Location: San Francisco, CA

EXPERIENCE
Software Engineer — Acme Corp (2020-01 to 2023-12)
Built web applications with Python and React.

EDUCATION
B.S. Computer Science — State University (2020)

SKILLS
Python, JavaScript, SQL, Docker

CERTIFICATIONS
AWS Certified Developer

LANGUAGES
English (native), Spanish (conversational)
""".strip()


def _ollama_available() -> bool:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        response = httpx.get(f"{host}/api/tags", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def require_ollama():
    if not _ollama_available():
        pytest.skip("Ollama is not running at OLLAMA_HOST")


@pytest.fixture(scope="module")
def runtime_env(require_ollama):
    os.environ["AI_USE_GATEWAY"] = "true"
    os.environ["AI_RUNTIME_CONFIG"] = str(
        AI_ROOT / "runtime" / "config" / "runtime.production.yaml"
    )
    os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
    os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:14b-instruct")


def test_parse_via_runtime_returns_structured_resume(runtime_env):
    from app.ai.adapter.runtime_adapter import normalize_proposal, parse_via_runtime

    structured = parse_via_runtime(SAMPLE_RESUME, "resume")
    assert isinstance(structured, dict)
    assert structured.get("type") == "resume"

    toon = normalize_proposal(structured, "resume")
    assert toon["type"] == "resume"
    assert "person" in toon
    assert toon["person"]["name"]
    assert isinstance(toon["skills"], list)
    assert isinstance(toon["experience"], list)
    assert isinstance(toon["education"], list)


def test_call_llm_gateway_path(runtime_env):
    from app.integrations.openai.llm_service import call_llm

    toon = call_llm(SAMPLE_RESUME, "resume")
    assert toon["type"] == "resume"
    assert toon["person"]["name"]
    assert isinstance(toon["skills"], list)


def test_ollama_parse_persists_and_retry_uses_cache(runtime_env):
    """Real Ollama JSON → normalize → persist; second hash lookup must not duplicate."""
    from app.ai.adapter.runtime_adapter import normalize_proposal, parse_via_runtime
    from app.database.connection.db import db_all, db_get, db_run
    from app.domains.recruitment.services.parsing_storage import (
        compute_file_hash,
        store_parsed_resume,
        store_raw_file,
    )

    try:
        if not db_get("SELECT 1 AS ok"):
            pytest.skip("Postgres not reachable")
    except Exception as exc:
        pytest.skip(f"Postgres not reachable: {exc}")

    structured = parse_via_runtime(SAMPLE_RESUME, "resume")
    toon = normalize_proposal(structured, "resume")
    assert toon["person"]["name"]

    payload = SAMPLE_RESUME.encode("utf-8")
    uploader = "ollama-e2e-closure"
    raw = store_raw_file(
        uploader,
        "recruiter",
        payload,
        "jane-doe-e2e.txt",
        "text/plain",
        None,
    )
    parsed_id = store_parsed_resume(
        raw["id"],
        None,
        toon,
        SAMPLE_RESUME,
        0.9,
        "canonical-v6-jd-coverage+ollama-e2e",
    )
    try:
        row = db_get("SELECT id, toon FROM parsed_resumes WHERE id = ?", (parsed_id,))
        assert row and str(row["id"]) == str(parsed_id)
        assert "Jane" in (row["toon"] or "")

        file_hash = compute_file_hash(payload)
        assert file_hash == raw["file_hash"]
        dupes = db_all(
            """
            SELECT p.id FROM parsed_resumes p
            JOIN raw_files r ON r.id = p.raw_file_id
            WHERE r.file_hash = ? AND r.uploader_id = ?
            """,
            (file_hash, uploader),
        )
        assert len(dupes) == 1, f"retry/cache must not insert a second row: {dupes!r}"
    finally:
        db_run("DELETE FROM parsed_resumes WHERE id = ?", (parsed_id,))
        db_run("DELETE FROM raw_files WHERE id = ?", (raw["id"],))
        db_run(
            "DELETE FROM parsed_resumes WHERE raw_file_id IN "
            "(SELECT id FROM raw_files WHERE uploader_id = ?)",
            (uploader,),
        )
        db_run("DELETE FROM raw_files WHERE uploader_id = ?", (uploader,))
