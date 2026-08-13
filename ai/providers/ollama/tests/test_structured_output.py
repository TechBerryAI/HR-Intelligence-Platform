"""Structured output normalization tests."""

from __future__ import annotations

import json

from providers.ollama.structured_output import (
    build_messages,
    extract_json_content,
    normalize_content,
    resolve_response_format,
)


def test_build_messages_combines_prompt_and_input() -> None:
    messages = build_messages(prompt="Parse this resume:", input_text="Jane Doe")
    assert messages == [
        {"role": "system", "content": "Parse this resume:"},
        {"role": "user", "content": "Jane Doe"},
    ]


def test_resolve_response_format_json_when_schema_present() -> None:
    assert resolve_response_format("resume_v1") == "json"
    assert resolve_response_format(None) is None
    schema = {"type": "object", "properties": {"type": {"const": "resume"}}}
    assert resolve_response_format("resume_v1", schema) == schema


def test_extract_json_from_markdown_fence() -> None:
    payload = {"type": "resume"}
    fenced = f"```json\n{json.dumps(payload)}\n```"
    assert json.loads(extract_json_content(fenced)) == payload


def test_normalize_content_reformats_json() -> None:
    raw = '  {"type": "resume", "person": {"name": "A", "email": "a@b.com", "phone": "1"}}  '
    normalized = normalize_content(raw, schema_id="resume_v1")
    assert json.loads(normalized)["type"] == "resume"


def test_normalize_content_passthrough_text() -> None:
    assert normalize_content("  hello world  ", schema_id=None) == "hello world"
