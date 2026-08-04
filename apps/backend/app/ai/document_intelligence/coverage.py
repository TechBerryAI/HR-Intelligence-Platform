"""
JD coverage gate: compare filled JobProfile fields against source-text evidence.

Statuses:
  filled                 — profile already has a value
  recovered              — gap filled from grounded source extractors (no invention)
  missing_with_evidence  — source appears to contain the field but recovery failed
  missing_no_evidence    — neither profile nor source evidence
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.ai.document_intelligence.models.job import JobProfile
from app.ai.parser.enrichment.jd_text_inference import (
    extract_company_from_text,
    extract_employment_type_from_text,
    extract_experience_years,
    extract_kv_fields_from_text,
    extract_location_from_text,
    extract_overview_from_text,
    extract_responsibilities_from_text,
    extract_salary_from_text,
    extract_skills_from_text,
    extract_tech_keywords_from_text,
    extract_title_from_text,
    infer_jd_fields_from_text,
    is_plausible_job_title,
    normalize_skill_tokens,
    skills_look_skill_like,
)

COVERAGE_FIELDS = (
    'title',
    'location',
    'experience',
    'skills',
    'description',
    'salary',
    'employment_type',
    'company',
)


@dataclass
class CoverageEntry:
    field: str
    status: str
    detail: str = ''

    def as_dict(self) -> dict[str, str]:
        return {
            'field': self.field,
            'status': self.status,
            'detail': self.detail,
        }


@dataclass
class JdCoverageReport:
    entries: list[CoverageEntry] = field(default_factory=list)

    def as_dicts(self) -> list[dict[str, str]]:
        return [e.as_dict() for e in self.entries]

    @property
    def recovered_fields(self) -> list[str]:
        return [e.field for e in self.entries if e.status == 'recovered']

    @property
    def missing_with_evidence(self) -> list[str]:
        return [e.field for e in self.entries if e.status == 'missing_with_evidence']

    def by_field(self) -> dict[str, CoverageEntry]:
        return {e.field: e for e in self.entries}


def _has_text(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return any(str(v).strip() for v in value)
    return bool(str(value).strip())


def _skills_filled(profile: JobProfile) -> bool:
    skills = (
        list(profile.skills.mandatory or [])
        + list(profile.skills.preferred or [])
        + list(profile.skills.general or [])
    )
    return skills_look_skill_like(skills)


def _experience_filled(profile: JobProfile) -> bool:
    return (
        profile.requirements.min_experience_years is not None
        or profile.requirements.max_experience_years is not None
    )


def _description_filled(profile: JobProfile) -> bool:
    if (profile.basic.description or '').strip():
        return True
    return bool(profile.responsibilities.items)


def _source_has_title(text: str) -> bool:
    title = extract_title_from_text(text)
    if title and is_plausible_job_title(title):
        return True
    kv = extract_kv_fields_from_text(text)
    return bool(kv.get('title') and is_plausible_job_title(kv['title']))


def _source_has_location(text: str) -> bool:
    if extract_location_from_text(text):
        return True
    kv = extract_kv_fields_from_text(text)
    return bool((kv.get('location') or '').strip())


def _source_has_experience(text: str) -> bool:
    min_y, max_y = extract_experience_years(text)
    if min_y is not None or max_y is not None:
        return True
    kv = extract_kv_fields_from_text(text)
    if kv.get('experience'):
        a, b = extract_experience_years(kv['experience'])
        return a is not None or b is not None
    return False


def _source_has_skills(text: str) -> bool:
    mandatory, preferred, general = extract_skills_from_text(text)
    if skills_look_skill_like(mandatory or preferred or general):
        return True
    return bool(extract_tech_keywords_from_text(text, max_items=5))


def _source_has_description(text: str) -> bool:
    if extract_overview_from_text(text, max_chars=400):
        return True
    return bool(extract_responsibilities_from_text(text, max_items=3))


def _source_has_salary(text: str) -> bool:
    if extract_salary_from_text(text):
        return True
    return bool((extract_kv_fields_from_text(text).get('salary') or '').strip())


def _source_has_employment(text: str) -> bool:
    return bool(extract_employment_type_from_text(text))


def _source_has_company(text: str) -> bool:
    return bool(extract_company_from_text(text))


def _recover_title(profile: JobProfile, text: str) -> Optional[str]:
    title = extract_title_from_text(text)
    if title and is_plausible_job_title(title):
        return title[:120]
    kv = extract_kv_fields_from_text(text)
    cand = (kv.get('title') or '').strip()
    if cand and is_plausible_job_title(cand):
        return cand[:120]
    return None


def _recover_location(profile: JobProfile, text: str) -> Optional[str]:
    loc = extract_location_from_text(text)
    if loc:
        return loc[:120]
    kv = extract_kv_fields_from_text(text)
    raw = (kv.get('location') or '').strip()
    if raw:
        cleaned = extract_location_from_text(f'Location: {raw}') or raw
        return cleaned[:120]
    return None


def _recover_experience(
    profile: JobProfile, text: str
) -> tuple[Optional[float], Optional[float]]:
    min_y, max_y = extract_experience_years(text)
    if min_y is not None or max_y is not None:
        return min_y, max_y
    kv = extract_kv_fields_from_text(text)
    if kv.get('experience'):
        return extract_experience_years(kv['experience'])
    return None, None


def _recover_skills(profile: JobProfile, text: str) -> tuple[list[str], list[str], list[str]]:
    mandatory, preferred, general = extract_skills_from_text(text)
    mandatory = normalize_skill_tokens(mandatory, max_items=40)
    preferred = normalize_skill_tokens(preferred, max_items=30)
    general = normalize_skill_tokens(general, max_items=40)
    if len(mandatory) < 3 and not general:
        tech = extract_tech_keywords_from_text(text, max_items=20)
        seen = {s.lower() for s in mandatory}
        for tok in tech:
            if tok.lower() not in seen:
                mandatory.append(tok)
                seen.add(tok.lower())
            if len(mandatory) >= 15:
                break
    return mandatory, preferred, general or mandatory


def _recover_description(profile: JobProfile, text: str) -> tuple[str, list[str]]:
    overview = extract_overview_from_text(text) or ''
    resp = extract_responsibilities_from_text(text)
    return overview[:4000], resp


def recover_jd_profile_gaps(
    profile: JobProfile,
    raw_text: str,
) -> tuple[JobProfile, JdCoverageReport]:
    """Fill empty JobProfile fields from grounded JD text extractors; emit coverage."""
    text = (raw_text or '').strip()
    inferred = infer_jd_fields_from_text(text) if text else {}
    report = JdCoverageReport()

    # --- title ---
    if profile.basic.title and is_plausible_job_title(profile.basic.title):
        report.entries.append(CoverageEntry('title', 'filled', 'profile'))
    else:
        recovered = _recover_title(profile, text) or (
            inferred.get('title') if is_plausible_job_title(str(inferred.get('title') or '')) else None
        )
        if recovered:
            profile.basic.title = recovered
            report.entries.append(CoverageEntry('title', 'recovered', 'source_text'))
        elif _source_has_title(text):
            report.entries.append(CoverageEntry('title', 'missing_with_evidence', 'extractor_failed'))
        else:
            report.entries.append(CoverageEntry('title', 'missing_no_evidence', 'empty'))

    # --- location ---
    if (profile.location.primary or '').strip():
        report.entries.append(CoverageEntry('location', 'filled', 'profile'))
    else:
        recovered = _recover_location(profile, text) or (inferred.get('location') or '').strip() or None
        if recovered:
            profile.location.primary = recovered
            report.entries.append(CoverageEntry('location', 'recovered', 'source_text'))
        elif _source_has_location(text):
            report.entries.append(CoverageEntry('location', 'missing_with_evidence', 'extractor_failed'))
        else:
            report.entries.append(CoverageEntry('location', 'missing_no_evidence', 'empty'))

    # --- experience ---
    if _experience_filled(profile):
        report.entries.append(CoverageEntry('experience', 'filled', 'profile'))
    else:
        min_y, max_y = _recover_experience(profile, text)
        if min_y is None and max_y is None:
            min_y = inferred.get('min_experience_years')
            max_y = inferred.get('max_experience_years')
        if min_y is not None or max_y is not None:
            profile.requirements.min_experience_years = min_y
            profile.requirements.max_experience_years = max_y
            report.entries.append(CoverageEntry('experience', 'recovered', 'source_text'))
        elif _source_has_experience(text):
            report.entries.append(CoverageEntry('experience', 'missing_with_evidence', 'extractor_failed'))
        else:
            report.entries.append(CoverageEntry('experience', 'missing_no_evidence', 'empty'))

    # --- skills ---
    if _skills_filled(profile):
        report.entries.append(CoverageEntry('skills', 'filled', 'profile'))
    else:
        mandatory, preferred, general = _recover_skills(profile, text)
        if skills_look_skill_like(mandatory or preferred or general):
            if mandatory:
                profile.skills.mandatory = mandatory
            if preferred:
                profile.skills.preferred = preferred
            if general:
                profile.skills.general = general
            report.entries.append(CoverageEntry('skills', 'recovered', 'source_text'))
        elif _source_has_skills(text):
            report.entries.append(CoverageEntry('skills', 'missing_with_evidence', 'extractor_failed'))
        else:
            report.entries.append(CoverageEntry('skills', 'missing_no_evidence', 'empty'))

    # --- description / responsibilities ---
    if _description_filled(profile):
        report.entries.append(CoverageEntry('description', 'filled', 'profile'))
    else:
        overview, resp = _recover_description(profile, text)
        if not overview and inferred.get('description'):
            overview = str(inferred['description'])
        if not resp and inferred.get('responsibilities'):
            resp = list(inferred['responsibilities'] or [])
        if overview or resp:
            if overview:
                profile.basic.description = overview
            if resp and not profile.responsibilities.items:
                profile.responsibilities.items = resp
            report.entries.append(CoverageEntry('description', 'recovered', 'source_text'))
        elif _source_has_description(text):
            report.entries.append(CoverageEntry('description', 'missing_with_evidence', 'extractor_failed'))
        else:
            report.entries.append(CoverageEntry('description', 'missing_no_evidence', 'empty'))

    # --- salary ---
    if (profile.compensation.salary_range or '').strip():
        report.entries.append(CoverageEntry('salary', 'filled', 'profile'))
    else:
        recovered = extract_salary_from_text(text) or (inferred.get('salary_range') or '').strip() or None
        if recovered:
            profile.compensation.salary_range = recovered[:120]
            report.entries.append(CoverageEntry('salary', 'recovered', 'source_text'))
        elif _source_has_salary(text):
            report.entries.append(CoverageEntry('salary', 'missing_with_evidence', 'extractor_failed'))
        else:
            report.entries.append(CoverageEntry('salary', 'missing_no_evidence', 'empty'))

    # --- employment_type ---
    if (profile.basic.employment_type or '').strip():
        report.entries.append(CoverageEntry('employment_type', 'filled', 'profile'))
    else:
        recovered = (
            extract_employment_type_from_text(text)
            or (inferred.get('employment_type') or '').strip()
            or None
        )
        if recovered:
            profile.basic.employment_type = recovered[:80]
            report.entries.append(CoverageEntry('employment_type', 'recovered', 'source_text'))
        elif _source_has_employment(text):
            report.entries.append(
                CoverageEntry('employment_type', 'missing_with_evidence', 'extractor_failed')
            )
        else:
            report.entries.append(CoverageEntry('employment_type', 'missing_no_evidence', 'empty'))

    # --- company ---
    if (profile.basic.company or '').strip():
        report.entries.append(CoverageEntry('company', 'filled', 'profile'))
    else:
        recovered = extract_company_from_text(text) or (inferred.get('company') or '').strip() or None
        if recovered:
            profile.basic.company = recovered[:120]
            report.entries.append(CoverageEntry('company', 'recovered', 'source_text'))
        elif _source_has_company(text):
            report.entries.append(CoverageEntry('company', 'missing_with_evidence', 'extractor_failed'))
        else:
            report.entries.append(CoverageEntry('company', 'missing_no_evidence', 'empty'))

    return profile, report
