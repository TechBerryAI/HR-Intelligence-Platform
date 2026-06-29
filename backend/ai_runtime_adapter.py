"""
Bridge HRMS backend parsing to the AI Runtime (Provider Manager → Ollama / Grok).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
_AI_ROOT = _REPO_ROOT / "ai"
_RUNTIME_CONFIG = _AI_ROOT / "runtime" / "config" / "runtime.production.yaml"

if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

# Load AI workspace env (Ollama, XAI) then backend env overrides.
load_dotenv(_AI_ROOT / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

_last_model_version: str = "ai-runtime-v1"

_TASK_MAP = {
    "resume": "resume_parsing",
    "jd": "jd_parsing",
}


def _resolve_runtime_config() -> Path:
    """Resolve runtime YAML; supports repo-relative and backend-relative paths."""
    explicit = (os.getenv("AI_RUNTIME_CONFIG") or "").strip()
    if explicit:
        path = Path(explicit)
        if path.is_absolute():
            resolved = path.resolve()
        elif explicit.startswith(".."):
            # backend/.env style: ../ai/runtime/config/...
            resolved = (Path(__file__).resolve().parent / path).resolve()
        else:
            # repo-root style: ai/runtime/config/...
            resolved = (_REPO_ROOT / path).resolve()
        if resolved.exists():
            return resolved
    if _RUNTIME_CONFIG.exists():
        return _RUNTIME_CONFIG
    raise FileNotFoundError(
        f"AI runtime config not found. Set AI_RUNTIME_CONFIG or add {_RUNTIME_CONFIG}"
    )


def _ensure_runtime():
    from runtime import get_runtime

    return get_runtime(_resolve_runtime_config())


def _parse_json_output(output: Any) -> dict[str, Any]:
    if isinstance(output, dict):
        return output
    if isinstance(output, str):
        from providers.ollama.structured_output import extract_json_content

        text = extract_json_content(output)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("AI runtime returned non-object JSON")
        return parsed
    raise ValueError(f"AI runtime returned unsupported output type: {type(output)}")


def _apply_resume_text_fields(person: dict[str, Any], raw_resume_text: str | None, actions: list[str]) -> None:
    """Extract URLs and location from raw resume text when LLM missed them."""
    if not raw_resume_text:
        return

    url_pattern = (
        r'(https?://[^\s<>"\'\)]+|www\.[^\s<>"\'\)]+|linkedin\.com/[^\s<>"\'\)]+|'
        r'github\.com/[^\s<>"\'\)]+|twitter\.com/[^\s<>"\'\)]+|x\.com/[^\s<>"\'\)]+|'
        r'[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}[^\s<>"\'\)]*)'
    )
    found_urls = re.findall(url_pattern, raw_resume_text, re.IGNORECASE)

    if not person.get('linkedin'):
        linkedin_urls = [u for u in found_urls if 'linkedin' in u.lower() or 'linked.in' in u.lower()]
        if linkedin_urls:
            url = linkedin_urls[0].strip('.,;:')
            person['linkedin'] = url if url.startswith('http') else f'https://{url}'
            actions.append('extracted_linkedin_from_text')

    if not person.get('github'):
        github_urls = [u for u in found_urls if 'github' in u.lower()]
        if github_urls:
            url = github_urls[0].strip('.,;:')
            person['github'] = url if url.startswith('http') else f'https://{url}'
            actions.append('extracted_github_from_text')

    if not person.get('twitter'):
        twitter_urls = [u for u in found_urls if 'twitter' in u.lower() or 'x.com' in u.lower()]
        if twitter_urls:
            url = twitter_urls[0].strip('.,;:')
            person['twitter'] = url if url.startswith('http') else f'https://{url}'
            actions.append('extracted_twitter_from_text')

    if not person.get('portfolio') and not person.get('website'):
        excluded = [
            'linkedin', 'github', 'twitter', 'x.com', 'gmail', 'yahoo', 'outlook',
            'hotmail', 'email', 'mail', 'edu', 'ac.', '.gov',
        ]
        portfolio_urls = [
            u for u in found_urls
            if not any(x in u.lower() for x in excluded) and '.' in u and len(u) > 5
        ]
        if portfolio_urls:
            url = portfolio_urls[0].strip('.,;:')
            person['portfolio'] = url if url.startswith('http') else f'https://{url}'
            actions.append('extracted_portfolio_from_text')

    if not isinstance(person.get('otherUrls'), list):
        person['otherUrls'] = []

    categorized = set()
    for key in ('linkedin', 'github', 'twitter', 'portfolio', 'website'):
        val = person.get(key)
        if val:
            categorized.add(str(val).lower())

    for url in found_urls:
        url_clean = url.strip('.,;:')
        if url_clean.lower() not in categorized and url_clean not in person['otherUrls']:
            url_final = url_clean if url_clean.startswith('http') else f'https://{url_clean}'
            person['otherUrls'].append(url_final)

    if not person.get('location') or not str(person.get('location', '')).strip():
        location_patterns = [
            r'(?:location|current\s*location|address|city|based\s*in)\s*[:\-]\s*([A-Za-z\s,\.\-]+?)(?:\n|$|\.|;)',
            r'(?:location|address|city)\s*[:\-]\s*([A-Za-z\s,\.\-]+)',
        ]
        for pat in location_patterns:
            m = re.search(pat, raw_resume_text, re.IGNORECASE)
            if m and m.group(1):
                loc = m.group(1).strip().strip('.,;:')
                if 2 <= len(loc) <= 80:
                    person['location'] = loc
                    actions.append('extracted_location_from_text')
                    break

        if not person.get('location') or not str(person.get('location', '')).strip():
            header_text = raw_resume_text[:500] if len(raw_resume_text) > 500 else raw_resume_text
            cities = [
                'Mumbai', 'Delhi', 'Bangalore', 'Bengaluru', 'Hyderabad', 'Chennai',
                'Kolkata', 'Pune', 'Ahmedabad', 'Gurgaon', 'Gurugram', 'Noida',
                'Faridabad', 'Jaipur', 'Lucknow',
            ]
            for city in cities:
                if city in header_text:
                    person['location'] = city
                    actions.append('extracted_location_from_header')
                    break


def _first_nonempty(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and len(value) == 0:
            continue
        return value
    return None


def _repair_resume_structure(data: dict[str, Any], raw_resume_text: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """Normalize common LLM shape drift into milestone resume schema. Returns (repaired, actions)."""
    actions: list[str] = []
    source = dict(data) if isinstance(data, dict) else {}

    person_raw = source.get("person") or source.get("candidate")
    if not isinstance(person_raw, dict):
        person_raw = {
            "name": source.get("name", ""),
            "email": source.get("email", ""),
            "phone": source.get("phone", ""),
            "location": source.get("location", ""),
        }
        if any(person_raw.values()):
            actions.append("coalesced_top_level_person_fields")

    person = dict(person_raw) if isinstance(person_raw, dict) else {}
    links_raw = source.get("links")
    if isinstance(links_raw, dict):
        link_map = {
            "linkedin": ("linkedin", "linkedIn"),
            "github": ("github",),
            "portfolio": ("portfolio",),
            "website": ("website", "site"),
            "twitter": ("twitter", "x"),
        }
        for canon, aliases in link_map.items():
            if not person.get(canon):
                for alias in aliases:
                    val = links_raw.get(alias)
                    if val:
                        person[canon] = _str(val)
                        actions.append(f"coalesced_links_{canon}")
                        break
        other_urls = links_raw.get("otherUrls") or links_raw.get("other")
        if other_urls and not person.get("otherUrls"):
            person["otherUrls"] = _ensure_array(other_urls)
            actions.append("coalesced_links_otherUrls")

    languages = _first_nonempty(source, "languages") or []
    if isinstance(languages, dict):
        languages = [
            {"language": key, "proficiency": value}
            for key, value in languages.items()
            if not isinstance(key, str) or not key.endswith("Language")
        ] or [
            {"language": languages.get("nativeLanguage", ""), "proficiency": "native"},
            *[
                {"language": lang, "proficiency": "conversational"}
                for lang in languages.get("conversationalLanguages", [])
            ],
        ]
        actions.append("coerced_languages_dict")

    experience_raw = _first_nonempty(
        source, "experience", "experiences", "work_experience", "employment",
    )
    if experience_raw is not None and experience_raw != source.get("experience"):
        actions.append("coalesced_experiences_alias")

    education_raw = _first_nonempty(source, "education", "educations", "academic_background")
    if education_raw is not None and education_raw != source.get("education"):
        actions.append("coalesced_education_alias")

    projects_raw = _first_nonempty(source, "projects", "personal_projects")
    if projects_raw is not None and projects_raw != source.get("projects"):
        actions.append("coalesced_projects_alias")

    certs_raw = _first_nonempty(source, "certifications", "certificates", "licenses")
    if certs_raw is not None and certs_raw != source.get("certifications"):
        actions.append("coalesced_certifications_alias")

    summary_raw = _first_nonempty(source, "summary", "objective", "profile_summary")
    if summary_raw is not None and summary_raw != source.get("summary"):
        actions.append("coalesced_summary_alias")

    skills, skill_actions = _collect_skills_from_source(source)
    actions.extend(skill_actions)

    repaired = {
        "type": "resume",
        "person": person,
        "skills": skills,
        "experience": _normalize_experience(experience_raw or []),
        "education": _normalize_education(education_raw or []),
        "projects": _ensure_array(projects_raw or []),
        "certifications": _normalize_certifications(certs_raw or []),
        "languages": languages if isinstance(languages, list) else _ensure_array(languages),
        "summary": _str(summary_raw) if isinstance(summary_raw, str) else summary_raw,
        "total_experience_years": source.get("total_experience_years"),
    }

    for key in (
        "type", "person", "skills", "experience", "education",
        "projects", "certifications", "languages", "summary", "total_experience_years",
    ):
        if key not in repaired:
            repaired[key] = [] if key in ("skills", "experience", "education", "projects", "certifications", "languages") else (
                {} if key == "person" else ("" if key == "summary" else None)
            )

    _apply_resume_text_fields(repaired["person"], raw_resume_text, actions)
    repaired["type"] = "resume"
    return repaired, actions


def repair_resume_toon(data: dict[str, Any], raw_resume_text: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """Public resume repair entry point for the parse pipeline."""
    return _repair_resume_structure(data, raw_resume_text=raw_resume_text)


def _repair_jd_structure(data: dict[str, Any], raw_jd_text: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """Normalize common LLM shape drift into milestone JD schema. Returns (repaired, actions)."""
    actions: list[str] = []
    source = dict(data) if isinstance(data, dict) else {}

    nested_job = source.get("job")
    if isinstance(nested_job, dict):
        source = {**nested_job, **{k: v for k, v in source.items() if k != "job"}}
        actions.append("flattened_nested_job")

    def _first_nonempty(*keys: str) -> Any:
        for key in keys:
            val = source.get(key)
            if val is None:
                continue
            if isinstance(val, str) and not val.strip():
                continue
            if isinstance(val, list) and len(val) == 0:
                continue
            return val
        return None

    resp_raw = _first_nonempty(
        "responsibilities", "duties", "key_responsibilities",
        "role_responsibilities", "responsibilities_list",
    )
    if resp_raw is not source.get("responsibilities") and resp_raw is not None:
        actions.append("coalesced_responsibilities_alias")

    repaired = {
        "type": "job_description",
        "title": _str(source.get("title") or source.get("job_title")),
        "company": _str(source.get("company")),
        "location": _str(source.get("location")),
        "employment_type": _str(source.get("employment_type") or source.get("employmentType")),
        "skills": _normalize_skills(source.get("skills")),
        "mandatory_skills": _normalize_skills(
            source.get("mandatory_skills") or source.get("required_skills")
        ),
        "preferred_skills": _normalize_skills(
            source.get("preferred_skills") or source.get("nice_to_have_skills")
        ),
        "responsibilities": _ensure_string_array(resp_raw),
        "qualifications": _ensure_string_array(
            _first_nonempty("qualifications", "requirements", "education_requirements")
        ),
        "benefits": _ensure_string_array(source.get("benefits")),
        "keywords": _ensure_string_array(source.get("keywords")),
        "description": _str(source.get("description")),
        "min_experience_years": source.get("min_experience_years"),
        "max_experience_years": source.get("max_experience_years"),
        "salary_range": _str(source.get("salary_range") or source.get("salary")),
        "confidence": source.get("confidence"),
    }

    if isinstance(resp_raw, str) and repaired["responsibilities"]:
        actions.append("coerced_responsibilities_string")

    if not repaired.get("mandatory_skills") and repaired.get("skills"):
        repaired["mandatory_skills"] = _normalize_skills(repaired.get("skills"))
    if not repaired.get("skills"):
        repaired["skills"] = list(repaired.get("mandatory_skills") or []) + list(
            repaired.get("preferred_skills") or []
        )

    if not repaired["responsibilities"]:
        desc = repaired.get("description") or ""
        if desc:
            from jd_text_inference import extract_responsibilities_from_text
            inferred = extract_responsibilities_from_text(desc)
            if inferred:
                repaired["responsibilities"] = inferred
                actions.append("inferred_responsibilities_from_description")

    if not repaired["responsibilities"] and raw_jd_text:
        from jd_text_inference import extract_responsibilities_from_text, infer_jd_fields_from_text
        inferred = extract_responsibilities_from_text(raw_jd_text)
        if inferred:
            repaired["responsibilities"] = inferred
            actions.append("inferred_responsibilities_from_raw_text")
        inferred_fields = infer_jd_fields_from_text(raw_jd_text)
        if not repaired.get("location") and inferred_fields.get("location"):
            repaired["location"] = inferred_fields["location"]
            actions.append("inferred_location_from_raw_text")
        if not repaired.get("skills") and inferred_fields.get("skills"):
            repaired["skills"] = inferred_fields["skills"]
            repaired["mandatory_skills"] = inferred_fields.get("mandatory_skills") or inferred_fields["skills"]
            if inferred_fields.get("preferred_skills"):
                repaired["preferred_skills"] = inferred_fields["preferred_skills"]
            actions.append("inferred_skills_from_raw_text")

    if not repaired.get("qualifications"):
        desc = repaired.get("description") or raw_jd_text or ""
        if desc:
            from jd_text_inference import extract_qualifications_from_text
            quals = extract_qualifications_from_text(desc)
            if quals:
                repaired["qualifications"] = quals
                actions.append("inferred_qualifications_from_text")

    repaired["type"] = "job_description"
    return repaired, actions


def repair_jd_toon(data: dict[str, Any], raw_jd_text: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """Public JD repair entry point for the parse pipeline."""
    return _repair_jd_structure(data, raw_jd_text=raw_jd_text)


def parse_via_runtime(text: str, doc_type: Literal["resume", "jd"]) -> dict[str, Any]:
    """Run AI Runtime task and return validated structured output dict."""
    global _last_model_version

    task_name = _TASK_MAP[doc_type]
    runtime = _ensure_runtime()
    result = runtime.run_task(task_name, text)
    _last_model_version = f"{result.provider_id}/{result.model}"
    output = _parse_json_output(result.output)
    # Resume/JD repair runs in resume_toon_pipeline / jd_toon_pipeline (single repair path)
    if not isinstance(output, dict):
        raise ValueError(f"AI runtime returned non-dict output for {task_name}")
    return output


def get_model_version() -> str:
    return _last_model_version


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _split_string_to_items(text: str) -> list[str]:
    import re
    raw = text.strip()
    if not raw:
        return []
    if '|' in raw:
        parts = [p.strip() for p in raw.split('|')]
    elif ',' in raw and '\n' not in raw:
        parts = [p.strip() for p in raw.split(',')]
    else:
        parts = [p.strip() for p in re.split(r'\n+', raw)]
    result: list[str] = []
    for part in parts:
        cleaned = re.sub(r'^[\s•·\-\*]+', '', part).strip()
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
        if cleaned:
            result.append(cleaned)
    return result


def _ensure_string_array(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_string_to_items(value)
    if isinstance(value, dict):
        for key in ("text", "description", "value", "name", "title"):
            if key in value and value[key]:
                return _ensure_string_array(value[key])
        return []
    if isinstance(value, list):
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            if isinstance(item, str):
                for part in _split_string_to_items(item):
                    key = part.lower()
                    if key not in seen:
                        seen.add(key)
                        result.append(part)
            elif isinstance(item, dict):
                for part in _ensure_string_array(item):
                    key = part.lower()
                    if key not in seen:
                        seen.add(key)
                        result.append(part)
            elif item is not None:
                part = _str(item)
                if part:
                    key = part.lower()
                    if key not in seen:
                        seen.add(key)
                        result.append(part)
        return result
    part = _str(value)
    return [part] if part else []


def _ensure_array(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        items = _split_string_to_items(value)
        return items if items else []
    if isinstance(value, dict):
        return _ensure_string_array(value)
    return [value]


def _normalize_skills(skills: Any) -> list:
    items = _ensure_array(skills)
    normalized: list = []
    for item in items:
        if isinstance(item, str):
            if item.strip():
                normalized.append(item.strip())
        elif isinstance(item, dict):
            name = item.get("name") or item.get("skill")
            if name:
                normalized.append(_str(name))
        elif item is not None:
            normalized.append(_str(item))
    return normalized


_SKILL_SOURCE_KEYS = (
    "skills",
    "technical_skills",
    "core_skills",
    "key_skills",
    "tools",
    "technologies",
    "frameworks",
    "programming_languages",
)


def _dedupe_skills_preserve_case(skills: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for skill in skills:
        if not skill or not str(skill).strip():
            continue
        key = str(skill).strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(str(skill).strip())
    return result


def _collect_skills_from_source(source: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Merge skills from common LLM keys and nested groups; dedupe case-insensitively."""
    actions: list[str] = []
    merged: list[str] = []

    def extend_skills(raw: Any, action: str | None = None) -> None:
        nonlocal merged
        before = len(merged)
        merged.extend(_normalize_skills(raw))
        if action and len(merged) > before:
            actions.append(action)

    for key in _SKILL_SOURCE_KEYS:
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

    return _dedupe_skills_preserve_case(merged), actions


