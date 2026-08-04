"""Validation rules tests for resume_parsing capability (milestone schema)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from capabilities.loader import load_capability
from runtime.exceptions import ValidationError
from runtime.validation.validator import OutputValidator


CAPABILITY_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def package():
    return load_capability(CAPABILITY_DIR)


@pytest.fixture
def validator() -> OutputValidator:
    return OutputValidator()


def _resume_payload(**overrides: object) -> str:
    base = {
        "type": "resume",
        "person": {"name": "Jane Doe", "email": "jane@example.com", "phone": "+15550123456"},
        "skills": ["Python", "SQL"],
        "experience": [
            {
                "title": "Engineer",
                "company": "Acme",
                "from": "2020-03",
                "to": "Present",
                "years": 5,
            }
        ],
        "education": [{"degree": "BSc", "field": "CS", "year": "2019"}],
        "confidence": 0.85,
    }
    base.update(overrides)
    return json.dumps(base)


def test_runtime_validation_passes_valid_resume(package, validator: OutputValidator) -> None:
    output = validator.validate(
        _resume_payload(),
        schema=package.schema_doc,
        rules=package.validation_rules,
    )
    assert output["type"] == "resume"
    assert output["confidence"] == 0.85


def test_runtime_validation_allows_low_confidence_without_rule(package, validator: OutputValidator) -> None:
    """Milestone validation.yaml has no confidence threshold — schema-only gate."""
    output = validator.validate(
        _resume_payload(confidence=0.4),
        schema=package.schema_doc,
        rules=package.validation_rules,
    )
    assert output["confidence"] == 0.4


def test_runtime_validation_allows_email_string_without_format(package, validator: OutputValidator) -> None:
    """Milestone person.email is plain string (format checks live in Document Intelligence)."""
    payload = json.loads(_resume_payload())
    payload["person"]["email"] = "not-an-email"
    output = validator.validate(
        json.dumps(payload),
        schema=package.schema_doc,
        rules=package.validation_rules,
    )
    assert output["person"]["email"] == "not-an-email"


def test_runtime_validation_rejects_invalid_type_enum(package, validator: OutputValidator) -> None:
    with pytest.raises(ValidationError):
        validator.validate(
            _resume_payload(type="cv"),
            schema=package.schema_doc,
            rules=package.validation_rules,
        )


def test_runtime_validation_allows_freeform_experience_date(package, validator: OutputValidator) -> None:
    payload = json.loads(_resume_payload())
    payload["experience"][0]["from"] = "not-a-date"
    output = validator.validate(
        json.dumps(payload),
        schema=package.schema_doc,
        rules=package.validation_rules,
    )
    assert output["experience"][0]["from"] == "not-a-date"


def test_runtime_validation_accepts_present_end_date(package, validator: OutputValidator) -> None:
    validator.validate(
        _resume_payload(),
        schema=package.schema_doc,
        rules=package.validation_rules,
    )


def test_runtime_validation_skills_are_strings(package, validator: OutputValidator) -> None:
    payload = json.loads(_resume_payload())
    payload["skills"] = ["Python", "SQL"]
    validator.validate(
        json.dumps(payload),
        schema=package.schema_doc,
        rules=package.validation_rules,
    )


def test_runtime_validation_rejects_skill_objects(package, validator: OutputValidator) -> None:
    payload = json.loads(_resume_payload())
    payload["skills"] = [{"name": "Python", "category": "language"}]
    with pytest.raises(ValidationError):
        validator.validate(
            json.dumps(payload),
            schema=package.schema_doc,
            rules=package.validation_rules,
        )


def test_validation_rules_required_fields_declared(package) -> None:
    rules = package.validation_rules
    required = set(rules.get("required_fields") or [])
    assert {"type", "person", "skills", "experience", "education"}.issubset(required)
    nested = rules.get("nested_required") or {}
    assert set(nested.get("person") or []) >= {"name", "email", "phone"}
