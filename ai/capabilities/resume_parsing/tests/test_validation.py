"""Validation rules tests for resume_parsing capability."""

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


def test_runtime_validation_rejects_low_confidence(package, validator: OutputValidator) -> None:
    with pytest.raises(ValidationError) as exc:
        validator.validate(
            _resume_payload(confidence=0.4),
            schema=package.schema_doc,
            rules=package.validation_rules,
        )
    assert "confidence" in str(exc.value).lower()


def test_runtime_validation_rejects_invalid_email(package, validator: OutputValidator) -> None:
    payload = json.loads(_resume_payload())
    payload["person"]["email"] = "not-an-email"
    with pytest.raises(ValidationError):
        validator.validate(
            json.dumps(payload),
            schema=package.schema_doc,
            rules=package.validation_rules,
        )


def test_runtime_validation_rejects_invalid_type_enum(package, validator: OutputValidator) -> None:
    with pytest.raises(ValidationError):
        validator.validate(
            _resume_payload(type="cv"),
            schema=package.schema_doc,
            rules=package.validation_rules,
        )


def test_runtime_validation_rejects_invalid_experience_date(package, validator: OutputValidator) -> None:
    payload = json.loads(_resume_payload())
    payload["experience"][0]["from"] = "not-a-date"
    with pytest.raises(ValidationError):
        validator.validate(
            json.dumps(payload),
            schema=package.schema_doc,
            rules=package.validation_rules,
        )


def test_runtime_validation_accepts_present_end_date(package, validator: OutputValidator) -> None:
    validator.validate(
        _resume_payload(),
        schema=package.schema_doc,
        rules=package.validation_rules,
    )


def test_runtime_validation_skill_category_enum(package, validator: OutputValidator) -> None:
    payload = json.loads(_resume_payload())
    payload["skills"] = [{"name": "Python", "category": "language"}]
    validator.validate(
        json.dumps(payload),
        schema=package.schema_doc,
        rules=package.validation_rules,
    )


def test_runtime_validation_rejects_invalid_skill_category(package, validator: OutputValidator) -> None:
    payload = json.loads(_resume_payload())
    payload["skills"] = [{"name": "Python", "category": "invalid_category"}]
    with pytest.raises(ValidationError):
        validator.validate(
            json.dumps(payload),
            schema=package.schema_doc,
            rules=package.validation_rules,
        )


def test_validation_rules_cross_field_declared(package) -> None:
    cross_field = package.validation_rules.get("cross_field", [])
    rule_ids = {rule["id"] for rule in cross_field}
    assert "experience_dates_order" in rule_ids
    assert "person_links_dedupe" in rule_ids
    assert len(cross_field) >= 5


def test_validation_rules_arrays_declared(package) -> None:
    arrays = package.validation_rules.get("arrays", {})
    assert "skills" in arrays
    assert arrays["skills"].get("allow_string_items") is True
    assert arrays["skills"].get("allow_object_items") is True