def _normalize_certifications(certs: Any) -> list:
    items = _ensure_array(certs)
    normalized: list = []
    for item in items:
        if isinstance(item, str):
            if item.strip():
                normalized.append({"name": item.strip()})
        elif isinstance(item, dict):
            normalized.append({
                "name": _str(item.get("name") or item.get("title")),
                "issuer": _str(item.get("issuer") or item.get("organization")),
            })
        elif item is not None:
            normalized.append({"name": _str(item)})
    return normalized


def _normalize_experience(experience: Any) -> list:
    items = _ensure_array(experience)
    normalized: list = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "title": _str(item.get("title") or item.get("role")),
            "company": _str(item.get("company") or item.get("employer")),
            "from": _str(item.get("from") or item.get("start") or item.get("start_date")),
            "to": _str(item.get("to") or item.get("end") or item.get("end_date")),
            "years": item.get("years"),
            "description": _str(item.get("description")),
        })
    return normalized


def _normalize_education(education: Any) -> list:
    items = _ensure_array(education)
    normalized: list = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "degree": _str(item.get("degree")),
            "field": _str(item.get("field") or item.get("major")),
            "institution": _str(item.get("institution") or item.get("school")),
            "year": _str(item.get("year") or item.get("to") or item.get("end")),
        })
    return normalized


