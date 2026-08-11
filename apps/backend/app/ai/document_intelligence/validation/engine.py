"""
Validation Engine — deterministic validators + anti-contamination rules.

Invalid values must never silently populate the UI.
"""
from __future__ import annotations

import re
from typing import Tuple

from app.ai.document_intelligence.models.candidate import (
    CandidateProfile,
    EducationEntry,
    ExperienceEntry,
    SkillEntry,
)

_EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')
_PHONE_RE = re.compile(r'^\+?[\d\s\-().]{7,20}$')
_URL_RE = re.compile(r'^(https?://)?([A-Za-z0-9\-]+\.)+[A-Za-z]{2,}(/.*)?$', re.I)
_MONTH_YEAR_RE = re.compile(
    r'^(?:'
    r'(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}(?:[/\-](?:0?[1-9]|1[0-2]))?'
    r'|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)\d{2}'
    r'|Present|Current|Now'
    r')$',
    re.I,
)
_MONTH_ONLY_RE = re.compile(
    r'^(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|'
    r'0?[1-9]|1[0-2])$',
    re.I,
)
_SECTION_HEADERS = frozenset({
    'resume', 'curriculum vitae', 'cv', 'profile', 'summary', 'objective',
    'experience', 'education', 'skills', 'projects', 'certifications',
    'professional summary', 'work experience', 'contact',
})
_PROJECT_LIKE_EXP = re.compile(
    r'(?i)\b(?:assignment|coursera|internship\s+project|academic\s+project|'
    r'fictional\s+brand)\b'
)
_SENTENCE_SKILL = re.compile(
    r'(?i)\b(?:developed|built|improved|responsible|worked|managed|led|created|'
    r'implemented|designed|collaborated|delivered)\b'
)


def validate_nonempty(value: str, label: str = 'field') -> Tuple[bool, str]:
    if value is None or not str(value).strip():
        return False, f'{label}_empty'
    return True, 'ok'


def validate_email(value: str) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s:
        return False, 'email_empty'
    if not _EMAIL_RE.match(s):
        return False, 'email_invalid'
    return True, 'ok'


def validate_phone(value: str) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s:
        return False, 'phone_empty'
    digits = re.sub(r'\D', '', s)
    if len(digits) < 7 or len(digits) > 15:
        return False, 'phone_digit_count'
    # Reject concatenated calendar years (e.g. 202620182020202)
    years = re.findall(r'(?:19|20)\d{2}', digits)
    if len(years) >= 2 and ''.join(years) in digits:
        return False, 'phone_year_soup'
    if len(digits) >= 12 and re.fullmatch(r'(?:(?:19|20)\d{2}){3,}', digits):
        return False, 'phone_year_soup'
    if not _PHONE_RE.match(s):
        return False, 'phone_invalid'
    return True, 'ok'


def validate_location(value: str) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s:
        return False, 'location_empty'
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_location_value

    if not is_plausible_location_value(s):
        return False, 'location_implausible'
    return True, 'ok'


def validate_url(
    value: str,
    *,
    allow_empty: bool = False,
    host_hint: str | None = None,
) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s:
        return (True, 'empty_allowed') if allow_empty else (False, 'url_empty')
    lower = s.lower()
    for bad in ('example.com', 'localhost', 'placeholder', 'loading.', 'test.com'):
        if bad in lower and 'linkedin.com' not in lower and 'github.com' not in lower:
            # allow gold lake example.com emails are separate; URLs with example.com rejected
            if 'linkedin' not in (host_hint or '') and 'github' not in (host_hint or ''):
                return False, 'url_placeholder'
    if not _URL_RE.match(s) and not _URL_RE.match(f'https://{s}'):
        return False, 'url_invalid'
    if host_hint and host_hint.lower() not in lower:
        return False, f'url_host_mismatch_{host_hint}'
    return True, 'ok'


def validate_person_name(value: str) -> Tuple[bool, str]:
    s = (value or '').strip()
    s = re.sub(r'[\u200b\u200c\u200d\u2060\ufeff\u00ad]', '', s).replace('\xa0', ' ').strip()
    if not s:
        return False, 'name_empty'
    low = s.lower()
    if low in _SECTION_HEADERS or low.endswith(' resume') or low.endswith(' cv'):
        return False, 'name_is_title'
    if '@' in s or 'http' in low:
        return False, 'name_not_person'
    if re.search(r'\d', s):
        return False, 'name_has_digits'
    words = s.split()
    if not (1 <= len(words) <= 5):
        return False, 'name_word_count'
    return True, 'ok'


