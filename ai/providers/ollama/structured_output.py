"""Structured output helpers for Ollama responses."""

from __future__ import annotations

import json
import re
from typing import Any


_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)


def build_messages(*, prompt: str, input_text: str) -> list[dict[str, str]]:
    """Build Ollama chat messages from runtime prompt and input."""
    system = prompt.strip() or "Return JSON only."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": input_text},
    ]


def resolve_response_format(
    schema_id: str | None,
    schema_doc: dict[str, Any] | None = None,
) -> str | dict[str, Any] | None:
    """Return Ollama format: JSON Schema when available, else json mode."""
    if isinstance(schema_doc, dict) and schema_doc:
        return schema_doc
    if schema_id:
        return "json"
    return None


def extract_json_content(content: str) -> str:
    """Extract JSON payload from raw model text, stripping markdown fences."""
    stripped = content.strip()
    if not stripped:
        return stripped

    fence_match = _JSON_FENCE_RE.search(stripped)
    if fence_match:
        return fence_match.group(1).strip()

    if stripped.startswith("{") or stripped.startswith("["):
        return stripped

    brace_start = stripped.find("{")
    brace_end = stripped.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        return stripped[brace_start : brace_end + 1]

    return stripped


def _coerce_prompt_shapes(parsed: dict[str, Any]) -> dict[str, Any]:
    """Coerce shapes the prompts already document (skill objects → name strings)."""
    for key in ("skills", "mandatory_skills", "preferred_skills"):
        vals = parsed.get(key)
        if not isinstance(vals, list):
            continue
        out: list[Any] = []
        for item in vals:
            if isinstance(item, dict):
                name = item.get("name") or item.get("skill") or item.get("value")
                if name:
                    out.append(str(name))
            elif item is not None:
                out.append(item if isinstance(item, str) else str(item))
        parsed[key] = out
    return parsed


def normalize_content(content: str, *, schema_id: str | None) -> str:
    """Normalize provider output to runtime-expected content string."""
    if not schema_id:
        return content.strip()
    extracted = extract_json_content(content)
    try:
        parsed = json.loads(extracted)
    except json.JSONDecodeError:
        return extracted
    if isinstance(parsed, dict):
        parsed = _coerce_prompt_shapes(parsed)
        return json.dumps(parsed)
    return json.dumps(parsed)
