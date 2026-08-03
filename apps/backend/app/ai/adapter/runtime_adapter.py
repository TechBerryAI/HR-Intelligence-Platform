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

_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # apps/backend
_REPO_ROOT = _BACKEND_ROOT.parent.parent  # repository root (not apps/)
_AI_ROOT = _REPO_ROOT / "ai"
_RUNTIME_CONFIG = _AI_ROOT / "runtime" / "config" / "runtime.production.yaml"

if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

# Load AI workspace env (Ollama, XAI) then backend env.
# Do not override absolute AI_RUNTIME_CONFIG already set by start.js.
_existing_runtime_config = (os.getenv("AI_RUNTIME_CONFIG") or "").strip()
load_dotenv(_AI_ROOT / ".env")
load_dotenv(_BACKEND_ROOT / ".env", override=True)
if _existing_runtime_config and Path(_existing_runtime_config).is_absolute():
    os.environ["AI_RUNTIME_CONFIG"] = _existing_runtime_config

_last_model_version: str = "ai-runtime-v1"

_TASK_MAP = {
    "resume": "resume_parsing",
    "jd": "jd_parsing",
}


def _resolve_runtime_config() -> Path:
    """Resolve runtime YAML; supports absolute, repo-relative, and backend-relative paths."""
    try:
        packages = _REPO_ROOT / "packages"
        if packages.exists() and str(packages) not in sys.path:
            sys.path.insert(0, str(packages))
        from ai_runtime import get_runtime_config_path

        shim = get_runtime_config_path()
        if shim.exists():
            return shim
    except Exception:
        pass

    explicit = (os.getenv("AI_RUNTIME_CONFIG") or "").strip()
    if explicit:
        path = Path(explicit)
        candidates: list[Path] = []
        if path.is_absolute():
            candidates.append(path)
        else:
            # Prefer repo-root style: ai/runtime/config/...
            candidates.append((_REPO_ROOT / path).resolve())
            # Backend-relative: ../../ai/... or ../ai/...
            candidates.append((_BACKEND_ROOT / path).resolve())
            # CWD-relative (last resort)
            candidates.append(path.resolve())
        for resolved in candidates:
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

    from app.ai.parser.enrichment.resume_text_inference import extract_location_from_text

    def _is_false_address_url(u: str) -> bool:
        """Reject Indian address abbreviations misread as domains (H.no, S.no, etc.)."""
        s = (u or '').strip().lower()
        s = re.sub(r'^https?://', '', s)
        host = s.split('/')[0].split('?')[0].rstrip('.')
        if re.match(
            r'^(?:h|s|plot|flat|survey|house|door|room)\.?n(?:o|umber)?\.?$',
            host.replace(' ', ''),
        ):
            return True
        if re.search(r'\bh\.?\s*no\.?\b|\bs\.?\s*no\.?\b|plot\.?\s*no|flat\.?\s*no', s):
            return True
        # Single-letter hostname + junk TLD (h.no)
        parts = host.split('.')
        if len(parts) == 2 and len(parts[0]) <= 1 and len(parts[1]) <= 3:
            return True
        return False

    def _normalize_url(u: str) -> str | None:
        url = (u or '').strip('.,;:')
        if not url or _is_false_address_url(url):
            return None
        return url if url.startswith('http') else f'https://{url}'

    url_pattern = (
        r'(https?://[^\s<>"\'\)]+|www\.[^\s<>"\'\)]+|linkedin\.com/[^\s<>"\'\)]+|'
        r'github\.com/[^\s<>"\'\)]+|twitter\.com/[^\s<>"\'\)]+|x\.com/[^\s<>"\'\)]+|'
        r'[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}[^\s<>"\'\)]*)'
    )
    found_urls = [
        u for u in re.findall(url_pattern, raw_resume_text, re.IGNORECASE)
        if not _is_false_address_url(u)
    ]

    if not person.get('linkedin'):
        linkedin_urls = [u for u in found_urls if 'linkedin' in u.lower() or 'linked.in' in u.lower()]
        if linkedin_urls:
            url = _normalize_url(linkedin_urls[0])
            if url:
                person['linkedin'] = url
                actions.append('extracted_linkedin_from_text')

    if not person.get('github'):
        github_urls = [u for u in found_urls if 'github' in u.lower()]
        if github_urls:
            url = _normalize_url(github_urls[0])
            if url:
                person['github'] = url
                actions.append('extracted_github_from_text')

    if not person.get('twitter'):
        twitter_urls = [u for u in found_urls if 'twitter' in u.lower() or 'x.com' in u.lower()]
        if twitter_urls:
            url = _normalize_url(twitter_urls[0])
            if url:
                person['twitter'] = url
                actions.append('extracted_twitter_from_text')

    if not person.get('portfolio') and not person.get('website'):
        excluded = [
            'linkedin', 'github', 'twitter', 'x.com', 'gmail', 'yahoo', 'outlook',
            'hotmail', 'email', 'mail', 'edu', 'ac.', '.gov',
        ]
        portfolio_urls = [
            u for u in found_urls
            if not any(x in u.lower() for x in excluded) and '.' in u and len(u) > 5
            and not _is_false_address_url(u)
        ]
        if portfolio_urls:
            url = _normalize_url(portfolio_urls[0])
            if url:
                person['portfolio'] = url
                actions.append('extracted_portfolio_from_text')

    if not isinstance(person.get('otherUrls'), list):
        person['otherUrls'] = []

    categorized = set()
    for key in ('linkedin', 'github', 'twitter', 'portfolio', 'website'):
        val = person.get(key)
        if val:
            categorized.add(str(val).lower())

    for url in found_urls:
        url_final = _normalize_url(url)
        if not url_final:
            continue
        if url_final.lower() not in categorized and url_final not in person['otherUrls']:
            person['otherUrls'].append(url_final)

    if not person.get('location') or not str(person.get('location', '')).strip():
        loc = extract_location_from_text(raw_resume_text)
        if loc:
            person['location'] = loc
            actions.append('extracted_location_from_text')


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