def validate_month_year(value: str, *, allow_empty: bool = True) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s:
        return (True, 'empty_allowed') if allow_empty else (False, 'date_empty')
    if _MONTH_YEAR_RE.match(s) or re.match(r'^(?:19|20)\d{2}$', s):
        return True, 'ok'
    return False, 'date_invalid'


def validate_institution(value: str) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s:
        return False, 'institution_empty'
    if _MONTH_ONLY_RE.match(s):
        return False, 'institution_is_month'
    if _MONTH_YEAR_RE.match(s):
        return False, 'institution_is_date'
    if len(s) < 3:
        return False, 'institution_too_short'
    return True, 'ok'


def validate_degree(value: str) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s:
        return False, 'degree_empty'
    if _MONTH_ONLY_RE.match(s) or _MONTH_YEAR_RE.match(s):
        return False, 'degree_is_date'
    return True, 'ok'


def validate_company(value: str) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s:
        return False, 'company_empty'
    if _MONTH_ONLY_RE.match(s) or _MONTH_YEAR_RE.match(s):
        return False, 'company_is_date'
    low = s.lower()
    if low in _SECTION_HEADERS or low in (
        'board/university', 'board / university', 'school/college',
        'year of passing', 'percentage/ cgpa', 'percentage/cgpa',
    ):
        return False, 'company_is_header'
    if re.search(r'(?i)year of passing|board/university|school/college', s):
        return False, 'company_is_edu_table'
    if re.match(
        r'(?i)^(india|usa|uk|remote|hybrid|mumbai|pune|thane|delhi|hyderabad|'
        r'chennai|bangalore|bengaluru|noida)$',
        s,
    ):
        return False, 'company_is_geo'
    if len(s) > 120:
        return False, 'company_too_long'
    return True, 'ok'


def validate_role(value: str) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s:
        return False, 'role_empty'
    if _MONTH_ONLY_RE.match(s) or _MONTH_YEAR_RE.match(s):
        return False, 'role_is_date'
    if len(s) > 120:
        return False, 'role_too_long'
    low = s.lower()
    if low in _SECTION_HEADERS:
        return False, 'role_is_header'
    if re.search(
        r'(?i)degree/certificate|year of passing|board/university|school/college|'
        r'percentage/?\s*cgpa',
        s,
    ):
        return False, 'role_is_edu_table'
    if re.match(
        r'(?i)^(india|usa|uk|remote|hybrid|mumbai|pune|thane|delhi|hyderabad|'
        r'chennai|bangalore|bengaluru|noida|trends|python|sql|java)$',
        s,
    ):
        return False, 'role_is_noise'
    # Education lines mistaken for jobs
    if re.search(
        r'(?i)\b(?:b\.?\s?tech|b\.?\s?e\b|bca|mca|mba|bsc|msc|bachelor|master|diploma|hsc|ssc)\b',
        s,
    ) and not re.search(r'(?i)\bintern|engineer|developer|analyst|trainee\b', s):
        return False, 'role_is_degree'
    return True, 'ok'


def validate_skill_item(value: str) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s or len(s) < 2:
        return False, 'skill_empty'
    if len(s) > 80:
        return False, 'skill_too_long'
    if _SENTENCE_SKILL.search(s) and len(s.split()) >= 4:
        return False, 'skill_is_experience_text'
    if _MONTH_YEAR_RE.match(s) or _MONTH_ONLY_RE.match(s):
        return False, 'skill_is_date'
    low = s.lower()
    if low in _SECTION_HEADERS:
        return False, 'skill_is_header'
    return True, 'ok'


