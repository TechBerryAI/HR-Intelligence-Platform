"""JD completeness coverage — recover fields that exist in source but were missed."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.ai.document_intelligence.models.job import JobProfile

CoverageStatus = Literal[
    'filled',
    'recovered',
    'missing_no_evidence',
    'missing_with_evidence',
]

CORE_FIELDS = (
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
class FieldCoverage:
    field: str
    status: CoverageStatus
    evidence: bool = False
    detail: str = ''


@dataclass
class CoverageReport:
    fields: list[FieldCoverage] = field(default_factory=list)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                'field': f.field,
                'status': f.status,
                'evidence': f.evidence,
                'detail': f.detail,
            }
            for f in self.fields
        ]

    @property
    def missing_with_evidence(self) -> list[str]:
        return [f.field for f in self.fields if f.status == 'missing_with_evidence']

    @property
    def recovered_fields(self) -> list[str]:
        return [f.field for f in self.fields if f.status == 'recovered']


def _has_location_evidence(text: str) -> bool:
    return bool(
        re.search(
            r'(?i)\b(?:location|work\s*location|job\s*location|based\s+in|office)\s*[:\-–—]|'
            r'\b(?:mumbai|pune|bengaluru|bangalore|chennai|hyderabad|delhi|noida|remote|hybrid)\b',
            text or '',
        )
    )


def _has_experience_evidence(text: str) -> bool:
    return bool(
        re.search(
            r'(?i)(?:experience|work\s*experience|exp\.?)\s*[:\-–—]|'
            r'\b\d+(?:\.\d+)?\s*(?:\+|to|[-–—])\s*\d*(?:\.\d+)?\s*(?:years?|yrs?)\b|'
            r'\bfresher\b',
            text or '',
        )
    )


def _has_skills_evidence(text: str) -> bool:
    from app.ai.parser.enrichment.jd_text_inference import extract_tech_keywords_from_text

    if re.search(
        r'(?i)(?:required|primary|technical|key|mandatory|preferred)?\s*skills?\s*[:\-–—]|'
        r'tech\s*stack|primary\s*skills?',
        text or '',
    ):
        return True
    return len(extract_tech_keywords_from_text(text or '', max_items=5)) >= 2


def _has_salary_evidence(text: str) -> bool:
    return bool(
        re.search(
            r'(?i)(?:salary|ctc|compensation|pay)\s*[:\-–—]\s*\S|'
            r'\b\d+(?:\.\d+)?\s*[-–—]\s*\d+(?:\.\d+)?\s*(?:lpa|lakhs?)\b|'
            r'(?:₹|rs\.?|inr)\s*[\d,]+',
            text or '',
        )
    )


def _has_employment_evidence(text: str) -> bool:
    return bool(
        re.search(
            r'(?i)(?:employment\s*type|job\s*type)\s*[:\-–—]|'
            r'\b(?:full[- ]?time|part[- ]?time|contract|internship)\b',
            text or '',
        )
    )


def _has_company_evidence(text: str) -> bool:
    return bool(
        re.search(r'(?i)(?:company|employer|organization|organisation)\s*[:\-–—]', text or '')
    )


def _has_description_evidence(text: str) -> bool:
    if not text or len(text.strip()) < 80:
        return False
    return bool(
        re.search(
            r'(?i)(?:responsibilities|duties|about\s+the\s+role|job\s+summary|overview|'
            r'we\s+are\s+seeking|looking\s+for)',
            text,
        )
    ) or len(text.strip()) >= 200


def detect_jd_evidence(text: str) -> dict[str, bool]:
    return {
        'title': bool((text or '').strip()),
        'location': _has_location_evidence(text),
        'experience': _has_experience_evidence(text),
        'skills': _has_skills_evidence(text),
        'description': _has_description_evidence(text),
        'salary': _has_salary_evidence(text),
        'employment_type': _has_employment_evidence(text),
        'company': _has_company_evidence(text),
    }


def _profile_filled(profile: JobProfile) -> dict[str, bool]:
    try:
        from app.ai.parser.enrichment.jd_text_inference import (
            is_plausible_jd_location,
            skills_look_skill_like,
        )
    except ImportError:
        # Stale process may predate is_plausible_jd_location — keep coverage usable
        from app.ai.parser.enrichment.jd_text_inference import skills_look_skill_like

        def is_plausible_jd_location(loc: str) -> bool:
            s = (loc or '').strip()
            return bool(s) and '\n' not in s and '\r' not in s and 2 <= len(s) <= 80

    skills = list(profile.skills.mandatory or []) + list(profile.skills.general or [])
    desc = (profile.basic.description or '').strip()
    has_resp = bool(profile.responsibilities.items)
    salary = (profile.compensation.salary_range or '').strip()
    # Currency-only noise is not a filled salary
    salary_ok = bool(salary) and bool(re.search(r'\d', salary) or re.search(r'(?i)lpa|lakh|negotiable', salary))
    loc = (profile.location.primary or '').strip()
    return {
        'title': bool((profile.basic.title or '').strip()),
        # Garbage locations (newline bleed / duty noise) count as unfilled so recovery can replace them
        'location': bool(loc) and is_plausible_jd_location(loc),
        'experience': profile.requirements.min_experience_years is not None
        or profile.requirements.max_experience_years is not None,
        'skills': skills_look_skill_like(skills),
        'description': len(desc) >= 40 or has_resp,
        'salary': salary_ok,
        'employment_type': bool((profile.basic.employment_type or '').strip()),
        'company': bool((profile.basic.company or '').strip()),
    }


def recover_jd_profile_gaps(profile: JobProfile, raw_text: str) -> tuple[JobProfile, CoverageReport]:
    """
    Fill empty profile fields when source text has clear evidence.
    Never invents values that are not grounded in raw_text.
    """
    from app.ai.parser.enrichment.jd_text_inference import (
        build_description_from_available,
        extract_company_from_text,
        extract_employment_type_from_text,
        extract_experience_years,
        extract_kv_fields_from_text,
        extract_location_from_text,
        extract_overview_from_text,
        extract_qualifications_from_text,
        extract_responsibilities_from_text,
        extract_salary_from_text,
        extract_skills_from_text,
        extract_tech_keywords_from_text,
        extract_title_from_text,
        is_plausible_job_title,
        normalize_skill_tokens,
        skills_look_skill_like,
    )

    try:
        from app.ai.parser.enrichment.jd_text_inference import is_plausible_jd_location
    except ImportError:

        def is_plausible_jd_location(loc: str) -> bool:
            s = (loc or '').strip()
            return bool(s) and '\n' not in s and '\r' not in s and 2 <= len(s) <= 80

    evidence = detect_jd_evidence(raw_text)
    filled = _profile_filled(profile)
    report = CoverageReport()
    kv = extract_kv_fields_from_text(raw_text)

    data = profile.model_dump()
    recovered: set[str] = set()

    # Title
    if not filled['title']:
        title = (kv.get('title') or extract_title_from_text(raw_text) or '').strip()
        if is_plausible_job_title(title):
            data['basic']['title'] = title[:120]
            recovered.add('title')
            filled['title'] = True

    # Location — replace empty or implausible captures; never accept duty/newline noise
    if not filled['location'] and evidence['location']:
        loc = (kv.get('location') or extract_location_from_text(raw_text) or '').strip()
        grounded = bool(
            loc
            and (
                loc.lower() in raw_text.lower()
                or loc.split(',')[0].lower().strip() in raw_text.lower()
            )
        )
        if loc and grounded and is_plausible_jd_location(loc):
            data['location']['primary'] = loc[:120]
            recovered.add('location')
            filled['location'] = True
        elif data.get('location', {}).get('primary'):
            # Clear garbage so status stays missing_with_evidence rather than filled
            data['location']['primary'] = ''

    # Experience
    if not filled['experience'] and evidence['experience']:
        src = kv.get('experience') or raw_text
        min_y, max_y = extract_experience_years(src)
        if min_y is not None or max_y is not None:
            data['requirements']['min_experience_years'] = min_y
            data['requirements']['max_experience_years'] = max_y
            recovered.add('experience')
            filled['experience'] = True

    # Skills (also replace garbage / non-skill-like tokens)
    if (not filled['skills'] and evidence['skills']) or (
        evidence['skills'] and not skills_look_skill_like(
            list(data.get('skills', {}).get('mandatory') or [])
            + list(data.get('skills', {}).get('general') or [])
        )
    ):
        mand, pref, gen = extract_skills_from_text(raw_text)
        skills = normalize_skill_tokens(mand or gen or [], max_items=30, from_skill_section=True)
        if len(skills) < 3:
            tech = extract_tech_keywords_from_text(raw_text, max_items=20)
            seen = {s.lower() for s in skills}
            for t in tech:
                if t.lower() not in seen:
                    skills.append(t)
                    seen.add(t.lower())
        # Ground: token must appear in source (case-insensitive) or be acronym in source
        grounded = []
        src_l = raw_text.lower()
        for s in skills:
            if s.lower() in src_l or any(tok.lower() in src_l for tok in s.split() if len(tok) >= 3):
                grounded.append(s)
        if grounded and skills_look_skill_like(grounded):
            data['skills']['mandatory'] = grounded
            data['skills']['general'] = list(grounded)
            if pref:
                data['skills']['preferred'] = normalize_skill_tokens(
                    pref, max_items=15, from_skill_section=True
                )
            recovered.add('skills')
            filled['skills'] = True

    # Company / salary / employment
    if not filled['company'] and evidence['company']:
        company = (kv.get('company') or extract_company_from_text(raw_text) or '').strip()
        if company and company.lower() in raw_text.lower():
            data['basic']['company'] = company[:120]
            recovered.add('company')
            filled['company'] = True

    if not filled['salary'] and evidence['salary']:
        salary = (kv.get('salary') or extract_salary_from_text(raw_text) or '').strip()
        if salary and (re.search(r'\d', salary) or re.search(r'(?i)lpa|lakh|negotiable', salary)):
            data['compensation']['salary_range'] = salary[:120]
            recovered.add('salary')
            filled['salary'] = True
    elif filled['salary']:
        # Clear currency-only noise left from earlier passes
        cur = (data.get('compensation', {}) or {}).get('salary_range') or ''
        if cur and not (re.search(r'\d', cur) or re.search(r'(?i)lpa|lakh|negotiable', cur)):
            data['compensation']['salary_range'] = ''
            filled['salary'] = False
            if evidence['salary']:
                salary = extract_salary_from_text(raw_text) or ''
                if salary and (re.search(r'\d', salary) or re.search(r'(?i)lpa|lakh|negotiable', salary)):
                    data['compensation']['salary_range'] = salary[:120]
                    recovered.add('salary')
                    filled['salary'] = True

    if not filled['employment_type'] and evidence['employment_type']:
        emp = (kv.get('employment_type') or extract_employment_type_from_text(raw_text) or '').strip()
        if emp:
            data['basic']['employment_type'] = emp[:60]
            recovered.add('employment_type')
            filled['employment_type'] = True

    # Description / responsibilities — also scrub heading-only pollution
    resp_items = list(data.get('responsibilities', {}).get('items') or [])
    if resp_items:
        scrubbed = [
            r for r in resp_items
            if r and not re.match(
                r'(?i)^(?:education|qualifications?|requirements?|key\s+responsibilities|'
                r'responsibilities)\s*:?\s*$',
                str(r).strip(),
            )
        ]
        if len(scrubbed) != len(resp_items):
            data['responsibilities']['items'] = scrubbed
            resp_items = scrubbed

    if not filled['description'] and evidence['description']:
        overview = extract_overview_from_text(raw_text) or ''
        resp = list(data.get('responsibilities', {}).get('items') or [])
        if not resp:
            resp = extract_responsibilities_from_text(raw_text)
        quals = list(data.get('requirements', {}).get('qualifications') or [])
        if not quals:
            quals = extract_qualifications_from_text(raw_text)
        composed = build_description_from_available(
            overview=overview,
            responsibilities=resp,
            mandatory_skills=list(data.get('skills', {}).get('mandatory') or []),
            preferred_skills=list(data.get('skills', {}).get('preferred') or []),
            qualifications=quals,
            title=data.get('basic', {}).get('title') or '',
            source_text=raw_text,
            include_responsibilities=bool(resp),
        )
        if composed and len(composed.strip()) >= 40:
            data['basic']['description'] = composed[:4000]
            if resp:
                data['responsibilities']['items'] = resp[:30]
            if quals:
                data['requirements']['qualifications'] = quals[:20]
            recovered.add('description')
            filled['description'] = True

    # Keywords from overall JD (tech/domain) — not a mandatory-skills copy
    existing_kw = list(data.get('requirements', {}).get('keywords') or [])
    if len(existing_kw) < 3:
        from app.ai.parser.enrichment.jd_text_inference import extract_jd_keywords_from_text

        derived = extract_jd_keywords_from_text(
            raw_text,
            max_items=20,
            preferred_skills=list(data.get('skills', {}).get('preferred') or []),
            mandatory_skills=list(data.get('skills', {}).get('mandatory') or []),
        )
        if derived:
            data['requirements']['keywords'] = derived
        elif existing_kw:
            tech = extract_tech_keywords_from_text(raw_text, max_items=15)
            data['requirements']['keywords'] = list(dict.fromkeys([*existing_kw, *tech]))[:20]

    for name in CORE_FIELDS:
        ev = evidence.get(name, False)
        is_filled = filled.get(name, False)
        if name in recovered:
            status: CoverageStatus = 'recovered'
        elif is_filled:
            status = 'filled'
        elif ev:
            status = 'missing_with_evidence'
        else:
            status = 'missing_no_evidence'
        report.fields.append(
            FieldCoverage(
                field=name,
                status=status,
                evidence=ev,
                detail='recovered from source' if name in recovered else '',
            )
        )

    return JobProfile.model_validate(data), report