def _apply_resume_text_recovery(repaired: dict[str, Any], raw_resume_text: str | None, actions: list[str]) -> None:
    """Fill empty canonical fields from raw resume text (mirrors JD repair pattern)."""
    if not raw_resume_text:
        return

    from app.ai.parser.enrichment.resume_text_inference import (
        compute_total_experience_years,
        extract_date_range_from_line,
        infer_resume_fields_from_text,
    )

    inferred = infer_resume_fields_from_text(raw_resume_text)

    skills = repaired.get("skills")
    if not isinstance(skills, list) or len(skills) == 0:
        new_skills = inferred.get("skills") or []
        if new_skills:
            repaired["skills"] = new_skills
            actions.append("inferred_skills_from_text")

    if not _str(repaired.get("summary")):
        summary = _str(inferred.get("summary"))
        if summary:
            repaired["summary"] = summary
            actions.append("inferred_summary_from_text")

    person = repaired.get("person")
    if not isinstance(person, dict):
        person = {}
        repaired["person"] = person

    inferred_person = inferred.get("person") or {}
    if not _str(person.get("email")):
        email = _str(inferred_person.get("email"))
        if email:
            person["email"] = email
            actions.append("inferred_email_from_text")

    if not _str(person.get("phone")):
        phone = _str(inferred_person.get("phone"))
        if phone:
            person["phone"] = phone
            actions.append("inferred_phone_from_text")

    if not _str(person.get("name")):
        name = _str(inferred_person.get("name"))
        if name:
            from app.ai.parser.enrichment.resume_text_inference import is_plausible_person_name
            if is_plausible_person_name(name):
                person["name"] = name
                actions.append("inferred_name_from_text")
            else:
                actions.append("skipped_implausible_inferred_name")

    if not _str(person.get("location")):
        loc = _str(inferred_person.get("location"))
        if loc:
            person["location"] = loc
            actions.append("inferred_location_from_text")

    experience = repaired.get("experience")
    if not isinstance(experience, list) or len(experience) == 0:
        new_exp = inferred.get("experience") or []
        if new_exp:
            repaired["experience"] = new_exp
            actions.append("inferred_experience_from_text")
    elif isinstance(experience, list):
        # Backfill missing dates on LLM experience rows from description/title lines
        for exp in experience:
            if not isinstance(exp, dict):
                continue
            if _str(exp.get("from")) and _str(exp.get("to")):
                continue
            blob = " ".join(
                _str(exp.get(k)) for k in ("title", "company", "description", "from", "to")
            )
            from_d, to_d = extract_date_range_from_line(blob)
            if from_d and not _str(exp.get("from")):
                exp["from"] = from_d
            if to_d and not _str(exp.get("to")):
                exp["to"] = to_d

    education = repaired.get("education")
    if not isinstance(education, list) or len(education) == 0:
        new_edu = inferred.get("education") or []
        if new_edu:
            repaired["education"] = new_edu
            actions.append("inferred_education_from_text")
    elif isinstance(education, list):
        inferred_edu = inferred.get("education") or []
        for idx, edu in enumerate(education):
            if not isinstance(edu, dict):
                continue
            degree = _str(edu.get("degree"))
            institution = _str(edu.get("institution") or edu.get("school"))
            donor = inferred_edu[idx] if idx < len(inferred_edu) and isinstance(inferred_edu[idx], dict) else None
            if donor is None:
                for cand in inferred_edu:
                    if not isinstance(cand, dict):
                        continue
                    if not degree and _str(cand.get("degree")):
                        donor = cand
                        break
                    if not institution and _str(cand.get("institution")):
                        donor = cand
                        break
            if not donor:
                continue
            if not degree and _str(donor.get("degree")):
                edu["degree"] = _str(donor["degree"])
                actions.append("backfilled_education_degree")
            if not institution and _str(donor.get("institution")):
                edu["institution"] = _str(donor["institution"])
                actions.append("backfilled_education_institution")
            if not _str(edu.get("field")) and _str(donor.get("field")):
                edu["field"] = _str(donor["field"])
            if not _str(edu.get("gpa") or edu.get("cgpa")):
                donor_gpa = _str(donor.get("gpa") or donor.get("cgpa"))
                if donor_gpa:
                    edu["gpa"] = donor_gpa
                    edu["cgpa"] = donor_gpa
            if not _str(edu.get("from")) and _str(donor.get("from")):
                edu["from"] = _str(donor["from"])
            if not _str(edu.get("to") or edu.get("year")):
                if _str(donor.get("to")):
                    edu["to"] = _str(donor["to"])
                if _str(donor.get("year")):
                    edu["year"] = _str(donor["year"])

    experience = repaired.get("experience")
    if isinstance(experience, list) and experience:
        inferred_exp = inferred.get("experience") or []
        for idx, exp in enumerate(experience):
            if not isinstance(exp, dict):
                continue
            title = _str(exp.get("title") or exp.get("role"))
            company = _str(exp.get("company"))
            if title and company:
                continue
            donor = inferred_exp[idx] if idx < len(inferred_exp) and isinstance(inferred_exp[idx], dict) else None
            if not donor:
                continue
            if not title and _str(donor.get("title")):
                from app.ai.parser.enrichment.resume_text_inference import is_plausible_job_title
                donor_title = _str(donor.get("title"))
                if is_plausible_job_title(donor_title):
                    exp["title"] = donor_title
                    actions.append("backfilled_experience_title")
            if not company and _str(donor.get("company")):
                exp["company"] = _str(donor["company"])
                actions.append("backfilled_experience_company")
            if not _str(exp.get("from")) and _str(donor.get("from")):
                exp["from"] = _str(donor["from"])
            if not _str(exp.get("to")) and _str(donor.get("to")):
                exp["to"] = _str(donor["to"])

    certifications = repaired.get("certifications")
    if not isinstance(certifications, list) or len(certifications) == 0:
        new_certs = inferred.get("certifications") or []
        if new_certs:
            repaired["certifications"] = new_certs
            actions.append("inferred_certifications_from_text")

    if repaired.get("total_experience_years") in (None, "", 0):
        years = inferred.get("total_experience_years")
        if years is None:
            years = compute_total_experience_years(
                repaired.get("experience") if isinstance(repaired.get("experience"), list) else []
            )
        if years is not None:
            repaired["total_experience_years"] = years
            actions.append("inferred_total_experience_years")


