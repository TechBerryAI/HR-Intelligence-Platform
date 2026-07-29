"""
Resume TOON alias registry — loads proposal_mapping.yaml and provides generic coalescing.

Single source of truth for LLM field-name variance at runtime.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROPOSAL_MAPPING_PATH = (
    _REPO_ROOT / "ai" / "capabilities" / "resume_parsing" / "proposal_mapping.yaml"
)

# Fallback when YAML is unavailable (tests, minimal environments).
_FALLBACK_ROOT_ALIASES: dict[str, list[str]] = {
    "person": ["contact", "personal_information", "personal_info", "candidate"],
    "summary": ["objective", "profile", "professional_summary", "about", "profile_summary"],
    "skills": [
        "technical_skills", "core_skills", "core_competencies", "key_skills",
        "competencies", "skill_set", "tools", "technologies", "frameworks",
        "programming_languages", "expertise", "tech_stack",
    ],
    "experience": [
        "experiences", "work_experience", "employment", "employment_history",
        "work_history", "positions",
    ],
    "education": ["educations", "academic_background", "academics", "qualifications_education"],
    "projects": ["portfolio", "personal_projects", "side_projects"],
    "certifications": ["certificates", "licenses", "credentials", "professional_certifications"],
    "languages": ["language_skills", "spoken_languages"],
    "links": ["urls", "social_links", "web_presence", "profiles"],
}

_FALLBACK_PERSON_TOP_LEVEL = ["name", "email", "phone", "location"]
_FALLBACK_PERSON_ALIASES: dict[str, list[str]] = {
    "name": ["full_name", "candidate_name"],
    "email": ["email_address", "e_mail"],
    "phone": ["phone_number", "mobile", "telephone", "contact_number"],
    "location": ["address", "city", "current_location", "residence"],
}


def _load_yaml_mapping() -> dict[str, Any] | None:
    try:
        import yaml
    except ImportError:
        return None
    if not _PROPOSAL_MAPPING_PATH.exists():
        return None
    with _PROPOSAL_MAPPING_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        return None
    return data.get("mapping") or data


def _build_root_aliases(mapping: dict[str, Any] | None) -> dict[str, list[str]]:
    if not mapping:
        return dict(_FALLBACK_ROOT_ALIASES)
    root = mapping.get("root") if isinstance(mapping.get("root"), dict) else mapping
    if not isinstance(root, dict):
        return dict(_FALLBACK_ROOT_ALIASES)
    result: dict[str, list[str]] = {}
    for _key, spec in root.items():
        if not isinstance(spec, dict):
            continue
        canonical = spec.get("canonical")
        aliases = spec.get("aliases") or []
        if not canonical:
            continue
        alias_list = [a for a in aliases if isinstance(a, str)]
        if alias_list:
            result[str(canonical)] = alias_list
    for key, aliases in _FALLBACK_ROOT_ALIASES.items():
        if key not in result:
            result[key] = list(aliases)
        else:
            merged = list(result[key])
            for alias in aliases:
                if alias not in merged:
                    merged.append(alias)
            result[key] = merged
    return result


def _build_person_aliases(mapping: dict[str, Any] | None) -> dict[str, list[str]]:
    if not mapping:
        return dict(_FALLBACK_PERSON_ALIASES)
    person = mapping.get("person")
    if not isinstance(person, dict):
        return dict(_FALLBACK_PERSON_ALIASES)
    result: dict[str, list[str]] = {}
    for field, spec in person.items():
        if not isinstance(spec, dict):
            continue
        aliases = spec.get("aliases") or []
        alias_list = [a for a in aliases if isinstance(a, str)]
        if alias_list:
            result[str(field)] = alias_list
    for key, aliases in _FALLBACK_PERSON_ALIASES.items():
        if key not in result:
            result[key] = list(aliases)
    return result


_MAPPING = _load_yaml_mapping()
ROOT_FIELD_ALIASES: dict[str, list[str]] = _build_root_aliases(_MAPPING)
PERSON_FIELD_ALIASES: dict[str, list[str]] = _build_person_aliases(_MAPPING)
PERSON_TOP_LEVEL_FIELDS: tuple[str, ...] = tuple(_FALLBACK_PERSON_TOP_LEVEL)

SKILL_SOURCE_KEYS: tuple[str, ...] = ("skills",) + tuple(ROOT_FIELD_ALIASES.get("skills", []))


def _is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def first_nonempty(source: dict[str, Any], canonical: str, aliases: list[str] | None = None) -> Any:
    """Return first non-empty value for canonical key or any alias."""
    keys = [canonical] + list(aliases or ROOT_FIELD_ALIASES.get(canonical, []))
    for key in keys:
        value = source.get(key)
        if _is_nonempty(value):
            return value
    return None


def coalesce_root_field(
    source: dict[str, Any],
    canonical: str,
    *,
    aliases: list[str] | None = None,
) -> tuple[Any, list[str]]:
    """Coalesce a root-level field from canonical key and aliases."""
    actions: list[str] = []
    alias_list = aliases if aliases is not None else ROOT_FIELD_ALIASES.get(canonical, [])
    all_keys = [canonical] + [a for a in alias_list if a != canonical]
    value = None
    used_key: str | None = None
    for key in all_keys:
        candidate = source.get(key)
        if _is_nonempty(candidate):
            value = candidate
            used_key = key
            break
    if used_key and used_key != canonical:
        actions.append(f"coalesced_{used_key}")
    return value, actions


def merge_top_level_person_fields(
    source: dict[str, Any],
    person: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Merge top-level person scalars into person dict when person fields are empty."""
    actions: list[str] = []
    merged = dict(person) if isinstance(person, dict) else {}
    for field in PERSON_TOP_LEVEL_FIELDS:
        if not _is_nonempty(merged.get(field)):
            top_val = source.get(field)
            if _is_nonempty(top_val):
                merged[field] = top_val
                actions.append(f"coalesced_top_level_{field}")
    person_aliases = PERSON_FIELD_ALIASES
    for field, aliases in person_aliases.items():
        if not _is_nonempty(merged.get(field)):
            for alias in aliases:
                val = source.get(alias)
                if _is_nonempty(val):
                    merged[field] = val
                    actions.append(f"coalesced_person_alias_{alias}")
                    break
    return merged, actions


def coalesce_skill_sources(
    source: dict[str, Any],
    *,
    normalize_skills: Callable[[Any], list[str]],
    dedupe_skills: Callable[[list[str]], list[str]],
) -> tuple[list[str], list[str]]:
    """Merge skills from all skill-bearing alias keys and nested groups."""
    actions: list[str] = []
    merged: list[str] = []

    def extend_skills(raw: Any, action: str | None = None) -> None:
        nonlocal merged
        before = len(merged)
        merged.extend(normalize_skills(raw))
        if action and len(merged) > before:
            actions.append(action)

    for key in SKILL_SOURCE_KEYS:
        raw = source.get(key)
        if raw is None:
            continue
        if key == "skills" and isinstance(raw, dict):
            for sub_val in raw.values():
                extend_skills(sub_val, "flattened_nested_skills")
            continue
        action = None if key == "skills" else f"coalesced_{key}"
        extend_skills(raw, action)

    skill_groups = source.get("skill_groups")
    if isinstance(skill_groups, dict):
        for group_val in skill_groups.values():
            extend_skills(group_val, "flattened_skill_groups")

    if isinstance(source.get("skills"), str) and merged:
        actions.append("coerced_skills_string")

    return dedupe_skills(merged), actions