def _normalize_person(person: Any) -> dict[str, Any]:
    if not isinstance(person, dict):
        person = {}
    return {
        "name": _str(person.get("name")),
        "email": _str(person.get("email")),
        "phone": _str(person.get("phone")),
        "location": _str(person.get("location")),
        "linkedin": _str(person.get("linkedin")) or None,
        "github": _str(person.get("github")) or None,
        "portfolio": _str(person.get("portfolio")) or None,
        "website": _str(person.get("website")) or None,
        "twitter": _str(person.get("twitter")) or None,
        "otherUrls": person.get("otherUrls") if isinstance(person.get("otherUrls"), list) else [],
    }


def normalize_proposal(structured: dict[str, Any], doc_type: Literal["resume", "jd"]) -> dict[str, Any]:
    """Map runtime structured JSON to legacy TOON shape expected by backend validation."""
    if doc_type == "resume":
        toon_type = "resume"
        person = _normalize_person(structured.get("person") or structured.get("candidate"))
        return {
            "type": toon_type,
            "person": person,
            "skills": _normalize_skills(structured.get("skills")),
            "experience": _normalize_experience(structured.get("experience")),
            "education": _normalize_education(structured.get("education")),
            "projects": _ensure_array(structured.get("projects")),
            "certifications": _normalize_certifications(structured.get("certifications")),
            "languages": _ensure_array(structured.get("languages")),
            "summary": _str(structured.get("summary")) or None,
            "total_experience_years": structured.get("total_experience_years"),
        }

    # JD parsing — preserve ATS-critical fields
    mandatory = _normalize_skills(structured.get("mandatory_skills") or structured.get("required_skills"))
    preferred = _normalize_skills(structured.get("preferred_skills") or structured.get("nice_to_have_skills"))
    skills = _normalize_skills(structured.get("skills"))
    if not mandatory and skills:
        mandatory = skills
    if not skills:
        skills = list(mandatory) + list(preferred)
    return {
        "type": "job_description",
        "title": _str(structured.get("title")),
        "company": _str(structured.get("company")),
        "location": _str(structured.get("location")),
        "employment_type": _str(structured.get("employment_type") or structured.get("employmentType")),
        "skills": skills,
        "mandatory_skills": mandatory,
        "preferred_skills": preferred,
        "responsibilities": _ensure_string_array(structured.get("responsibilities")),
        "qualifications": _ensure_string_array(structured.get("qualifications")),
        "benefits": _ensure_string_array(structured.get("benefits")),
        "keywords": _ensure_string_array(structured.get("keywords")),
        "description": _str(structured.get("description")),
        "min_experience_years": structured.get("min_experience_years"),
        "max_experience_years": structured.get("max_experience_years"),
        "salary_range": _str(structured.get("salary_range") or structured.get("salary")),
        "confidence": structured.get("confidence"),
    }
