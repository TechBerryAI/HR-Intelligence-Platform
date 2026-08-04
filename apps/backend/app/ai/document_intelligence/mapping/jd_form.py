"""
Explicit JD → Job Create Form mappings.

Every form field has exactly ONE canonical source.
description is composed by a named transform (format_jd_description), not heuristics.
"""
from __future__ import annotations

from app.ai.document_intelligence.models.form_dtos import FieldTrace, JobCreateFormDTO
from app.ai.document_intelligence.models.job import JobProfile
from app.ai.document_intelligence.validation.engine import validate_nonempty

MAPPER_ID = 'document_intelligence.mapping.jd_form.v1'

JD_FORM_MAPPING_GRAPH: dict[str, str] = {
    'title': 'basic.title',
    'location': 'location.primary',
    'company': 'basic.company',
    'salary': 'compensation.salary_range',
    'experienceFrom': 'requirements.min_experience_years',
    'experienceTo': 'requirements.max_experience_years',
    'mandatorySkills': 'skills.mandatory',
    'preferredSkills': 'skills.preferred',
    'employmentType': 'basic.employment_type',
    'description': 'format_jd_description(basic,responsibilities,skills,requirements,benefits)',
    '_skills': 'skills.general',
    '_responsibilities': 'responsibilities.items',
    '_qualifications': 'requirements.qualifications',
    '_keywords': 'requirements.keywords',
}


def _trace(
    form_field: str,
    canonical_path: str,
    *,
    source: str,
    validator: str,
    confidence: float,
    reason: str,
) -> FieldTrace:
    return FieldTrace(
        form_field=form_field,
        canonical_path=canonical_path,
        mapper=MAPPER_ID,
        source=source,
        validator=validator,
        confidence=confidence,
        reason=reason,
    )


def format_jd_description(profile: JobProfile) -> str:
    """
    Description from whatever the JD has:
      overview → responsibilities → qualifications → required skills.
    Other details (title, location, salary, skills fields) fill their own form fields.
    """
    from app.ai.parser.enrichment.jd_text_inference import (
        build_description_from_available,
        has_responsibilities_section,
        strip_foreign_form_sections_from_description,
        strip_source_bullets_to_prose,
    )

    raw = (profile.basic.description or '').strip()
    narrative = strip_foreign_form_sections_from_description(
        raw,
        title=profile.basic.title or '',
    )
    if narrative and len(narrative) >= 15:
        return narrative

    responsibilities = [
        strip_source_bullets_to_prose(r)
        for r in profile.responsibilities.items
        if r and str(r).strip()
    ]
    responsibilities = [r for r in responsibilities if r]
    include_kr = bool(responsibilities) and (
        has_responsibilities_section(raw) or '• ' in raw or bool(responsibilities)
    )

    return build_description_from_available(
        overview='',
        responsibilities=responsibilities,
        mandatory_skills=list(profile.skills.mandatory or []),
        preferred_skills=list(profile.skills.preferred or profile.skills.general or []),
        qualifications=list(profile.requirements.qualifications or []),
        title=profile.basic.title or '',
        source_text=raw,
        include_responsibilities=include_kr,
    )


