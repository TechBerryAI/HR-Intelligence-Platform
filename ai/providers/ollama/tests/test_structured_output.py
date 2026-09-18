"""Structured output normalization tests."""

from __future__ import annotations

import json

from providers.ollama.structured_output import (
    build_messages,
    extract_json_content,
    normalize_content,
    resolve_response_format,
)


def test_build_messages_does_not_duplicate_inlined_input() -> None:
    resume = (
        "Priya Sharma\nExperience\nDatabase Administrator\n"
        "Infosenseglobal | Dec 2024 – Present\n"
        "Administered PostgreSQL backups and failover.\n"
    )
    prompt = (
        "You are an expert resume parser. Return JSON only.\n\n"
        "## Input\n\n"
        f"{resume}"
    )
    messages = build_messages(prompt=prompt, input_text=resume)
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    payload = resume.strip()
    assert messages[1]["content"] == payload
    system = messages[0]["content"]
    assert payload not in system
    joined = f"{system}\n{messages[1]['content']}"
    assert joined.count(payload) == 1


def test_build_messages_strips_capability_prompt_input_block() -> None:
    from pathlib import Path

    prompt_path = Path(__file__).resolve().parents[3] / "capabilities" / "resume_parsing" / "prompt.md"
    template = prompt_path.read_text(encoding="utf-8")
    resume = (
        "Alex Rivera\nExperience\nPlatform Engineer\nNorthwind Labs | Jan 2020 – Present\n"
        "Built internal APIs and PostgreSQL services for HR workflows.\n"
    )
    inlined = template.replace("{{input}}", resume)
    messages = build_messages(prompt=inlined, input_text=resume)
    payload = resume.strip()
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == payload
    assert payload not in messages[0]["content"]
    assert f"{messages[0]['content']}\n{messages[1]['content']}".count(payload) == 1
    assert "{{input}}" not in messages[0]["content"]


def test_build_messages_keeps_short_input_when_not_inlined() -> None:
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


def test_normalize_coerces_location_object_and_null_strings() -> None:
    raw = {
        "type": "resume",
        "person": {
            "name": "A",
            "email": "a@b.com",
            "phone": None,
            "location": {"city": "Pune", "region": "MH", "country": "India"},
            "linkedin": None,
        },
        "skills": [{"name": "Python"}, "SQL"],
        "experience": [
            {
                "title": "Dev",
                "company": "X",
                "from": "2020",
                "to": None,
                "location": {"city": "Remote", "remote": True},
            }
        ],
        "education": [],
        "summary": None,
        "total_experience_years": None,
    }
    normalized = json.loads(normalize_content(json.dumps(raw), schema_id="resume_milestone_v1"))
    assert normalized["person"]["phone"] == ""
    assert normalized["person"]["linkedin"] == ""
    assert normalized["person"]["location"] == "Pune, MH, India"
    assert normalized["skills"] == ["Python", "SQL"]
    assert normalized["experience"][0]["to"] == ""
    assert normalized["experience"][0]["location"] == "Remote"
    assert normalized["summary"] == ""
    assert normalized["total_experience_years"] is None


def test_normalize_does_not_invent_missing_optional_fields() -> None:
    raw = {
        "type": "resume",
        "person": {"name": "A", "email": "a@b.com", "phone": "1"},
        "skills": [],
        "experience": [],
        "education": [],
    }
    normalized = json.loads(normalize_content(json.dumps(raw), schema_id="resume_milestone_v1"))
    assert "summary" not in normalized
    assert "location" not in normalized["person"]
