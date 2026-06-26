"""Extended validation tests for capability rules."""

from __future__ import annotations

import pytest

from runtime.exceptions import ValidationError
from runtime.validation.validator import OutputValidator


RESUME_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "type": {"type": "string", "const": "resume"},
        "person": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
            },
            "required": ["name", "email", "phone"],
        },
        "skills": {"type": "array"},
        "experience": {"type": "array"},
        "education": {"type": "array"},
        "confidence": {"type": "number"},
    },
    "required": ["type", "person", "skills", "experience", "education"],
}


def test_validator_parses_json() -> None:
    validator = OutputValidator()
    output = validator.validate('{"name": "Jane"}', schema=None, rules={"schema_validate": True})
    assert output["name"] == "Jane"


def test_validator_required_fields() -> None:
    validator = OutputValidator()
    with pytest.raises(ValidationError) as exc:
        validator.validate("{}", schema=None, rules={"required_fields": ["name"]})
    assert "name" in str(exc.value)


def test_validator_allows_text_output() -> None:
    validator = OutputValidator()
    output = validator.validate("plain summary", schema=None, rules={"schema_validate": False})
    assert output == "plain summary"


def test_validator_schema_and_enums() -> None:
    validator = OutputValidator()
    payload = (
        '{"type":"resume","person":{"name":"A","email":"a@b.com","phone":"1"},'
        '"skills":[],"experience":[],"education":[],"confidence":0.9}'
    )
    output = validator.validate(
        payload,
        schema=RESUME_SCHEMA,
        rules={"schema_validate": True, "enums": {"type": ["resume"]}},
    )
    assert output["type"] == "resume"


def test_validator_confidence_threshold() -> None:
    validator = OutputValidator()
    payload = (
        '{"type":"resume","person":{"name":"A","email":"a@b.com","phone":"1"},'
        '"skills":[],"experience":[],"education":[],"confidence":0.4}'
    )
    with pytest.raises(ValidationError):
        validator.validate(
            payload,
            schema=RESUME_SCHEMA,
            rules={"schema_validate": True, "confidence": {"min_overall": 0.6}},
        )


def test_validator_regex_email() -> None:
    validator = OutputValidator()
    payload = (
        '{"type":"resume","person":{"name":"A","email":"invalid","phone":"1"},'
        '"skills":[],"experience":[],"education":[]}'
    )
    with pytest.raises(ValidationError):
        validator.validate(
            payload,
            schema=None,
            rules={
                "schema_validate": True,
                "regex": {"person.email": r"^[^@\s]+@[^@\s]+\.[^@\s]+$"},
            },
        )
