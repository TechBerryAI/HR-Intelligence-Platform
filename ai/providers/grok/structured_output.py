"""Structured output helpers for Grok responses."""

from __future__ import annotations

import json

from providers.ollama.structured_output import build_messages as _ollama_build_messages
from providers.ollama.structured_output import extract_json_content


def normalize_content(content: str, *, schema_id: str | None) -> str:
    if not schema_id:
        return content.strip()
    extracted = extract_json_content(content)
    try:
        parsed = json.loads(extracted)
    except json.JSONDecodeError:
        return extracted
    return json.dumps(parsed)


def build_messages(*, prompt: str, input_text: str) -> list[dict[str, str]]:
    return _ollama_build_messages(
        prompt=prompt,
        input_text=input_text,
        default_system="You are a structured data extraction assistant. Return JSON only.",
    )
