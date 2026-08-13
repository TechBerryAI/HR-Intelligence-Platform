"""Structured output helpers for Ollama responses."""

from __future__ import annotations

import json
import re
from typing import Any


_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)

_PERSON_STRING_FIELDS = (
    "name",
    "email",
    "phone",
    "location",
    "linkedin",
    "github",
    "portfolio",
    "website",
    "twitter",
)
_EXPERIENCE_STRING_FIELDS = (
    "title",
    "role",
    "company",
    "from",
    "to",
    "description",
    "location",
)
_EDUCATION_STRING_FIELDS = (
    "degree",
    "institution",
    "school",
    "field",
    "year",
    "from",
    "to",
    "gpa",
    "cgpa",
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


def _as_nonempty_str(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value).strip()
    return ""


def _location_object_to_string(value: dict[str, Any]) -> str:
    """Flatten {city,region,country} / {raw} / remote into a location string."""
    raw = _as_nonempty_str(
        value.get("raw") or value.get("name") or value.get("text") or value.get("value")
    )
    city = _as_nonempty_str(value.get("city"))
    region = _as_nonempty_str(value.get("region") or value.get("state"))
    country = _as_nonempty_str(value.get("country"))
    parts = [p for p in (city, region, country) if p]
    if parts:
        return ", ".join(parts)
    if value.get("remote") is True:
        return "Remote"
    return raw


def _null_to_empty_string(value: Any) -> Any:
    """Prompt contract: unknown string fields are \"\", never JSON null."""
    return "" if value is None else value


def _coerce_string_field(value: Any, *, allow_location_object: bool = False) -> Any:
    if value is None:
        return ""
    if allow_location_object and isinstance(value, dict):
        return _location_object_to_string(value)
    return value


def _coerce_record_string_fields(
    items: Any,
    fields: tuple[str, ...],
    *,
    location_fields: frozenset[str] = frozenset(),
) -> None:
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        for field in fields:
            if field not in item:
                continue
            item[field] = _coerce_string_field(
                item.get(field),
                allow_location_object=field in location_fields,
            )


def _coerce_prompt_shapes(parsed: dict[str, Any]) -> dict[str, Any]:
    """Coerce documented LLM shapes before jsonschema (do not invent values)."""
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

    person = parsed.get("person")
    if isinstance(person, dict):
        if "location" in person:
            person["location"] = _coerce_string_field(
                person.get("location"),
                allow_location_object=True,
            )
        for field in _PERSON_STRING_FIELDS:
            if field == "location":
                continue
            if field in person:
                person[field] = _null_to_empty_string(person.get(field))

    if "summary" in parsed:
        parsed["summary"] = _null_to_empty_string(parsed.get("summary"))

    _coerce_record_string_fields(
        parsed.get("experience"),
        _EXPERIENCE_STRING_FIELDS,
        location_fields=frozenset({"location"}),
    )
    _coerce_record_string_fields(parsed.get("education"), _EDUCATION_STRING_FIELDS)
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
