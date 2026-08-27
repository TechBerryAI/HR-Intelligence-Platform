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
# Degree abbreviations that look like hostnames because .IT / .IN / .COM are TLDs.
_DEGREE_AS_HOST_RE = re.compile(
    r'(?i)^(?:https?://)?(?:www\.)?'
    r'(?:bsc|msc|bcom|mcom|bca|mca|bba|mba|btech|mtech|be|me|ba|ma|phd)'
    r'\.[a-z]{2,6}/?$'
)
_DEGREE_CUE_RE = re.compile(
    r'(?i)\b(?:'
    r'(?:bachelor|master|doctor)(?:\'?s)?s?|'
    r'diploma|doctorate|phd|'
    r'b\.?\s*tech|m\.?\s*tech|b\.?\s*e\.?(?![a-z])|m\.?\s*e\.?(?![a-z])|'
    r'b\.?\s*sc|m\.?\s*sc|bsc|msc|'
    r'b\.?\s*com|m\.?\s*com|bcom|mcom|'
    r'b\.?\s*s\.?(?![a-z])|m\.?\s*s\.?(?![a-z])|'
    r'mba|mca|bca|bba|'
    r'ph\.?\s*d|'
    r'b\.?\s*pharm|d\.?\s*pharm|ll\.?\s*b|ll\.?\s*m|'
    r'hsc|ssc|cbse|icse|puc|'
    r'(?:10|12)(?:th)?|'
    r'higher\s+secondary|senior\s+secondary|pre[\s\-]?university|'
    r'high\s+school|secondary\s+school|'
    r'associate(?:\'?s)?'
    r')\b'
)
_EDU_DUTY_START_RE = re.compile(
    r'(?i)^(?:'
    r'helped|trained|taught|managed|executed|coordinated|collaborated|'
    r'developed|designed|created|built|led|implemented|optimized|'
    r'improved|worked|assisted|supported|handled|performed|conducted|'
    r'analyzed|delivered|configured|setup|responsible|identifying|'
    r'enabling|applied|resulting|drove|leading\s+to'
    r')\b'
)
_SCHOOL_CUE_RE = re.compile(
    r'(?i)\b(?:university|college|school|institute|academy|vidyalaya|'
    r'polytechnic|campus|faculty|iit|nit|iiit|bits|mit)\b'
)
_COMPANY_NOT_SCHOOL_RE = re.compile(
    r'(?i)\b(?:pvt\.?\s*ltd|private\s+limited|ltd|inc|llc|gmbh|corp|'
    r'technologies|technology|solutions|systems|foundation|consulting|'
    r'services|labs?|studio|ventures)\b'
)
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
    if _DEGREE_AS_HOST_RE.match(s):
        return False, 'url_is_degree'
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
    if _DEGREE_CUE_RE.search(s):
        return False, 'name_is_degree'
    words = s.split()
    if not (1 <= len(words) <= 5):
        return False, 'name_word_count'
    try:
        from app.ai.parser.enrichment.resume_text_inference import is_plausible_person_name

        if not is_plausible_person_name(s):
            return False, 'name_implausible'
    except Exception:
        pass
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
    if re.fullmatch(r'\d{1,3}(?:\.\d+)?\s*%', s) or re.fullmatch(
        r'(?i)(?:cgpa|gpa)\s*[:\-]?\s*[\d.]+', s
    ):
        return False, 'institution_is_score'
    if _EDU_DUTY_START_RE.match(s):
        return False, 'institution_is_duty'
    if s[:1].islower():
        return False, 'institution_is_prose'
    if _JOB_TITLE_CUE_RE.search(s) and not _SCHOOL_CUE_RE.search(s):
        return False, 'institution_is_job_title'
    if _COMPANY_NOT_SCHOOL_RE.search(s) and not _SCHOOL_CUE_RE.search(s):
        return False, 'institution_is_company'
    words = s.split()
    if len(words) > 12 and not _SCHOOL_CUE_RE.search(s):
        return False, 'institution_too_long'
    if s.endswith('.') and len(words) >= 4 and not _SCHOOL_CUE_RE.search(s):
        return False, 'institution_is_sentence'
    return True, 'ok'


