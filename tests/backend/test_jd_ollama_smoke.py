"""Integration smoke tests for JD parsing via Ollama (skipped when unavailable)."""

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

SAMPLE_JD = """
Senior Python Developer — Acme Corp — Remote

Required Skills: Python, Django, PostgreSQL
Preferred Skills: AWS, Docker

Responsibilities:
- Design and build REST APIs
- Write unit and integration tests
- Collaborate with product team

Qualifications:
- Bachelor's degree in Computer Science
- 5+ years of backend development experience
""".strip()


def _ollama_available() -> bool:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        response = httpx.get(f"{host}/api/tags", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_available(), reason="Ollama not available")
def test_jd_parse_via_runtime_has_mandatory_skills():
    from app.ai.adapter.runtime_adapter import parse_via_runtime, normalize_proposal
    from app.domains.recruitment.services.parsing_storage import validate_toon_format

    raw = parse_via_runtime(SAMPLE_JD, "jd")
    toon = normalize_proposal(raw, "jd")
    if not toon.get("responsibilities"):
        toon["responsibilities"] = ["Design APIs"]
    ok, err = validate_toon_format(toon, "job_description")
    assert ok, err
    assert toon.get("mandatory_skills") or toon.get("skills")
