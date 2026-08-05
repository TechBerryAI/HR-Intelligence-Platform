"""Capability package tests for resume_parsing."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from capabilities.loader import load_capability


CAPABILITY_DIR = Path(__file__).resolve().parent.parent


def _load_yaml(name: str) -> dict:
    with (CAPABILITY_DIR / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _minimal_valid_resume() -> dict:
    return {
        "type": "resume",
        "person": {"name": "A", "email": "a@example.com", "phone": "+15550100"},
        "skills": ["Python"],
        "experience": [
            {
                "title": "Engineer",
                "company": "Acme",
                "from": "2020-01",
                "to": "Present",
                "years": 5,
            }
        ],
        "education": [{"degree": "BSc", "field": "CS", "institution": "University", "year": "2019"}],
        "confidence": 0.9,
    }


def test_capability_loads() -> None:
    package = load_capability(CAPABILITY_DIR)
    assert package.id == "resume_parsing"
    assert package.metadata.version == "1.0.0"


def test_capability_has_prompt_template() -> None:
    package = load_capability(CAPABILITY_DIR)
    assert "{{input}}" in package.prompt_text
    template = (CAPABILITY_DIR / "prompt.template.md").read_text(encoding="utf-8")
    assert "## Role" in template
    assert "{{input}}" in template


def test_capability_schema_has_id() -> None:
    package = load_capability(CAPABILITY_DIR)
    assert package.schema_doc.get("$id") == "resume_milestone_v1"


def test_capability_runtime_config() -> None:
    package = load_capability(CAPABILITY_DIR)
    assert package.runtime_config.preferred_model_alias == "resume-parser"
    assert package.runtime_config.output_mode == "json"
    assert package.runtime_config.temperature == 0.1


def test_capability_validation_rules() -> None:
    package = load_capability(CAPABILITY_DIR)
    rules = package.validation_rules
    assert rules.get("schema_validate") is True
    assert "required_fields" in rules
    assert "nested_required" in rules
    assert "person" in (rules.get("nested_required") or {})


def test_capability_asset_files_exist() -> None:
    required_assets = [
        "capability.yaml",
        "schema.json",
        "validation.yaml",
        "runtime.yaml",
        "proposal_mapping.yaml",
        "field_definitions.yaml",
        "prompt.template.md",
        "prompt.md",
        "benchmarks/benchmark.yaml",
        "README.md",
    ]
    for asset in required_assets:
        assert (CAPABILITY_DIR / asset).exists(), f"Missing asset: {asset}"


def test_schema_validates_minimal_resume() -> None:
    package = load_capability(CAPABILITY_DIR)
    jsonschema.Draft202012Validator(package.schema_doc).validate(_minimal_valid_resume())


def test_schema_rejects_wrong_type() -> None:
    package = load_capability(CAPABILITY_DIR)
    invalid = _minimal_valid_resume()
    invalid["type"] = "job_description"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(package.schema_doc).validate(invalid)


def test_schema_supports_extended_sections() -> None:
    package = load_capability(CAPABILITY_DIR)
    payload = _minimal_valid_resume()
    payload.update(
        {
            "projects": [{"name": "App", "technologies": ["React"]}],
            "awards": [{"name": "Award"}],
            "publications": [{"title": "Paper", "year": "2021"}],
            "links": [{"type": "github", "url": "https://github.com/example"}],
            "source_tracking": {"extraction_method": "llm", "field_sources": []},
            "metadata": {"parser_version": "1.0.0", "capability_id": "resume_parsing"},
            "validation": {"is_valid": True, "toon_projectable": True, "errors": [], "warnings": []},
        }
    )
    jsonschema.Draft202012Validator(package.schema_doc).validate(payload)


def test_schema_skill_polymorphism() -> None:
    """Milestone schema uses string skill items (autofill-aligned)."""
    package = load_capability(CAPABILITY_DIR)
    payload = _minimal_valid_resume()
    payload["skills"] = ["Python", "AWS", "SQL"]
    jsonschema.Draft202012Validator(package.schema_doc).validate(payload)


def test_proposal_mapping_structure() -> None:
    mapping = _load_yaml("proposal_mapping.yaml")
    assert mapping["mapping"]["target_schema"] == "resume_v1"
    assert mapping["mapping"]["capability"] == "resume_parsing"
    assert "root" in mapping
    assert "person" in mapping
    assert "experience_item" in mapping
    assert "post_mapping" in mapping
    assert "transforms" in mapping
    assert mapping["root"]["type"]["canonical"] == "type"
    assert "start_date" in mapping["experience_item"]["from"]["aliases"]


def test_proposal_mapping_provider_independent() -> None:
    mapping = _load_yaml("proposal_mapping.yaml")
    description = mapping["mapping"]["description"]
    assert "provider" in description.lower()
    root_keys = set(mapping["root"].keys())
    for provider_specific in ("openai", "ollama", "grok", "anthropic"):
        assert provider_specific not in root_keys


def test_field_definitions_covers_root_fields() -> None:
    defs = _load_yaml("field_definitions.yaml")
    root = defs["root"]
    expected = {
        "type",
        "person",
        "summary",
        "skills",
        "experience",
        "education",
        "projects",
        "certifications",
        "languages",
        "awards",
        "publications",
        "links",
        "total_experience_years",
        "confidence",
        "source_tracking",
        "metadata",
        "validation",
    }
    assert expected.issubset(set(root.keys()))
    for field_name, field_def in root.items():
        assert "purpose" in field_def, field_name
        assert "business_meaning" in field_def, field_name
        assert "normalization_rules" in field_def, field_name


def test_benchmark_profiles_complete() -> None:
    benchmark_doc = _load_yaml("benchmarks/benchmark.yaml")
    benchmark = benchmark_doc["benchmark"]
    profiles = benchmark_doc["profiles"]
    expected_profiles = {
        "excellent_resume",
        "average_resume",
        "poor_resume",
        "fresh_graduate",
        "senior_engineer",
        "executive",
        "career_gap",
        "career_switch",
        "multiple_degrees",
        "international_resume",
    }
    assert expected_profiles == set(profiles.keys())
    for profile_id, profile in profiles.items():
        template_path = CAPABILITY_DIR / profile["template"]
        assert template_path.exists(), f"Missing benchmark template: {profile['template']}"


def test_capability_yaml_references_assets() -> None:
    meta = _load_yaml("capability.yaml")["capability"]
    assert meta["proposal_mapping"]["file"] == "proposal_mapping.yaml"
    assert meta["field_definitions"]["file"] == "field_definitions.yaml"
    assert meta["prompt"]["template"] == "prompt.template.md"


def test_schema_json_is_valid_json() -> None:
    schema = json.loads((CAPABILITY_DIR / "schema.milestone.json").read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "resume_milestone_v1"
    assert "skills" in schema["properties"]
    assert "experience" in schema["properties"]
    assert "education" in schema["properties"]