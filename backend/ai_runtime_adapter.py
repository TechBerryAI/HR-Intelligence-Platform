"""
Bridge HRMS backend parsing to the AI Runtime (Provider Manager → Ollama / Grok).
"""
from __future__ import annotations

import json
import os
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


def _repair_resume_structure(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize common LLM shape drift into milestone resume schema."""
    if data.get("type") == "resume" and isinstance(data.get("person"), dict):
        return data

    person = data.get("person")
    if not isinstance(person, dict):
        person = {
            "name": data.get("name", ""),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "location": data.get("location", ""),
        }

    skills = data.get("skills", [])
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]

    experience = data.get("experience", data.get("experiences", []))
    education = data.get("education", [])

    languages = data.get("languages", [])
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

    return {
        "type": "resume",
        "person": person,
        "skills": skills if isinstance(skills, list) else [],
        "experience": experience if isinstance(experience, list) else [],
        "education": education if isinstance(education, list) else [],
        "projects": data.get("projects", []) if isinstance(data.get("projects"), list) else [],
        "certifications": data.get("certifications", []) if isinstance(data.get("certifications"), list) else [],
        "languages": languages if isinstance(languages, list) else [],
        "summary": data.get("summary"),
        "total_experience_years": data.get("total_experience_years"),
    }


def parse_via_runtime(text: str, doc_type: Literal["resume", "jd"]) -> dict[str, Any]:
    """Run AI Runtime task and return validated structured output dict."""
    global _last_model_version

    task_name = _TASK_MAP[doc_type]
    runtime = _ensure_runtime()
    result = runtime.run_task(task_name, text)
    _last_model_version = f"{result.provider_id}/{result.model}"
    output = _parse_json_output(result.output)
    if doc_type == "resume":
        output = _repair_resume_structure(output)
    if not isinstance(output, dict):
        raise ValueError(f"AI runtime returned non-dict output for {task_name}")
    return output


def get_model_version() -> str:
    return _last_model_version


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _ensure_array(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
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

    # JD parsing — minimal normalization for gateway path
    return {
        "type": "job_description",
        "title": _str(structured.get("title")),
        "location": _str(structured.get("location")),
        "skills": _normalize_skills(structured.get("skills")),
        "responsibilities": _ensure_array(structured.get("responsibilities")),
        "qualifications": _ensure_array(structured.get("qualifications")),
        "description": _str(structured.get("description")),
    }
