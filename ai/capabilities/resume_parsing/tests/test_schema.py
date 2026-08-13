"""Schema validation tests for resume_parsing capability."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from capabilities.loader import load_capability


CAPABILITY_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def schema() -> dict:
    return load_capability(CAPABILITY_DIR).schema_doc


def test_person_required_keys(schema: dict) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(
            {
                "type": "resume",
                "person": {"name": "A"},
                "skills": [],
                "experience": [],
                "education": [],
            }
        )


def test_experience_date_aliases_allowed(schema: dict) -> None:
    payload = {
        "type": "resume",
        "person": {"name": "A", "email": "a@b.com", "phone": "1"},
        "skills": [],
        "experience": [{"title": "Dev", "company": "X", "start_date": "2021-06", "end_date": "Present"}],
        "education": [],
    }
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_certification_string_and_object(schema: dict) -> None:
    payload = {
        "type": "resume",
        "person": {"name": "A", "email": "a@b.com", "phone": "1"},
        "skills": [],
        "experience": [],
        "education": [],
        "certifications": ["PMP", {"name": "AWS SA", "issuer": "Amazon", "status": "active"}],
    }
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_language_string_and_object(schema: dict) -> None:
    payload = {
        "type": "resume",
        "person": {"name": "A", "email": "a@b.com", "phone": "1"},
        "skills": [],
        "experience": [],
        "education": [],
        "languages": ["English", {"language": "Spanish", "proficiency": "conversational"}],
    }
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_confidence_bounds(schema: dict) -> None:
    """Milestone schema allows optional confidence without strict bounds."""
    base = {
        "type": "resume",
        "person": {"name": "A", "email": "a@b.com", "phone": "1"},
        "skills": [],
        "experience": [],
        "education": [],
    }
    jsonschema.Draft202012Validator(schema).validate({**base, "confidence": 0.0})
    jsonschema.Draft202012Validator(schema).validate({**base, "confidence": 1.0})
    # additionalProperties: true — out-of-range confidence is not schema-rejected
    jsonschema.Draft202012Validator(schema).validate({**base, "confidence": 1.5})


def test_allows_additional_root_properties(schema: dict) -> None:
    payload = {
        "type": "resume",
        "person": {"name": "A", "email": "a@b.com", "phone": "1"},
        "skills": [],
        "experience": [],
        "education": [],
        "unknown_field": "x",
    }
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_null_total_experience_years_allowed(schema: dict) -> None:
    payload = {
        "type": "resume",
        "person": {"name": "A", "email": "a@b.com", "phone": "1"},
        "skills": ["Python"],
        "experience": [],
        "education": [],
        "total_experience_years": None,
    }
    jsonschema.Draft202012Validator(schema).validate(payload)


def test_coerced_location_object_then_passes_schema(schema: dict) -> None:
    from providers.ollama.structured_output import normalize_content

    raw = {
        "type": "resume",
        "person": {
            "name": "A",
            "email": "a@b.com",
            "phone": "1",
            "location": {"raw": "Pune, India", "city": "Pune", "country": "IN"},
        },
        "skills": [],
        "experience": [],
        "education": [],
        "summary": None,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(raw)
    coerced = json.loads(
        normalize_content(json.dumps(raw), schema_id="resume_milestone_v1")
    )
    jsonschema.Draft202012Validator(schema).validate(coerced)
    assert coerced["person"]["location"] == "Pune, IN"
    assert coerced["summary"] == ""


def test_location_is_string(schema: dict) -> None:
    payload = {
        "type": "resume",
        "person": {
            "name": "A",
            "email": "a@b.com",
            "phone": "1",
            "location": "Pune, India",
        },
        "skills": [],
        "experience": [],
        "education": [],
    }
    jsonschema.Draft202012Validator(schema).validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(
            {
                **payload,
                "person": {
                    "name": "A",
                    "email": "a@b.com",
                    "phone": "1",
                    "location": {"raw": "Pune, India", "city": "Pune", "country": "IN"},
                },
            }
        )
