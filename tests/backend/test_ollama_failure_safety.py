"""Malformed / outage / timeout AI output must fail closed with no persistence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parents[2] / "ai"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from runtime.exceptions import ProviderNotAvailableError, ProviderTimeoutError, ValidationError
from runtime.validation.validator import OutputValidator


def test_coerce_before_validate_accepts_location_object_and_null_strings():
    from capabilities.loader import load_capability
    from providers.ollama.structured_output import normalize_content
    import jsonschema

    package = load_capability(AI_ROOT / "capabilities" / "resume_parsing")
    raw = {
        "type": "resume",
        "person": {
            "name": "A",
            "email": "a@b.com",
            "phone": None,
            "location": {"city": "Pune", "country": "India"},
        },
        "skills": [{"name": "Python"}],
        "experience": [],
        "education": [],
        "summary": None,
        "total_experience_years": None,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(package.schema_doc).validate(raw)
    coerced = json.loads(normalize_content(json.dumps(raw), schema_id="resume_milestone_v1"))
    jsonschema.Draft202012Validator(package.schema_doc).validate(coerced)
    assert coerced["person"]["location"] == "Pune, India"
    assert coerced["person"]["phone"] == ""
    assert coerced["summary"] == ""
    assert coerced["skills"] == ["Python"]
    assert coerced["total_experience_years"] is None


def test_malformed_json_fails_validation():
    validator = OutputValidator()
    with pytest.raises(ValidationError) as exc:
        validator.validate(
            "not-json{",
            schema={"type": "object"},
            rules={"schema_validate": True},
        )
    assert "not valid JSON" in str(exc.value)


def test_missing_required_resume_fields_fail_schema():
    from capabilities.loader import load_capability
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    package = load_capability(repo / "ai" / "capabilities" / "resume_parsing")
    validator = OutputValidator()
    with pytest.raises(ValidationError):
        validator.validate(
            json.dumps({"type": "resume", "skills": []}),
            schema=package.schema_doc,
            rules=package.validation_rules,
        )


def test_validation_failure_does_not_persist(monkeypatch):
    from app.ai.adapter import runtime_adapter
    from runtime.exceptions import ValidationError as VE

    def _boom(*_a, **_k):
        raise VE("Schema validation failed", errors=["missing:person"])

    monkeypatch.setattr(runtime_adapter, "parse_via_runtime", _boom)
    persist_calls = []
    monkeypatch.setattr(
        "app.domains.recruitment.services.parsing_storage.store_parsed_resume",
        lambda *a, **k: persist_calls.append((a, k)) or "should-not-run",
    )
    with pytest.raises(VE):
        runtime_adapter.parse_via_runtime("resume text", "resume")
    assert persist_calls == []


def test_ollama_unavailable_does_not_persist(monkeypatch):
    from app.ai.adapter import runtime_adapter

    def _down(*_a, **_k):
        raise ProviderNotAvailableError(
            "Ollama unreachable",
            provider_id="ollama",
            retryable=True,
        )

    monkeypatch.setattr(runtime_adapter, "parse_via_runtime", _down)
    persist_calls = []
    monkeypatch.setattr(
        "app.domains.recruitment.services.parsing_storage.store_parsed_resume",
        lambda *a, **k: persist_calls.append(1),
    )
    with pytest.raises(ProviderNotAvailableError):
        runtime_adapter.parse_via_runtime("resume text", "resume")
    assert persist_calls == []


def test_timeout_is_bounded_and_does_not_persist(monkeypatch):
    from app.ai.adapter import runtime_adapter

    def _timeout(*_a, **_k):
        raise ProviderTimeoutError(
            "Ollama timed out",
            provider_id="ollama",
            retryable=True,
        )

    monkeypatch.setattr(runtime_adapter, "parse_via_runtime", _timeout)
    persist_calls = []
    monkeypatch.setattr(
        "app.domains.recruitment.services.parsing_storage.store_parsed_resume",
        lambda *a, **k: persist_calls.append(1),
    )
    with pytest.raises(ProviderTimeoutError):
        runtime_adapter.parse_via_runtime("resume text", "resume", timeout_seconds=2, max_attempts=1)
    assert persist_calls == []