def validate_degree(value: str) -> Tuple[bool, str]:
    s = (value or '').strip()
    if not s:
        return False, 'degree_empty'
    if _MONTH_ONLY_RE.match(s) or _MONTH_YEAR_RE.match(s):
        return False, 'degree_is_date'
    if _EDU_DUTY_START_RE.match(s):
        return False, 'degree_is_duty'
    if s[:1].islower():
        return False, 'degree_is_prose'
    if len(s) > 80 and not _DEGREE_CUE_RE.search(s):
        return False, 'degree_too_long'
    if _JOB_TITLE_CUE_RE.search(s) and not _DEGREE_CUE_RE.search(s):
        return False, 'degree_is_job_title'
    if not _DEGREE_CUE_RE.search(s):
        return False, 'degree_no_cue'
    return True, 'ok'


def is_grounded_education_row(degree: str, institution: str) -> bool:
    """True only when both sides look like education — used for every resume."""
    deg_ok, _ = validate_degree(degree) if (degree or '').strip() else (False, '')
    inst_ok, _ = validate_institution(institution) if (institution or '').strip() else (False, '')
    return bool(deg_ok and inst_ok)


_EDU_HEADING_TOKENS = frozenset(
    {'education', 'educational', 'qualification', 'qualifications', 'academics'}
)


def is_keepable_education_form_row(degree: str, institution: str) -> bool:
    """Apply-form rows: keep when one side is grounded and the other is empty."""
    deg = (degree or '').strip()
    inst = (institution or '').strip()
    if not deg and not inst:
        return False
    if deg.lower() in _EDU_HEADING_TOKENS or inst.lower() in _EDU_HEADING_TOKENS:
        return False
    deg_ok, _ = validate_degree(deg) if deg else (True, 'empty')
    inst_ok, _ = validate_institution(inst) if inst else (True, 'empty')
    if not deg_ok or not inst_ok:
        return False
    return bool((deg and deg_ok) or (inst and inst_ok))


_GEO_BARE_RE = re.compile(
    r'(?i)^(?:'
    r'india|usa|uk|uae|remote|hybrid|wfh|work\s+from\s+home|'
    r'mumbai|delhi|new\s+delhi|pune|thane|hyderabad|chennai|bangalore|bengaluru|'
    r'noida|gurugram|gurgaon|kolkata|ahmedabad|navi\s+mumbai|kalwa|nashik|'
    r'surat|vadodara|ambernath|dombivli|dombivili|sindhudurg|sewree|solapur|'
    r'mulund|kandivali|andheri|powai|kalyan|vasai|virar|panvel|aurangabad|kolhapur'
    r')$'
)
_GEO_CITY_REGION_RE = re.compile(
    r'(?i)^([A-Za-z][A-Za-z .]{1,40}),\s*'
    r'(?:India|Maharashtra|Karnataka|Tamil\s+Nadu|Telangana|Gujarat|KA|MH|TN|TS|UP|DL|USA|UK)$'
)
_INSTITUTION_AS_JOB_RE = re.compile(
    r'(?i)\b(?:university|college|institute|polytechnic|iit|nit|school)\b'
)
_JOB_TITLE_CUE_RE = re.compile(
    r'(?i)\b(?:intern(?:ship)?s?|engineer|developer|analyst|trainee|apprentice|'
    r'manager|officer|associate|consultant|lead|executive|specialist|'
    r'administrator|admin|architect|dba|designer|scientist|director|head|'
    r'programmer|coordinator|supervisor|trainer|instructor)\b'
)


