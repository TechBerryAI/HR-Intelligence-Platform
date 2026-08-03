"""
Canonical boundary: TOON dict ↔ CandidateProfile / JobProfile.

Alias coalescing happens HERE exactly once. Form mappers never see aliases.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from app.ai.document_intelligence.models.candidate import (
    CandidateProfile,
    CertificateEntry,
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    LanguageEntry,
    LinkEntry,
    PersonalInfo,
    ProjectEntry,
    SkillEntry,
)
from app.ai.document_intelligence.models.job import (
    JobBasicInfo,
    JobBenefits,
    JobCompensation,
    JobLocation,
    JobProfile,
    JobRequirements,
    JobResponsibilities,
    JobSkills,
)


def _str(v: Any) -> str:
    if v is None:
        return ''
    return str(v).strip()


def _as_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _string_list(v: Any) -> list[str]:
    out: list[str] = []
    for item in _as_list(v):
        if item is None:
            continue
        if isinstance(item, dict):
            name = _str(item.get('name') or item.get('skill') or item.get('title'))
            if name:
                out.append(name)
            continue
        s = _str(item)
        if not s:
            continue
        if '|' in s:
            out.extend(p for p in (x.strip() for x in s.split('|')) if p)
        elif '\n' in s:
            out.extend(p for p in (x.strip() for x in s.split('\n')) if p)
        else:
            out.append(s)
    return out


_PRESENT_RE = re.compile(r'^(present|current|now)$', re.I)


def _is_present(v: Any) -> bool:
    if v is True:
        return True
    return bool(_PRESENT_RE.match(_str(v)))


def _normalize_month(value: Any, *, year_only_month: str = '06') -> str:
    """Normalize dates to YYYY-MM. Deterministic only — no AI."""
    if value is None or value == '':
        return ''
    if isinstance(value, dict):
        y = value.get('year') or value.get('start_year') or value.get('end_year')
        m = value.get('month') or value.get('start_month') or value.get('end_month')
        if y is None:
            return ''
        yy = _str(y)
        if not re.fullmatch(r'\d{4}', yy):
            return ''
        mm = year_only_month
        if m is not None and m != '':
            try:
                num = int(m)
                if 1 <= num <= 12:
                    mm = f'{num:02d}'
            except (TypeError, ValueError):
                months = 'jan feb mar apr may jun jul aug sep oct nov dec'.split()
                key = _str(m).lower()[:3]
                if key in months:
                    mm = f'{months.index(key) + 1:02d}'
        return f'{yy}-{mm}'

    s = _str(value)
    if not s or _is_present(s):
        return ''
    range_m = re.match(
        r'^((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}|'
        r'\d{1,2}[/\-]\d{4}|\d{4}[/\-]\d{1,2}|\d{4}-\d{2}|\d{4})\s*(?:[-–—]|to)\s*',
        s,
        re.I,
    )
    if range_m:
        s = range_m.group(1)
    if re.fullmatch(r'\d{4}-\d{2}', s):
        return s
    if re.fullmatch(r'\d{4}', s):
        return f'{s}-{year_only_month}'
    mmyyyy = re.fullmatch(r'(\d{1,2})[/\-](\d{4})', s)
    if mmyyyy:
        month = int(mmyyyy.group(1))
        if 1 <= month <= 12:
            return f'{mmyyyy.group(2)}-{month:02d}'
    yyyymm = re.fullmatch(r'(\d{4})[/\-](\d{1,2})', s)
    if yyyymm:
        month = int(yyyymm.group(2))
        if 1 <= month <= 12:
            return f'{yyyymm.group(1)}-{month:02d}'
    mon_year = re.fullmatch(
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(\d{4})',
        s,
        re.I,
    )
    if mon_year:
        months = 'jan feb mar apr may jun jul aug sep oct nov dec'.split()
        key = 'sep' if mon_year.group(1).lower().startswith('sept') else mon_year.group(1).lower()[:3]
        if key in months:
            return f'{mon_year.group(2)}-{months.index(key) + 1:02d}'
    return ''


def _ensure_https(url: str) -> str:
    u = _str(url)
    if not u:
        return ''
    if u.startswith('//'):
        return f'https:{u}'
    if not re.match(r'^https?://', u, re.I):
        return f'https://{u}'
    return u


def candidate_profile_from_toon(toon: dict[str, Any]) -> CandidateProfile:
    """Convert persisted/engine TOON into the single CandidateProfile."""
    if not isinstance(toon, dict):
        return CandidateProfile()

    person = toon.get('person') if isinstance(toon.get('person'), dict) else {}
    other_urls = _string_list(person.get('otherUrls') or person.get('urls') or person.get('links'))

    education: list[EducationEntry] = []
    for edu in _as_list(toon.get('education')):
        if not isinstance(edu, dict):
            continue
        raw_end = edu.get('end') or edu.get('end_date') or edu.get('to') or edu.get('endMonth') or edu.get('year')
        end_str = _str(raw_end)
        year_only = bool(re.fullmatch(r'\d{4}', end_str) and _str(edu.get('year')) == end_str)
        education.append(
            EducationEntry(
                degree=_str(edu.get('degree') or edu.get('qualification') or edu.get('program')),
                field=_str(edu.get('field') or edu.get('major')),
                institution=_str(edu.get('institution') or edu.get('school') or edu.get('university')),
                gpa=_str(edu.get('gpa') or edu.get('cgpa') or edu.get('percentage') or edu.get('score')),
                start=_normalize_month(
                    edu.get('start') or edu.get('start_date') or edu.get('from') or edu.get('startMonth')
                ),
                end=_normalize_month(raw_end, year_only_month='12' if year_only else '06'),
            )
        )

    experience: list[ExperienceEntry] = []
    for exp in _as_list(toon.get('experience') or toon.get('experiences') or toon.get('work')):
        if not isinstance(exp, dict):
            continue
        raw_end = exp.get('to') or exp.get('end') or exp.get('end_date') or exp.get('endMonth')
        is_current = (
            _is_present(raw_end)
            or exp.get('isCurrent') is True
            or exp.get('present') is True
            or _str(exp.get('present')).lower() == 'yes'
        )
        experience.append(
            ExperienceEntry(
                company=_str(exp.get('company') or exp.get('employer') or exp.get('organization')),
                role=_str(exp.get('title') or exp.get('role') or exp.get('position')),
                start=_normalize_month(
                    exp.get('from') or exp.get('start') or exp.get('start_date') or exp.get('startMonth')
                ),
                end='' if is_current else _normalize_month(raw_end),
                is_current=is_current,
                description=_str(exp.get('description') or exp.get('responsibilities')),
                location=_str(exp.get('location') or exp.get('city')),
            )
        )

    certificates: list[CertificateEntry] = []
    for cert in _as_list(toon.get('certifications')):
        if cert is None:
            continue
        if isinstance(cert, str):
            certificates.append(CertificateEntry(name=_str(cert)))
            continue
        if not isinstance(cert, dict):
            continue
        certificates.append(
            CertificateEntry(
                name=_str(cert.get('name') or cert.get('title')),
                issuer=_str(cert.get('issuer') or cert.get('organization')),
                valid_till=_str(cert.get('validTill') or cert.get('expiry')),
                validation_url=_str(cert.get('url') or cert.get('validationUrl')),
                status=_str(cert.get('status')),
            )
        )

    skills = [
        SkillEntry(name=s, canonical=s)
        for s in _string_list(toon.get('skills'))
    ]

    languages: list[LanguageEntry] = []
    for lang in _as_list(toon.get('languages')):
        if isinstance(lang, str) and _str(lang):
            languages.append(LanguageEntry(name=_str(lang)))
        elif isinstance(lang, dict):
            languages.append(
                LanguageEntry(
                    name=_str(lang.get('name') or lang.get('language')),
                    proficiency=_str(lang.get('proficiency') or lang.get('level')),
                )
            )

    projects: list[ProjectEntry] = []
    for proj in _as_list(toon.get('projects')):
        if not isinstance(proj, dict):
            continue
        projects.append(
            ProjectEntry(
                name=_str(proj.get('name') or proj.get('title')),
                description=_str(proj.get('description')),
                technologies=_string_list(proj.get('technologies') or proj.get('tech')),
                url=_ensure_https(_str(proj.get('url'))),
            )
        )

    links = [LinkEntry(label='link', url=_ensure_https(u)) for u in other_urls if u]

    years = toon.get('total_experience_years')
    if years is None:
        years = toon.get('years_of_experience')
    try:
        total_years: Optional[float] = float(years) if years is not None and years != '' else None
    except (TypeError, ValueError):
        total_years = None

    meta = toon.get('_field_provenance') if isinstance(toon.get('_field_provenance'), dict) else {}

    return CandidateProfile(
        personal=PersonalInfo(
            full_name=_str(person.get('name') or person.get('full_name') or person.get('fullName')),
            summary=_str(toon.get('summary')),
        ),
        contact=ContactInfo(
            email=_str(person.get('email') or person.get('email_address')),
            phone=_str(
                person.get('phone')
                or person.get('mobile')
                or person.get('phone_number')
                or person.get('contact')
            ),
            location=_str(
                person.get('location')
                or person.get('current_location')
                or person.get('city')
                or person.get('address')
            ),
            preferred_location=_str(person.get('preferred_location')),
            linkedin=_ensure_https(_str(person.get('linkedin'))),
            github=_ensure_https(_str(person.get('github'))),
            portfolio=_ensure_https(_str(person.get('portfolio') or person.get('website'))),
            other_links=other_urls,
        ),
        education=education,
        experience=experience,
        projects=projects,
        skills=skills,
        certificates=certificates,
        languages=languages,
        links=links,
        total_experience_years=total_years,
        field_meta=meta,
    )


def toon_from_candidate_profile(profile: CandidateProfile) -> dict[str, Any]:
    """Serialize CandidateProfile to TOON for ATS persistence."""
    return {
        'type': 'resume',
        'person': {
            'name': profile.personal.full_name,
            'email': profile.contact.email,
            'phone': profile.contact.phone,
            'location': profile.contact.location,
            'preferred_location': profile.contact.preferred_location,
            'linkedin': profile.contact.linkedin,
            'github': profile.contact.github,
            'portfolio': profile.contact.portfolio,
            'otherUrls': list(profile.contact.other_links),
        },
        'summary': profile.personal.summary,
        'skills': [s.canonical or s.name for s in profile.skills],
        'experience': [
            {
                'title': e.role,
                'company': e.company,
                'from': e.start,
                'to': 'Present' if e.is_current else e.end,
                'description': e.description,
                'location': e.location,
            }
            for e in profile.experience
        ],
        'education': [
            {
                'degree': e.degree,
                'field': e.field,
                'institution': e.institution,
                'gpa': e.gpa,
                'from': e.start,
                'to': e.end,
            }
            for e in profile.education
        ],
        'certifications': [
            {
                'name': c.name,
                'issuer': c.issuer,
                'validTill': c.valid_till,
                'url': c.validation_url,
                'status': c.status,
            }
            for c in profile.certificates
        ],
        'languages': [
            {'name': lang.name, 'proficiency': lang.proficiency} for lang in profile.languages
        ],
        'projects': [
            {
                'name': p.name,
                'description': p.description,
                'technologies': p.technologies,
                'url': p.url,
            }
            for p in profile.projects
        ],
        'total_experience_years': profile.total_experience_years,
    }


def job_profile_from_toon(toon: dict[str, Any]) -> JobProfile:
    if not isinstance(toon, dict):
        return JobProfile()

    mandatory = _string_list(toon.get('mandatory_skills'))
    preferred = _string_list(toon.get('preferred_skills'))
    general = _string_list(toon.get('skills'))
    if not mandatory and general:
        mandatory = list(general)

    def _opt_float(v: Any) -> Optional[float]:
        if v is None or v == '':
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    meta = toon.get('_field_provenance') if isinstance(toon.get('_field_provenance'), dict) else {}

    return JobProfile(
        basic=JobBasicInfo(
            title=_str(toon.get('title')),
            company=_str(toon.get('company')),
            employment_type=_str(toon.get('employment_type') or toon.get('employmentType')),
            description=_str(toon.get('description')),
        ),
        requirements=JobRequirements(
            min_experience_years=_opt_float(toon.get('min_experience_years')),
            max_experience_years=_opt_float(toon.get('max_experience_years')),
            qualifications=_string_list(toon.get('qualifications')),
            keywords=_string_list(toon.get('keywords')),
        ),
        responsibilities=JobResponsibilities(items=_string_list(toon.get('responsibilities'))),
        skills=JobSkills(mandatory=mandatory, preferred=preferred, general=general),
        benefits=JobBenefits(items=_string_list(toon.get('benefits'))),
        location=JobLocation(primary=_str(toon.get('location'))),
        compensation=JobCompensation(salary_range=_str(toon.get('salary_range'))),
        field_meta=meta,
    )


def toon_from_job_profile(profile: JobProfile) -> dict[str, Any]:
    return {
        'type': 'job_description',
        'title': profile.basic.title,
        'company': profile.basic.company,
        'location': profile.location.primary,
        'employment_type': profile.basic.employment_type,
        'description': profile.basic.description,
        'min_experience_years': profile.requirements.min_experience_years,
        'max_experience_years': profile.requirements.max_experience_years,
        'skills': list(profile.skills.general or profile.skills.mandatory),
        'mandatory_skills': list(profile.skills.mandatory),
        'preferred_skills': list(profile.skills.preferred),
        'responsibilities': list(profile.responsibilities.items),
        'qualifications': list(profile.requirements.qualifications),
        'keywords': list(profile.requirements.keywords),
        'benefits': list(profile.benefits.items),
        'salary_range': profile.compensation.salary_range,
    }