def sanitize_experience_row(exp: ExperienceEntry) -> ExperienceEntry:
    """Reject company/role swaps, date contamination, edu-table and project-like rows."""
    company = exp.company.strip()
    role = exp.role.strip()
    desc = (exp.description or '').strip()
    # Em-dash title — Company  (SDE Intern — Edviron)
    if '—' in role and not company:
        left, _, right = role.partition('—')
        if left.strip() and right.strip():
            role, company = left.strip(), right.strip()
    if '—' in company and not role:
        left, _, right = company.partition('—')
        if left.strip() and right.strip():
            role, company = left.strip(), right.strip()

    # Drop assignment / Coursera / project narratives mistaken for jobs
    if _PROJECT_LIKE_EXP.search(f'{role} {company} {desc}'):
        return ExperienceEntry(company='', role='', start='', end='', is_current=False)
    # Drop duty-sentence fragments mistaken for role/company
    if re.match(
        r'(?i)^(managed|executed|coordinated|collaborated|utilized|maintained|'
        r'facilitated|developed|designed|created|built|led|drove|implemented|'
        r'optimized|improved|increased|worked|assisted|supported|handled|'
        r'performed|conducted|analyzed|monitored|delivered|owned|spearheaded|'
        r'identifying|enabling|engineered|gained|'
        r'[•·\*●])',
        role,
    ) or re.match(
        r'(?i)^(resulting|ensuring|improving|including|across|reports?|captions|'
        r'brand voice|traffic|and efficiency|identifying|integrating)\b',
        company,
    ):
        return ExperienceEntry(company='', role='', start='', end='', is_current=False)
    if company and len(company.split()) >= 10:
        company = ''
    company_ok, _ = validate_company(company) if company else (False, '')
    role_ok, _ = validate_role(role) if role else (False, '')

    # Detect swap: role looks like org, company looks like title
    if company and role:
        company_looks_role = bool(
            re.search(
                r'(?i)\b(?:engineer|developer|manager|analyst|consultant|lead|intern|officer|'
                r'trainee|associate)\b',
                company,
            )
        )
        role_looks_company = bool(
            re.search(
                r'(?i)\b(?:inc|llc|ltd|corp|solutions|technologies|labs|systems|pvt)\b',
                role,
            )
        ) and not re.search(
            r'(?i)\b(?:engineer|developer|manager|analyst|intern)\b',
            role,
        )
        if company_looks_role and role_looks_company:
            company, role = role, company
            company_ok, role_ok = True, True

    if company and role and company.lower() == role.lower():
        company = ''
        company_ok = False

    # Role is actually a company name (no title on line)
    if role and not company and re.search(
        r'(?i)\b(?:pvt|ltd|llc|inc|corp|limited|technologies|solutions|labs|systems)\b',
        role,
    ) and not re.search(r'(?i)\b(?:engineer|developer|manager|analyst|intern|trainee)\b', role):
        company, role = role, ''
        company_ok, role_ok = validate_company(company)[0], False

    start_ok, _ = validate_month_year(exp.start)
    end_ok, _ = validate_month_year(exp.end)
    cleaned = ExperienceEntry(
        company=company if company_ok else '',
        role=role if role_ok else '',
        start=exp.start if start_ok else '',
        end=exp.end if end_ok else '',
        is_current=exp.is_current,
        description=desc,
        location=exp.location.strip(),
    )
    # Prefer rows with a real role; company-only only when dated + org-like
    if cleaned.role:
        return cleaned
    if cleaned.company and cleaned.start and re.search(
        r'(?i)\b(?:pvt|ltd|llc|inc|corp|limited|technologies|solutions|labs|systems)\b',
        cleaned.company,
    ):
        return cleaned
    return ExperienceEntry(company='', role='', start='', end='', is_current=False)


def sanitize_education_row(edu: EducationEntry) -> EducationEntry:
    inst_ok, _ = validate_institution(edu.institution) if edu.institution else (False, '')
    deg_ok, _ = validate_degree(edu.degree) if edu.degree else (False, '')
    start_ok, _ = validate_month_year(edu.start)
    end_ok, _ = validate_month_year(edu.end)
    degree = edu.degree if deg_ok else ''
    institution = edu.institution if inst_ok else ''
    # Drop education table header pollution
    if re.search(
        r'(?i)degree/certificate|year of passing|board/university|school/college|'
        r'percentage/?\s*cgpa',
        f'{degree} {institution}',
    ):
        return EducationEntry()
    return EducationEntry(
        degree=degree,
        field=edu.field.strip(),
        institution=institution,
        gpa=edu.gpa.strip(),
        start=edu.start if start_ok else '',
        end=edu.end if end_ok else '',
    )