def _is_geo_only_token(value: str) -> bool:
    s = (value or '').strip()
    if not s or len(s) > 60:
        return False
    if re.search(r'(?i)\b(?:labs?|ltd|pvt|inc|corp|technologies|solutions|systems)\b', s):
        return False
    if _GEO_BARE_RE.match(s):
        return True
    if _GEO_CITY_REGION_RE.match(s):
        return True
    return False


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
    if _is_geo_only_token(s):
        return False, 'company_is_geo'
    if _INSTITUTION_AS_JOB_RE.search(s) and not _JOB_TITLE_CUE_RE.search(s):
        return False, 'company_is_institution'
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
    if _is_geo_only_token(s) or re.match(
        r'(?i)^(trends|python|sql|java)$',
        s,
    ):
        return False, 'role_is_noise'
    # Noun-led KPI / duty fragments (e.g. "Trends, and Revenue KPIs…")
    if (
        (',' in s or re.search(r'(?i)\b(?:trends?|kpis?|revenue)\b', s))
        and not _JOB_TITLE_CUE_RE.search(s)
    ):
        return False, 'role_is_duty_fragment'
    if _INSTITUTION_AS_JOB_RE.search(s) and not _JOB_TITLE_CUE_RE.search(s):
        return False, 'role_is_institution'
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
    loc = (exp.location or '').strip()
    # Em/en/hyphen title — Company  (SDE Intern — Edviron / Role - Company)
    for dash in ('—', '–', '-'):
        if dash in role and not company:
            left, _, right = role.partition(dash)
            if left.strip() and right.strip() and len(left.split()) <= 8:
                role, company = left.strip(), right.strip()
                break
        if dash in company and not role:
            left, _, right = company.partition(dash)
            if left.strip() and right.strip() and len(left.split()) <= 8:
                role, company = left.strip(), right.strip()
                break
    # Role,Company (PDF often drops the space after the comma)
    if ',' in role and not company:
        left, _, right = role.partition(',')
        if (
            left.strip()
            and right.strip()
            and len(left.split()) <= 6
            and len(right.split()) <= 8
            and _JOB_TITLE_CUE_RE.search(left)
            and not _JOB_TITLE_CUE_RE.search(right)
        ):
            role, company = left.strip(), right.strip()

    # Drop assignment / Coursera / project narratives mistaken for jobs
    if _PROJECT_LIKE_EXP.search(f'{role} {company} {desc}'):
        return ExperienceEntry(company='', role='', start='', end='', is_current=False)
    # Drop duty-sentence fragments mistaken for role/company
    # VALIDATION_FIX_duty_verbs_align — keep in sync with parser _DUTY_VERB_START
    if re.match(
        r'(?i)^(?:managed|executed|coordinated|collaborated|utilized|maintained|'
        r'facilitated|developed|designed|created|built|led|drove|implemented|'
        r'optimized|improved|increased|worked|assisted|supported|handled|'
        r'performed|conducted|analyzed|monitored|delivered|owned|spearheaded|'
        r'identifying|enabling|engineered|gained|helped|wrote|responsible\s+for|'
        r'administer(?:ed|ing)?|completed|pursued|strengthened|scheduled|'
        r'diagnosing|configuring|installing|creating|executing|participating|'
        r'using|implementing|monitoring|maintaining|query|role:|result:|'
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
    # City stuffed into company → location
    if company and _is_geo_only_token(company) and not loc:
        loc, company = company, ''
    if role and _is_geo_only_token(role) and not loc and not company:
        loc, role = role, ''
    company_ok, _ = validate_company(company) if company else (False, '')
    role_ok, _ = validate_role(role) if role else (False, '')

    # Detect swap: role looks like org, company looks like title
    if company and role:
        company_looks_role = bool(_JOB_TITLE_CUE_RE.search(company))
        role_looks_company = bool(
            re.search(
                r'(?i)\b(?:inc|llc|ltd|corp|solutions|technologies|labs|systems|pvt)\b',
                role,
            )
        ) and not _JOB_TITLE_CUE_RE.search(role)
        if company_looks_role and role_looks_company:
            company, role = role, company
            company_ok, role_ok = True, True

    if company and role and company.lower() == role.lower():
        company = ''
        company_ok = False

    # Role is actually a company name (no title cue): "Infosenseglobal", "Acme Pvt Ltd"
    if role and not company and not _JOB_TITLE_CUE_RE.search(role):
        org_like = bool(
            re.search(
                r'(?i)\b(?:pvt|ltd|llc|inc|corp|limited|technologies|solutions|labs|systems)\b',
                role,
            )
        )
        single_token = len(role.split()) == 1 and role[:1].isupper()
        if org_like or single_token:
            company, role = role, ''
            company_ok, role_ok = validate_company(company)[0], False

    start_ok, _ = validate_month_year(exp.start)
    end_ok, _ = validate_month_year(exp.end)
    if loc and _is_geo_only_token(loc) is False and len(loc) > 80:
        loc = ''
    cleaned = ExperienceEntry(
        company=company if company_ok else '',
        role=role if role_ok else '',
        start=exp.start if start_ok else '',
        end=exp.end if end_ok else '',
        is_current=exp.is_current,
        description=desc,
        location=loc[:120],
    )
    # Prefer rows with a real role; keep dated company-only (Infosenseglobal has no Ltd suffix)
    if cleaned.role:
        return cleaned
    if cleaned.company and cleaned.start:
        return cleaned
    if cleaned.company and cleaned.location:
        return cleaned
    # Dated location stub (date-first | Remote) kept for merge/years
    if cleaned.start and cleaned.location and (cleaned.end or cleaned.is_current):
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


def _summary_ok(summary: str | None) -> bool:
    """Reject contact/phone/email blobs that must never become personal.summary."""
    try:
        from app.ai.parser.enrichment.resume_text_inference import is_valid_summary

        return is_valid_summary(summary)
    except Exception:
        s = (summary or '').strip()
        return bool(s) and '@' not in s and not re.search(r'\b\d{10}\b', s)


def sanitize_candidate_profile(
    profile: CandidateProfile,
    *,
    source_text: str = '',
) -> CandidateProfile:
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
    experience = [
        e
        for e in experience
        if e.role
        or (e.company and e.start)
        or (e.company and e.location)
        or (e.start and e.location)
    ]
    education = [sanitize_education_row(e) for e in profile.education]
    education = [e for e in education if e.degree or e.institution]

    companies = {e.company for e in experience if e.company}
    skills = sanitize_skills(profile.skills, companies=companies)

    # Recompute years after experience sanitization (VALIDATION_FIX_years_after_sanitize)
    from app.ai.parser.enrichment.resume_text_inference import (
        compute_total_experience_years,
        extract_total_experience_years_from_text,
        heal_location_candidate,
        is_plausible_location_value,
        merge_experience_years,
    )

    date_years = compute_total_experience_years(
        [
            {
                'from': e.start,
                'to': 'Present' if e.is_current else e.end,
                'description': e.description or '',
                'role': e.role or '',
                'company': e.company or '',
            }
            for e in experience
        ]
    )
    prose_years = (
        extract_total_experience_years_from_text(source_text)
        if source_text
        else None
    )
    years = merge_experience_years(date_years, prose_years)
    if years is None:
        years = profile.total_experience_years

    # Sanitize location on contact — heal pipe/phone bleed before reject
    loc = heal_location_candidate((profile.contact.location or '').strip())
    if loc and not is_plausible_location_value(loc):
        loc = ''
    pref = heal_location_candidate((profile.contact.preferred_location or '').strip())
    if pref and not is_plausible_location_value(pref):
        pref = ''
    if loc and not pref:
        pref = loc

    return CandidateProfile(
        schema_version=profile.schema_version,
        personal=profile.personal.model_copy(
            update={
                'full_name': raw_name if name_ok else '',
                'summary': (
                    profile.personal.summary.strip()
                    if _summary_ok(profile.personal.summary)
                    else ''
                ),
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
        total_experience_years=years,
        field_meta=dict(profile.field_meta or {}),
    )