def _repair_resume_structure(data: dict[str, Any], raw_resume_text: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """Normalize common LLM shape drift into milestone resume schema. Mutates data in place."""
    from app.ai.toon.alias_registry import (
        coalesce_root_field,
        coalesce_skill_sources,
        merge_top_level_person_fields,
    )

    actions: list[str] = []
    if not isinstance(data, dict):
        data = {}

    # Always materialize a minimal skeleton before coalescing / inference / logging.
    for key, default in (
        ("type", "resume"),
        ("person", {}),
        ("skills", []),
        ("experience", []),
        ("education", []),
        ("projects", []),
        ("certifications", []),
        ("languages", []),
        ("summary", ""),
    ):
        if key == "type":
            data["type"] = "resume"
            continue
        if key not in data or data.get(key) is None:
            data[key] = {} if key == "person" else ([] if key != "summary" else "")
            actions.append(f"ensured_skeleton_{key}")
        elif key == "person" and not isinstance(data.get("person"), dict):
            # Wrong-type person → empty dict; later merge/inference fill fields.
            data["person"] = {}
            actions.append("ensured_skeleton_person")
        # Leave non-list skills/experience/etc. for existing coercion paths.

    source = dict(data)

    person_raw, person_actions = coalesce_root_field(source, "person")
    if not isinstance(person_raw, dict):
        person_raw = {}
    person, top_actions = merge_top_level_person_fields(source, person_raw)
    if not isinstance(person, dict):
        person = {}
    # Ensure required person keys exist and coerce LLM ints/lists to strings
    for pk in ("name", "email", "phone", "location", "linkedin", "github", "portfolio", "website", "twitter"):
        if pk not in person or person.get(pk) is None:
            if pk in ("name", "email", "phone", "location"):
                person[pk] = ""
        else:
            person[pk] = _str(person.get(pk))
    actions.extend(person_actions)
    actions.extend(top_actions)

    links_raw, links_actions = coalesce_root_field(source, "links")
    actions.extend(links_actions)
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

    languages, lang_actions = coalesce_root_field(source, "languages")
    actions.extend(lang_actions)
    if languages is None:
        languages = []
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

    experience_raw, exp_actions = coalesce_root_field(source, "experience")
    actions.extend(exp_actions)

    education_raw, edu_actions = coalesce_root_field(source, "education")
    actions.extend(edu_actions)

    projects_raw, proj_actions = coalesce_root_field(source, "projects")
    actions.extend(proj_actions)

    certs_raw, cert_actions = coalesce_root_field(source, "certifications")
    actions.extend(cert_actions)

    summary_raw, sum_actions = coalesce_root_field(source, "summary")
    actions.extend(sum_actions)

    skills, skill_actions = coalesce_skill_sources(
        source,
        normalize_skills=_normalize_skills,
        dedupe_skills=_dedupe_skills_preserve_case,
    )
    actions.extend(skill_actions)

    experience_list = experience_raw if isinstance(experience_raw, list) else []
    education_list = education_raw if isinstance(education_raw, list) else []
    projects_list = projects_raw if isinstance(projects_raw, list) else []
    certs_list = certs_raw if isinstance(certs_raw, list) else []

    _coerce_record_strings(
        experience_list,
        ("title", "role", "company", "description", "from", "to", "location"),
    )
    _coerce_record_strings(
        education_list,
        ("degree", "institution", "school", "field", "year", "from", "to", "gpa", "cgpa"),
    )
    _coerce_record_strings(
        projects_list,
        ("name", "title", "description", "url", "from", "to"),
    )
    _coerce_record_strings(
        certs_list,
        ("name", "issuer", "validTill", "url", "year"),
    )

    repaired = {
        "type": "resume",
        "person": person,
        "skills": skills,
        "experience": experience_list,
        "education": education_list,
        "projects": projects_list,
        "certifications": certs_list,
        "languages": languages if isinstance(languages, list) else _ensure_array(languages),
        "summary": _str(summary_raw),
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
    _apply_resume_text_recovery(repaired, raw_resume_text, actions)

    # Re-coerce after inference/backfill may have reintroduced non-strings
    for pk in ("name", "email", "phone", "location", "linkedin", "github", "portfolio", "website", "twitter"):
        if isinstance(repaired.get("person"), dict) and pk in repaired["person"]:
            repaired["person"][pk] = _str(repaired["person"].get(pk))
    repaired["summary"] = _str(repaired.get("summary"))
    _coerce_record_strings(
        repaired.get("experience"),
        ("title", "role", "company", "description", "from", "to", "location"),
    )
    _coerce_record_strings(
        repaired.get("education"),
        ("degree", "institution", "school", "field", "year", "from", "to", "gpa", "cgpa"),
    )

    data.clear()
    data.update(repaired)
    return data, actions


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
            if isinstance(val, dict) and len(val) == 0:
                continue
            return val
        return None

    def _first_str(*keys: str) -> str:
        for key in keys:
            s = _str(source.get(key))
            if s:
                return s
        return ""

    resp_raw = _first_nonempty(
        "responsibilities", "duties", "key_responsibilities",
        "role_responsibilities", "responsibilities_list",
    )
    if resp_raw is not source.get("responsibilities") and resp_raw is not None:
        actions.append("coalesced_responsibilities_alias")

    min_years, max_years = _coerce_experience_years(source)
    if (
        (min_years is not None or max_years is not None)
        and (
            source.get("min_experience_years") in (None, "")
            or source.get("max_experience_years") in (None, "")
        )
        and any(
            source.get(k) not in (None, "")
            for k in (
                "experience_years",
                "years_of_experience",
                "experience",
                "experience_range",
                "exp",
                "experience_required",
            )
        )
    ):
        actions.append("coalesced_experience_years_alias")

    repaired = {
        "type": "job_description",
        "title": _first_str("title", "job_title", "position"),
        "company": _first_str("company", "employer", "organization", "organisation"),
        "location": _first_str("location", "job_location", "work_location", "city"),
        "employment_type": _first_str("employment_type", "employmentType"),
        "skills": _normalize_skills(source.get("skills")),
        "mandatory_skills": _normalize_skills(
            source.get("mandatory_skills") or source.get("required_skills")
        ),
        "preferred_skills": _normalize_skills(
            source.get("preferred_skills") or source.get("nice_to_have_skills")
        ),
        "responsibilities": _normalize_responsibility_items(resp_raw),
        "qualifications": _normalize_responsibility_items(
            _first_nonempty("qualifications", "requirements", "education_requirements")
        ),
        "benefits": _ensure_string_array(source.get("benefits")),
        "keywords": _ensure_string_array(source.get("keywords")),
        "description": _str(source.get("description")),
        "min_experience_years": min_years,
        "max_experience_years": max_years,
        "salary_range": _first_str(
            "salary_range", "salary", "compensation", "ctc", "pay_range", "pay"
        ),
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
            from app.ai.parser.enrichment.jd_text_inference import extract_responsibilities_from_text
            inferred = extract_responsibilities_from_text(desc)
            if inferred:
                repaired["responsibilities"] = _normalize_responsibility_items(inferred)
                actions.append("inferred_responsibilities_from_description")

    if not repaired["responsibilities"] and raw_jd_text:
        from app.ai.parser.enrichment.jd_text_inference import extract_responsibilities_from_text
        inferred = extract_responsibilities_from_text(raw_jd_text)
        if inferred:
            repaired["responsibilities"] = _normalize_responsibility_items(inferred)
            actions.append("inferred_responsibilities_from_raw_text")

    infer_source = _str(repaired.get("description") or raw_jd_text)
    if infer_source:
        from app.ai.parser.enrichment.jd_text_inference import (
            extract_experience_years,
            extract_qualifications_from_text,
            infer_jd_fields_from_text,
        )

        inferred_fields = infer_jd_fields_from_text(infer_source)

        if not repaired.get("title") and inferred_fields.get("title"):
            repaired["title"] = inferred_fields["title"]
            actions.append("inferred_title_from_text")
        if not repaired.get("company") and inferred_fields.get("company"):
            repaired["company"] = inferred_fields["company"]
            actions.append("inferred_company_from_text")
        if not repaired.get("location") and inferred_fields.get("location"):
            repaired["location"] = inferred_fields["location"]
            actions.append("inferred_location_from_raw_text")
        if not repaired.get("skills") and inferred_fields.get("skills"):
            repaired["skills"] = inferred_fields["skills"]
            repaired["mandatory_skills"] = (
                inferred_fields.get("mandatory_skills") or inferred_fields["skills"]
            )
            if inferred_fields.get("preferred_skills"):
                repaired["preferred_skills"] = inferred_fields["preferred_skills"]
            actions.append("inferred_skills_from_raw_text")
        if not repaired.get("salary_range") and inferred_fields.get("salary_range"):
            repaired["salary_range"] = inferred_fields["salary_range"]
            actions.append("inferred_salary_from_text")
        if not repaired.get("employment_type") and inferred_fields.get("employment_type"):
            repaired["employment_type"] = inferred_fields["employment_type"]
            actions.append("inferred_employment_type_from_text")

        if repaired.get("min_experience_years") in (None, "") or repaired.get("max_experience_years") in (None, ""):
            min_y = inferred_fields.get("min_experience_years")
            max_y = inferred_fields.get("max_experience_years")
            if min_y is None and max_y is None:
                min_y, max_y = extract_experience_years(infer_source)
            if repaired.get("min_experience_years") in (None, "") and min_y is not None:
                repaired["min_experience_years"] = min_y
                actions.append("inferred_min_experience_years")
            if repaired.get("max_experience_years") in (None, "") and max_y is not None:
                repaired["max_experience_years"] = max_y
                actions.append("inferred_max_experience_years")

        if not repaired.get("qualifications"):
            quals = inferred_fields.get("qualifications") or extract_qualifications_from_text(infer_source)
            if quals:
                repaired["qualifications"] = quals
                actions.append("inferred_qualifications_from_text")

        if not repaired.get("description") and inferred_fields.get("description"):
            repaired["description"] = inferred_fields["description"]
            actions.append("inferred_description_from_text")

    # Ensure responsibilities present only when JD has a responsibilities section
    from app.ai.parser.enrichment.jd_text_inference import (
        clean_jd_description,
        compose_jd_description,
        extract_overview_from_text,
        extract_responsibilities_from_text,
        extract_tech_keywords_from_text,
        has_responsibilities_section,
    )

    source_text = (raw_jd_text or repaired.get("description") or "").strip()
    jd_has_kr = has_responsibilities_section(source_text)
    # When raw JD is unavailable, trust non-empty LLM responsibilities; when raw JD
    # is present, only include KR if that section actually exists in the document.
    if not jd_has_kr and not (raw_jd_text or "").strip() and repaired.get("responsibilities"):
        jd_has_kr = True
        actions.append("assumed_responsibilities_without_raw_jd")

    if jd_has_kr:
        # Prefer sentences extracted from the JD section; rebuild our own bullets later
        inferred_resp = extract_responsibilities_from_text(source_text)
        if inferred_resp:
            repaired["responsibilities"] = _normalize_responsibility_items(inferred_resp)
            actions.append("extracted_responsibilities_from_jd_section")
        elif repaired.get("responsibilities"):
            repaired["responsibilities"] = _normalize_responsibility_items(
                repaired.get("responsibilities")
            )
    else:
        # No KR section → Description stays overview-only (array may remain for ATS/validation)
        if repaired.get("responsibilities"):
            repaired["responsibilities"] = _normalize_responsibility_items(
                repaired.get("responsibilities")
            )
            actions.append("responsibilities_excluded_from_description")

    # Compose Description = overview [+ Key Responsibilities only if JD has that section]
    overview = clean_jd_description(
        repaired.get("description") or "",
        title=repaired.get("title") or "",
    )
    if not overview and raw_jd_text:
        overview = extract_overview_from_text(raw_jd_text)
        if overview:
            actions.append("filled_description_from_overview")

    resp_for_desc = (repaired.get("responsibilities") or []) if jd_has_kr else []
    composed = compose_jd_description(
        overview,
        resp_for_desc,
        title=repaired.get("title") or "",
        include_responsibilities=jd_has_kr,
    )
    if composed:
        if composed != (repaired.get("description") or ""):
            actions.append(
                "composed_description_with_responsibilities"
                if jd_has_kr and resp_for_desc
                else "composed_description_overview_only"
            )
        repaired["description"] = composed
    elif resp_for_desc:
        repaired["description"] = compose_jd_description(
            "",
            resp_for_desc,
            title=repaired.get("title") or "",
            include_responsibilities=True,
        )
        actions.append("filled_description_from_responsibilities")
    else:
        # No overview / KR — Description = Required Skills only
        required = [
            _str(s)
            for s in (
                list(repaired.get("mandatory_skills") or [])
                or list(repaired.get("skills") or [])
            )
            if _str(s)
        ]
        if required:
            repaired["description"] = f"**Required Skills:**\n{', '.join(required)}"
            actions.append("filled_description_from_required_skills")

    # Flag for frontend autofill: only show KR block when JD had that section
    repaired["has_key_responsibilities"] = bool(jd_has_kr and resp_for_desc)

    # Keywords: skills first, then short tech terms found in the JD (never sentences)
    tech_from_text = extract_tech_keywords_from_text(
        raw_jd_text or repaired.get("description") or ""
    )
    repaired["keywords"] = _derive_jd_keywords(
        list(repaired.get("keywords") or []) + tech_from_text,
        repaired,
        raw_jd_text or repaired.get("description") or "",
    )
    if repaired["keywords"]:
        actions.append("derived_keywords_from_jd")

    repaired["type"] = "job_description"
    return repaired, actions


def _derive_jd_keywords(
    existing: Any,
    repaired: dict[str, Any],
    jd_text: str,
    *,
    max_keywords: int = 20,
) -> list[str]:
    """Build keywords strictly from JD content — never invent unrelated terms."""
    from app.ai.parser.enrichment.jd_text_inference import is_plausible_keyword

    stop = {
        "and", "or", "the", "a", "an", "to", "of", "in", "for", "with", "on", "at",
        "job", "role", "position", "team", "work", "working", "experience", "years",
        "year", "required", "preferred", "nice", "have", "must", "strong", "good",
        "knowledge", "ability", "skills", "skill", "etc", "including", "using",
        "jd", "engineer", "developer",  # bare titles alone are weak keywords
    }
    skill_list = [
        _str(s)
        for s in (
            list(repaired.get("mandatory_skills") or [])
            + list(repaired.get("preferred_skills") or [])
            + list(repaired.get("skills") or [])
        )
        if _str(s)
    ]
    skill_set = {s.lower() for s in skill_list}

    # Prefer skills first; only keep short keyword tokens from parser keywords
    candidates = skill_list + _ensure_string_array(existing)

    text_lower = (jd_text or "").lower()
    result: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        kw = _str(raw)
        if not is_plausible_keyword(kw):
            continue
        key = kw.lower()
        if key in stop or key in seen:
            continue
        # Only keep terms present in the JD text, or already extracted as JD skills
        if text_lower and key not in text_lower and key not in skill_set:
            continue
        seen.add(key)
        result.append(kw)
        if len(result) >= max_keywords:
            break
    return result


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
    """Coerce LLM TOON values to a stripped string (ints, lists, None-safe)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return str(value).strip()
    if isinstance(value, (int, float)):
        return str(value).strip()
    if isinstance(value, list):
        parts = [_str(item) for item in value]
        return ", ".join(p for p in parts if p)
    if isinstance(value, dict):
        for key in ("name", "title", "text", "value", "label", "raw", "email", "phone"):
            if key in value and value[key] is not None and str(value[key]).strip():
                return _str(value[key])
        # Location-style objects: {city, region/state, country, remote}
        city = _str(value.get("city"))
        region = _str(value.get("region") or value.get("state"))
        country = _str(value.get("country"))
        loc_parts = [p for p in (city, region, country) if p]
        if loc_parts:
            return ", ".join(loc_parts)
        if value.get("remote") is True:
            return "Remote"
        return ""
    return str(value).strip()


def _coerce_experience_years(source: dict[str, Any]) -> tuple[Any, Any]:
    """Pull min/max years from canonical fields or common LLM aliases."""
    from app.ai.parser.enrichment.jd_text_inference import extract_experience_years

    def _as_number(val: Any) -> Any:
        if val is None or val == "":
            return None
        if isinstance(val, bool):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val.strip())
            except ValueError:
                return None
        return None

    min_y = _as_number(source.get("min_experience_years"))
    max_y = _as_number(source.get("max_experience_years"))
    if min_y is not None and max_y is not None:
        return min_y, max_y

    for key in (
        "experience_years",
        "years_of_experience",
        "experience",
        "experience_range",
        "exp",
        "experience_required",
    ):
        val = source.get(key)
        if val is None or val == "":
            continue
        if isinstance(val, dict):
            mn = val.get("min") or val.get("from") or val.get("min_years") or val.get("minimum")
            mx = val.get("max") or val.get("to") or val.get("max_years") or val.get("maximum")
            if min_y is None:
                min_y = _as_number(mn)
            if max_y is None:
                max_y = _as_number(mx)
        elif isinstance(val, (int, float)):
            if min_y is None:
                min_y = float(val)
        elif isinstance(val, str):
            parsed_min, parsed_max = extract_experience_years(val)
            if min_y is None and parsed_min is not None:
                min_y = parsed_min
            if max_y is None and parsed_max is not None:
                max_y = parsed_max
        if min_y is not None or max_y is not None:
            break

    return min_y, max_y


def _coerce_record_strings(records: Any, keys: tuple[str, ...]) -> Any:
    """In-place coerce selected dict fields to strings via _str."""
    if not isinstance(records, list):
        return records
    for item in records:
        if not isinstance(item, dict):
            continue
        for key in keys:
            if key in item:
                item[key] = _str(item.get(key))
    return records


def _split_string_to_items(text: str) -> list[str]:
    """Split prose lists on pipes, newlines, or bullets — never on commas.

    Commas appear inside normal sentences ("Design, build, and ship APIs") and must
    not become separate bullet lines in JD responsibilities/qualifications.
    """
    raw = text.strip()
    if not raw:
        return []
    if '|' in raw:
        parts = [p.strip() for p in raw.split('|')]
    else:
        parts = [p.strip() for p in re.split(r'\n+', raw)]
    result: list[str] = []
    for part in parts:
        cleaned = re.sub(r'^[\s•·\-\*]+', '', part).strip()
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
        if cleaned:
            result.append(cleaned)
    return result


def _split_skill_tokens(text: str) -> list[str]:
    """Split skill lists on commas, pipes, or newlines (skills are short tokens)."""
    raw = text.strip()
    if not raw:
        return []
    if '|' in raw:
        parts = [p.strip() for p in raw.split('|')]
    elif '\n' in raw:
        parts = [p.strip() for p in re.split(r'\n+', raw)]
    else:
        parts = [p.strip() for p in re.split(r'[,;•·]+', raw)]
    result: list[str] = []
    for part in parts:
        cleaned = re.sub(r'^[\s•·\-\*]+', '', part).strip()
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
        if cleaned:
            result.append(cleaned)
    return result


def _rejoin_comma_split_prose_items(items: list[str]) -> list[str]:
    """Rejoin items wrongly split on in-sentence commas into one bullet.

    Example: ["Design", "build", "and maintain APIs"]
          -> ["Design, build, and maintain APIs"]

    Does not join adjacent complete duties like ["Build APIs", "Write tests"].
    """
    if not items or len(items) < 2:
        return items

    def _is_continuation(prev: str, nxt: str) -> bool:
        p = (prev or "").strip()
        n = (nxt or "").strip()
        if not p or not n:
            return False
        if p.endswith((".", "!", "?", ";", ":")):
            return False
        lower = n.lower()
        if lower.startswith(("and ", "or ", "but ", "with ", "including ", "plus ")):
            return True
        # Mid-list fragment after a comma ("build", "design", "evaluation")
        if n[0].islower():
            return True
        return False

    out: list[str] = []
    buf = items[0].strip()
    for raw in items[1:]:
        nxt = (raw or "").strip()
        if not nxt:
            continue
        if _is_continuation(buf, nxt) and (len(buf) + len(nxt) < 240):
            buf = f"{buf}, {nxt}"
        else:
            out.append(buf)
            buf = nxt
    if buf:
        out.append(buf)
    return out


def _flatten_string_array_items(value: Any) -> list[str]:
    """Flatten list/string blobs without case-insensitive dedupe (needed before rejoin)."""
    if value is None:
        return []
    if isinstance(value, str):
        return _split_string_to_items(value)
    if isinstance(value, dict):
        for key in ("text", "description", "value", "name", "title"):
            if key in value and value[key]:
                return _flatten_string_array_items(value[key])
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                stripped = item.strip()
                if not stripped:
                    continue
                if '|' in stripped or '\n' in stripped:
                    result.extend(_split_string_to_items(stripped))
                else:
                    cleaned = re.sub(r'^[\s•·\-\*]+', '', stripped).strip()
                    cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
                    if cleaned:
                        result.append(cleaned)
            elif isinstance(item, dict):
                result.extend(_flatten_string_array_items(item))
            elif item is not None:
                part = _str(item)
                if part:
                    result.append(part)
        return result
    part = _str(value)
    return [part] if part else []


def _dedupe_string_items(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _normalize_responsibility_items(value: Any) -> list[str]:
    """Normalize responsibilities: strip source bullets, rejoin comma fragments, dedupe."""
    from app.ai.parser.enrichment.jd_text_inference import _strip_list_marker

    flat = _flatten_string_array_items(value)
    flat = [_strip_list_marker(x) for x in flat]
    flat = [x for x in flat if x]
    rejoined = _rejoin_comma_split_prose_items(flat)
    return _dedupe_string_items([_strip_list_marker(x) for x in rejoined if _strip_list_marker(x)])


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
                # Keep comma-containing sentences intact; only expand pipe/newline blobs.
                stripped = item.strip()
                if not stripped:
                    continue
                if '|' in stripped or '\n' in stripped:
                    parts = _split_string_to_items(stripped)
                else:
                    cleaned = re.sub(r'^[\s•·\-\*]+', '', stripped).strip()
                    cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
                    parts = [cleaned] if cleaned else []
                for part in parts:
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
    if skills is None:
        return []
    raw_items: list = []
    if isinstance(skills, str):
        raw_items = _split_skill_tokens(skills)
    elif isinstance(skills, list):
        for item in skills:
            if isinstance(item, str):
                stripped = item.strip()
                if not stripped:
                    continue
                # Expand compact skill lists; leave long prose alone.
                if (',' in stripped or ';' in stripped or '|' in stripped) and '\n' not in stripped and len(stripped) <= 180:
                    raw_items.extend(_split_skill_tokens(stripped))
                elif '\n' in stripped or '|' in stripped:
                    raw_items.extend(_split_skill_tokens(stripped))
                else:
                    raw_items.append(stripped)
            else:
                raw_items.append(item)
    else:
        raw_items = _ensure_array(skills)

    normalized: list = []
    for item in raw_items:
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


def _normalize_certifications(certs: Any) -> list:
    items = _ensure_array(certs)
    normalized: list = []
    for item in items:
        if isinstance(item, str):
            if item.strip():
                normalized.append({"name": item.strip(), "issuer": "", "validTill": "", "url": ""})
        elif isinstance(item, dict):
            normalized.append({
                "name": _str(item.get("name") or item.get("title")),
                "issuer": _str(item.get("issuer") or item.get("organization")),
                "validTill": _str(item.get("validTill") or item.get("expiry") or item.get("valid_till")),
                "url": _str(item.get("url") or item.get("validationUrl") or item.get("validation_url")),
            })
        elif item is not None:
            normalized.append({"name": _str(item), "issuer": "", "validTill": "", "url": ""})
    return normalized


def _normalize_experience(experience: Any) -> list:
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_job_title

    items = _ensure_array(experience)
    normalized: list = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _str(item.get("title") or item.get("role") or item.get("position"))
        company = _str(item.get("company") or item.get("employer"))
        description = _str(item.get("description"))
        if title and not is_plausible_job_title(title):
            # Mis-mapped objective/summary prose → keep as description, clear role
            if not description:
                description = title
            title = ""
        if not title and not company:
            continue
        normalized.append({
            "title": title,
            "company": company,
            "from": _str(item.get("from") or item.get("start") or item.get("start_date")),
            "to": _str(item.get("to") or item.get("end") or item.get("end_date")),
            "years": item.get("years"),
            "description": description,
            "location": _str(item.get("location") or item.get("city")),
        })
    return normalized


def _normalize_education(education: Any) -> list:
    items = _ensure_array(education)
    normalized: list = []
    for item in items:
        if not isinstance(item, dict):
            continue
        year = _str(item.get("year") or item.get("to") or item.get("end") or item.get("end_date"))
        from_val = _str(item.get("from") or item.get("start") or item.get("start_date"))
        to_val = _str(item.get("to") or item.get("end") or item.get("end_date") or year)
        gpa = _str(item.get("gpa") or item.get("cgpa") or item.get("percentage") or item.get("score"))
        normalized.append({
            "degree": _str(item.get("degree") or item.get("qualification") or item.get("program")),
            "field": _str(item.get("field") or item.get("major")),
            "institution": _str(item.get("institution") or item.get("school") or item.get("university")),
            "year": year,
            "from": from_val,
            "to": to_val,
            "gpa": gpa,
            "cgpa": gpa,
        })
    return normalized


def _normalize_person(person: Any) -> dict[str, Any]:
    if not isinstance(person, dict):
        person = {}
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_person_name

    raw_name = _str(person.get("name"))
    name = raw_name if is_plausible_person_name(raw_name) else ""
    return {
        "name": name,
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


def canonicalize_resume_toon(toon: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Single canonicalization pass: coerce types, trim whitespace, ensure required keys. Mutates in place."""
    actions: list[str] = []
    if not isinstance(toon, dict):
        return toon, actions

    toon["type"] = "resume"
    toon["person"] = _normalize_person(toon.get("person"))
    toon["skills"] = _dedupe_skills_preserve_case(_normalize_skills(toon.get("skills")))
    toon["experience"] = _normalize_experience(toon.get("experience"))
    toon["education"] = _normalize_education(toon.get("education"))
    toon["projects"] = _ensure_array(toon.get("projects"))
    toon["certifications"] = _normalize_certifications(toon.get("certifications"))
    toon["languages"] = _ensure_array(toon.get("languages"))
    summary = _str(toon.get("summary"))
    toon["summary"] = summary or None
    if "total_experience_years" not in toon:
        toon["total_experience_years"] = None

    for key in ("person", "skills", "experience", "education"):
        if key not in toon:
            toon[key] = {} if key == "person" else []
            actions.append(f"ensured_{key}")

    return toon, actions


def normalize_proposal(structured: dict[str, Any], doc_type: Literal["resume", "jd"]) -> dict[str, Any]:
    """Map runtime structured JSON to legacy TOON shape expected by backend validation."""
    if doc_type == "resume":
        import copy
        toon = copy.deepcopy(structured) if isinstance(structured, dict) else {}
        canonicalize_resume_toon(toon)
        return toon

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
        "responsibilities": _normalize_responsibility_items(structured.get("responsibilities")),
        "qualifications": _normalize_responsibility_items(structured.get("qualifications")),
        "benefits": _ensure_string_array(structured.get("benefits")),
        "keywords": _ensure_string_array(structured.get("keywords")),
        "description": _str(structured.get("description")),
        "min_experience_years": structured.get("min_experience_years"),
        "max_experience_years": structured.get("max_experience_years"),
        "salary_range": _str(structured.get("salary_range") or structured.get("salary")),
        "confidence": structured.get("confidence"),
        "has_key_responsibilities": bool(structured.get("has_key_responsibilities")),
    }