def sanitize_skills(skills: list[SkillEntry], *, companies: set[str] | None = None) -> list[SkillEntry]:
    companies = {c.lower() for c in (companies or set()) if c}
    out: list[SkillEntry] = []
    seen: set[str] = set()
    for sk in skills:
        name = (sk.canonical or sk.name or '').strip()
        ok, _ = validate_skill_item(name)
        if not ok:
            continue
        if name.lower() in companies:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(SkillEntry(name=name, canonical=name, category=sk.category))
    return out


def sanitize_candidate_profile(profile: CandidateProfile) -> CandidateProfile:
    """Apply anti-contamination rules; blank invalid fields rather than guess."""
    raw_name = re.sub(
        r'[\u200b\u200c\u200d\u2060\ufeff\u00ad]',
        '',
        (profile.personal.full_name or ''),
    ).replace('\xa0', ' ').strip()
    name_ok, _ = validate_person_name(raw_name)
    email_ok, _ = validate_email(profile.contact.email) if profile.contact.email else (False, '')
    phone_ok, _ = validate_phone(profile.contact.phone) if profile.contact.phone else (False, '')

    li = profile.contact.linkedin
    li_ok, _ = validate_url(li, allow_empty=True, host_hint='linkedin') if li else (True, '')
    gh = profile.contact.github
    gh_ok, _ = validate_url(gh, allow_empty=True, host_hint='github') if gh else (True, '')
    port = profile.contact.portfolio
    port_ok, _ = validate_url(port, allow_empty=True) if port else (True, '')

    experience = [sanitize_experience_row(e) for e in profile.experience]
    experience = [e for e in experience if e.role or (e.company and e.start)]
    education = [sanitize_education_row(e) for e in profile.education]
    education = [e for e in education if e.degree or e.institution]

    companies = {e.company for e in experience if e.company}
    skills = sanitize_skills(profile.skills, companies=companies)

    # Recompute years after experience sanitization (VALIDATION_FIX_years_after_sanitize)
    from app.ai.parser.enrichment.resume_text_inference import compute_total_experience_years

    years = compute_total_experience_years(
        [
            {
                'from': e.start,
                'to': 'Present' if e.is_current else e.end,
            }
            for e in experience
        ]
    )

    # Sanitize location on contact
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_location_value

    loc = (profile.contact.location or '').strip()
    if loc:
        loc = loc.splitlines()[0].strip()
        # Prefer city token from "Company | City" or phone⋄City bleed
        if '|' in loc:
            parts = [p.strip() for p in loc.split('|') if p.strip()]
            city_part = next(
                (
                    p
                    for p in reversed(parts)
                    if is_plausible_location_value(p)
                ),
                '',
            )
            loc = city_part or ''
        loc = re.sub(r'(?i)^\+?\d[\d\s\-().]{6,}\s*[⋄·•|]*\s*', '', loc).strip()
        if not is_plausible_location_value(loc):
            loc = ''
    pref = (profile.contact.preferred_location or '').strip()
    if pref and not is_plausible_location_value(pref.splitlines()[0].strip()):
        pref = ''
    if loc and not pref:
        pref = loc

    return CandidateProfile(
        schema_version=profile.schema_version,
        personal=profile.personal.model_copy(
            update={
                'full_name': raw_name if name_ok else '',
                'summary': profile.personal.summary.strip(),
            }
        ),
        contact=profile.contact.model_copy(
            update={
                'email': profile.contact.email if email_ok else '',
                'phone': profile.contact.phone if phone_ok else '',
                'linkedin': li if li_ok else '',
                'github': gh if gh_ok else '',
                'portfolio': port if port_ok else '',
                'location': loc,
                'preferred_location': pref,
            }
        ),
        education=education,
        experience=experience,
        projects=profile.projects,
        skills=skills,
        certificates=profile.certificates,
        languages=profile.languages,
        links=profile.links,
        preferences=profile.preferences,
        total_experience_years=years if years is not None else profile.total_experience_years,
        field_meta=dict(profile.field_meta or {}),
    )