def map_job_to_form(
    profile: JobProfile,
    *,
    coverage: list[dict] | None = None,
    raw_text: str = '',
) -> JobCreateFormDTO:
    traces: list[FieldTrace] = []

    title_ok, title_reason = validate_nonempty(profile.basic.title, 'title')
    title = profile.basic.title if title_ok else ''
    traces.append(
        _trace(
            'title',
            'basic.title',
            source='semantic_ai',
            validator='validate_nonempty' if title_ok else 'none',
            confidence=0.95 if title_ok else 0.0,
            reason=title_reason if title_ok else 'empty',
        )
    )

    loc_ok, loc_reason = validate_nonempty(profile.location.primary, 'location')
    location = profile.location.primary if loc_ok else ''
    traces.append(
        _trace(
            'location',
            'location.primary',
            source='deterministic',
            validator='validate_nonempty' if loc_ok else 'none',
            confidence=0.9 if loc_ok else 0.0,
            reason=loc_reason if loc_ok else 'empty',
        )
    )

    company = profile.basic.company.strip()
    traces.append(
        _trace(
            'company',
            'basic.company',
            source='semantic_ai',
            validator='validate_nonempty' if company else 'none',
            confidence=0.85 if company else 0.0,
            reason='ok' if company else 'empty',
        )
    )

    salary = profile.compensation.salary_range.strip()
    traces.append(
        _trace(
            'salary',
            'compensation.salary_range',
            source='deterministic',
            validator='validate_nonempty' if salary else 'none',
            confidence=0.85 if salary else 0.0,
            reason='ok' if salary else 'empty',
        )
    )

    exp_from = (
        str(int(profile.requirements.min_experience_years))
        if profile.requirements.min_experience_years is not None
        else ''
    )
    # Preserve decimals if not integer
    if profile.requirements.min_experience_years is not None:
        y = profile.requirements.min_experience_years
        exp_from = str(int(y)) if float(y).is_integer() else str(y)
    traces.append(
        _trace(
            'experienceFrom',
            'requirements.min_experience_years',
            source='deterministic',
            validator='numeric' if exp_from else 'none',
            confidence=0.9 if exp_from else 0.0,
            reason='ok' if exp_from else 'empty',
        )
    )

    exp_to = ''
    if profile.requirements.max_experience_years is not None:
        y = profile.requirements.max_experience_years
        exp_to = str(int(y)) if float(y).is_integer() else str(y)
    traces.append(
        _trace(
            'experienceTo',
            'requirements.max_experience_years',
            source='deterministic',
            validator='numeric' if exp_to else 'none',
            confidence=0.9 if exp_to else 0.0,
            reason='ok' if exp_to else 'empty',
        )
    )

    mandatory = [s for s in profile.skills.mandatory if s.strip()]
    preferred = [s for s in profile.skills.preferred if s.strip()]
    general = [s for s in profile.skills.general if s.strip()]
    # mandatorySkills source is ONLY skills.mandatory (canonical already filled from skills if empty)
    traces.append(
        _trace(
            'mandatorySkills',
            'skills.mandatory',
            source='knowledge',
            validator='skill_list' if mandatory else 'none',
            confidence=0.9 if mandatory else 0.0,
            reason=f'{len(mandatory)} skills',
        )
    )
    traces.append(
        _trace(
            'preferredSkills',
            'skills.preferred',
            source='knowledge',
            validator='skill_list' if preferred else 'none',
            confidence=0.85 if preferred else 0.0,
            reason=f'{len(preferred)} skills',
        )
    )

    employment = profile.basic.employment_type.strip()
    traces.append(
        _trace(
            'employmentType',
            'basic.employment_type',
            source='deterministic',
            validator='validate_nonempty' if employment else 'none',
            confidence=0.85 if employment else 0.0,
            reason='ok' if employment else 'empty',
        )
    )

    description = format_jd_description(profile)
    traces.append(
        _trace(
            'description',
            JD_FORM_MAPPING_GRAPH['description'],
            source='derived',
            validator='format_jd_description',
            confidence=0.9 if description else 0.0,
            reason='composed' if description else 'empty',
        )
    )

    responsibilities = [r for r in profile.responsibilities.items if r.strip()]
    qualifications = [q for q in profile.requirements.qualifications if q.strip()]
    from app.ai.parser.enrichment.jd_text_inference import (
        extract_tech_keywords_from_text,
        is_plausible_keyword,
    )

    # Keywords: grounded profile keywords + mandatory/preferred + tech from source
    keywords = [
        k.strip()
        for k in profile.requirements.keywords
        if k and is_plausible_keyword(str(k).strip())
    ]
    if not keywords:
        keywords = [
            s for s in (mandatory + preferred + general)
            if s and is_plausible_keyword(s) and len(s.split()) <= 4
        ][:20]
    if raw_text:
        tech = extract_tech_keywords_from_text(raw_text, max_items=15)
        src_l = raw_text.lower()
        for tok in tech:
            if tok.lower() in src_l and tok not in keywords:
                keywords.append(tok)
    keywords = list(dict.fromkeys(keywords))[:25]

    # Merge coverage into field traces for UI visibility
    coverage_rows = list(coverage or [])
    cov_by_field = {c.get('field'): c for c in coverage_rows if isinstance(c, dict)}
    for form_field, cov_key in (
        ('title', 'title'),
        ('location', 'location'),
        ('experienceFrom', 'experience'),
        ('mandatorySkills', 'skills'),
        ('description', 'description'),
        ('salary', 'salary'),
        ('employmentType', 'employment_type'),
        ('company', 'company'),
    ):
        c = cov_by_field.get(cov_key)
        if not c:
            continue
        traces.append(
            _trace(
                form_field,
                f'coverage.{cov_key}',
                source='coverage_gate',
                validator=str(c.get('status') or ''),
                confidence=0.95 if c.get('status') in ('filled', 'recovered') else 0.4,
                reason=str(c.get('detail') or c.get('status') or ''),
            )
        )

    return JobCreateFormDTO(
        title=title,
        location=location,
        experienceFrom=exp_from,
        experienceTo=exp_to,
        description=description,
        keywords=', '.join(keywords),
        salary=salary,
        company=company,
        mandatorySkills=mandatory,
        preferredSkills=preferred,
        employmentType=employment,
        skillsList=general or mandatory,
        mandatorySkillsList=mandatory,
        preferredSkillsList=preferred,
        responsibilitiesList=responsibilities,
        qualificationsList=qualifications,
        keywordsList=keywords,
        trace=traces,
        coverage=coverage_rows,
    )
