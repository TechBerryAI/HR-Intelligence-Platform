"""Capability package tests for interview_generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from capabilities.loader import load_capability


CAPABILITY_DIR = Path(__file__).resolve().parent.parent


def test_capability_loads() -> None:
    package = load_capability(CAPABILITY_DIR)
    assert package.id == "interview_generation"
    assert package.metadata.version == "1.0.0"


def test_capability_has_prompt_template() -> None:
    package = load_capability(CAPABILITY_DIR)
    assert "{{input}}" in package.prompt_text
    assert "interview_generation_v1" in package.prompt_text or "interview_generation" in package.prompt_text


def test_capability_schema_has_id() -> None:
    package = load_capability(CAPABILITY_DIR)
    assert package.schema_doc.get("$id") == "interview_v1"


def test_capability_runtime_config() -> None:
    package = load_capability(CAPABILITY_DIR)
    assert package.runtime_config.preferred_model_alias == "interview-generator"


def test_capability_validation_rules() -> None:
    package = load_capability(CAPABILITY_DIR)
    assert "schema_validate" in package.validation_rules
