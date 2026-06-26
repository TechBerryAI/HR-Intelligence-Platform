"""Proposal mapping tests for resume_parsing capability."""

from __future__ import annotations

from pathlib import Path

import yaml


CAPABILITY_DIR = Path(__file__).resolve().parent.parent


def _load_mapping() -> dict:
    with (CAPABILITY_DIR / "proposal_mapping.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_mapping_targets_resume_v1() -> None:
    doc = _load_mapping()
    assert doc["mapping"]["target_schema"] == "resume_v1"


def test_mapping_declares_all_root_sections() -> None:
    doc = _load_mapping()
    root = doc["root"]
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
    assert expected == set(root.keys())


def test_experience_date_alias_mapping() -> None:
    doc = _load_mapping()
    from_field = doc["experience_item"]["from"]
    to_field = doc["experience_item"]["to"]
    assert "start_date" in from_field["aliases"]
    assert "end_date" in to_field["aliases"]
    assert from_field["canonical"] == "experience[].from"
    assert to_field["canonical"] == "experience[].to"


def test_person_contact_aliases() -> None:
    doc = _load_mapping()
    root_person = doc["root"]["person"]
    person_fields = doc["person"]
    assert "personal_information" in root_person["aliases"]
    assert "email_address" in person_fields["email"]["aliases"]


def test_post_mapping_normalization_steps() -> None:
    doc = _load_mapping()
    step_ids = {step["id"] for step in doc["post_mapping"]}
    assert "dedupe_skills" in step_ids
    assert "normalize_experience_dates" in step_ids
    assert "merge_person_links" in step_ids


def test_omitted_on_toon_includes_normalized_only_sections() -> None:
    doc = _load_mapping()
    omitted = set(doc["omitted_on_toon"])
    assert "projects" in omitted
    assert "awards" in omitted
    assert "publications" in omitted
    assert "metadata" in omitted
    assert "source_tracking" in omitted


def test_transforms_catalog_complete() -> None:
    doc = _load_mapping()
    transforms = doc["transforms"]
    required_transforms = [
        "normalize_date",
        "normalize_date_present",
        "skill_array",
        "confidence_clamp",
        "location_or_string",
    ]
    for transform in required_transforms:
        assert transform in transforms, f"Missing transform: {transform}"
