"""End-to-end smoke tests for Ollama resume parsing pipeline."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "apps" / "backend"
REPO_ROOT = BACKEND_ROOT.parent
AI_ROOT = REPO_ROOT / "ai"

if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

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
    os.environ.setdefault("AI_USE_GATEWAY", "true")
    os.environ.setdefault(
        "AI_RUNTIME_CONFIG",
        str(AI_ROOT / "runtime" / "config" / "runtime.production.yaml"),
    )
    os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
    os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:7b-instruct")


def test_parse_via_runtime_returns_structured_resume(runtime_env):
    from ai_runtime_adapter import normalize_proposal, parse_via_runtime

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
    from llm_service import call_llm

    toon = call_llm(SAMPLE_RESUME, "resume")
    assert toon["type"] == "resume"
    assert toon["person"]["name"]
    assert isinstance(toon["skills"], list)
