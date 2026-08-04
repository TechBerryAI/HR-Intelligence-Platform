"""JD section parsers — emit JobProfile fragments only."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

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
from app.ai.document_intelligence.sections import SectionSpan, pick_section
from app.ai.parser.enrichment.jd_text_inference import (
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
    is_non_title_label,
    is_plausible_job_title,
    normalize_skill_tokens,
)
from app.ai.parser.enrichment.resume_text_inference import split_list_items


def _bullets(text: str) -> list[str]:
    if not text:
        return []
    items = split_list_items(text)
    out = []
    for i in items:
        s = re.sub(r'^[\s•·\-\*]+', '', i).strip()
        if s:
            out.append(s)
    return out


def parse_title(section_text: str, full_text: str) -> str:
    kv = extract_kv_fields_from_text(full_text)
    if kv.get('title') and is_plausible_job_title(kv['title']):
        return kv['title'][:120]

    # Labeled patterns across common JD formats
    labeled = extract_title_from_text(full_text)
    if labeled and is_plausible_job_title(labeled):
        return labeled

    m = re.search(
        r'(?im)^(?:job\s+title|title|position(?:\s+title)?|designation)\s*[:\-–—]\s*(.+)$',
        full_text[:1200],
    )
    if m:
        cand = m.group(1).strip()[:120]
        if is_plausible_job_title(cand):
            return cand

    for line in (section_text or full_text).splitlines()[:15]:
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if low.startswith((
            'job description', 'about', 'company', 'location', 'salary', 'employment',
            'experience', 'responsibilit', 'requirement', 'skill', 'qualification',
            'benefit', 'what you', 'notice period', 'primary skills', 'role overview',
            'job summary', 'overview', 'public', 'confidential',
        )):
            continue
        if is_non_title_label(s):
            continue
        s2 = re.sub(
            r'(?i)^(?:job\s+title|title|position(?:\s+title)?|designation|role)\s*[:\-–—]\s*',
            '',
            s,
        ).strip()
        if is_plausible_job_title(s2):
            return s2[:120]
    return ''


def parse_jd_summary(section_text: str, full_text: str) -> str:
    if section_text.strip():
        return section_text.strip()[:4000]
    overview = extract_overview_from_text(full_text)
    return overview[:4000] if overview else ''


def parse_responsibilities(section_text: str, full_text: str) -> list[str]:
    if section_text.strip():
        return _bullets(section_text)[:30]
    return extract_responsibilities_from_text(full_text)


def parse_requirements(section_text: str, full_text: str) -> list[str]:
    if section_text.strip():
        return _bullets(section_text)[:20]
    return extract_qualifications_from_text(full_text)


def parse_preferred_skills(section_text: str, full_text: str) -> list[str]:
    if section_text.strip():
        return normalize_skill_tokens(_bullets(section_text), max_items=30)
    _, preferred, _ = extract_skills_from_text(full_text)
    return preferred


def parse_mandatory_skills(section_text: str, full_text: str) -> list[str]:
    if section_text.strip():
        skills = normalize_skill_tokens(_bullets(section_text), max_items=40)
        if skills:
            return skills
    mandatory, preferred, general = extract_skills_from_text(full_text)
    skills = mandatory or general
    if len(skills) < 3:
        # Prefer text before preferred sections so preferred tech is not promoted to mandatory
        backfill_text = full_text
        cut = re.search(
            r'(?i)(?:preferred\s+(?:skills?|qualifications?)|nice[- ]?to[- ]?have|bonus\s+points?)',
            full_text or '',
        )
        if cut and cut.start() > 40:
            backfill_text = full_text[: cut.start()]
        tech = extract_tech_keywords_from_text(backfill_text, max_items=20)
        seen = {s.lower() for s in skills} | {s.lower() for s in preferred}
        for tok in tech:
            if tok.lower() not in seen:
                skills.append(tok)
                seen.add(tok.lower())
            if len(skills) >= 20:
                break
    return skills[:40]


def parse_benefits(section_text: str, full_text: str) -> list[str]:
    if section_text.strip():
        return _bullets(section_text)[:20]
    return []


def parse_location(section_text: str, full_text: str) -> str:
    kv = extract_kv_fields_from_text(full_text)
    if kv.get('location'):
        cleaned = extract_location_from_text(f"Location: {kv['location']}") or kv['location']
        if cleaned:
            return cleaned[:120]
    if section_text.strip():
        line = section_text.strip().splitlines()[0].strip()
        # Prefer labeled extraction for cleanup of interview notes
        cleaned = extract_location_from_text(f'Location: {line}') or extract_location_from_text(full_text)
        if cleaned:
            return cleaned[:120]
        if line and not line.lower().startswith(('location', 'work location')):
            return line[:120]
    return extract_location_from_text(full_text)


def parse_salary(section_text: str, full_text: str) -> str:
    kv = extract_kv_fields_from_text(full_text)
    if kv.get('salary'):
        return kv['salary'][:120]
    if section_text.strip():
        return section_text.strip().splitlines()[0].strip()[:120]
    return extract_salary_from_text(full_text)


def parse_experience_range(section_text: str, full_text: str) -> tuple[Optional[float], Optional[float]]:
    kv = extract_kv_fields_from_text(full_text)
    if kv.get('experience'):
        min_y, max_y = extract_experience_years(kv['experience'])
        if min_y is not None or max_y is not None:
            return min_y, max_y
    # Prefer Experience section; fall back to labeled lines in full text only
    if section_text and section_text.strip():
        min_y, max_y = extract_experience_years(section_text)
        if min_y is not None or max_y is not None:
            return min_y, max_y
    # Labeled experience anywhere in JD (strict years requirement inside extractor)
    return extract_experience_years(full_text)


def parse_jd_from_sections(
    sections: list[SectionSpan],
    full_text: str,
    *,
    max_workers: int = 4,
) -> JobProfile:
    title_text = pick_section(sections, 'Title', 'Job Title', 'Position')
    summary_text = pick_section(
        sections, 'Summary', 'About the Role', 'Overview', 'Job Description', 'Job Summary', 'Role Overview'
    )
    resp_text = pick_section(sections, 'Responsibilities', 'Key Responsibilities', 'Duties')
    req_text = pick_section(sections, 'Requirements', 'Qualifications')
    mand_text = pick_section(
        sections,
        'Required Skills',
        'Mandatory Skills',
        'Core Skills',
        'Primary Skills',
        'Technical Skills',
        'Skills',
    )
    pref_text = pick_section(
        sections,
        'Preferred Skills',
        'Preferred Qualifications',
        'Nice to Have',
        'Nice-to-Have',
        'Nice to Have Skills',
        'Bonus Points',
        'Good to Have',
    )
    ben_text = pick_section(sections, 'Benefits')
    loc_text = pick_section(sections, 'Location')
    sal_text = pick_section(sections, 'Salary', 'Compensation')
    exp_text = pick_section(sections, 'Experience', 'Work Experience')

    results: dict[str, Any] = {}

    def _run(name, fn, *args):
        results[name] = fn(*args)

    tasks = [
        ('title', parse_title, title_text, full_text),
        ('summary', parse_jd_summary, summary_text, full_text),
        ('resp', parse_responsibilities, resp_text, full_text),
        ('req', parse_requirements, req_text, full_text),
        ('mand', parse_mandatory_skills, mand_text, full_text),
        ('pref', parse_preferred_skills, pref_text, full_text),
        ('ben', parse_benefits, ben_text, full_text),
        ('loc', parse_location, loc_text, full_text),
        ('sal', parse_salary, sal_text, full_text),
        ('exp', parse_experience_range, exp_text, full_text),
    ]

    workers = max(1, min(max_workers, len(tasks)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_run, name, fn, *args) for name, fn, *args in tasks]
        for fut in as_completed(futs):
            fut.result()

    min_y, max_y = results['exp']
    kv = extract_kv_fields_from_text(full_text)
    company = kv.get('company') or extract_company_from_text(full_text)
    employment = kv.get('employment_type') or extract_employment_type_from_text(full_text)
    mandatory = results['mand']
    preferred = results['pref']
    if kv.get('skills') and not mandatory:
        from app.ai.parser.enrichment.jd_text_inference import normalize_skill_tokens as _norm

        mandatory = _norm(
            [p.strip() for p in re.split(r'[,•·|]', kv['skills']) if p.strip()],
            max_items=30,
        )
    general = list(mandatory)
    title = results['title']
    if title and not is_plausible_job_title(title):
        title = ''

    return JobProfile(
        basic=JobBasicInfo(
            title=title,
            company=company,
            employment_type=employment,
            description=results['summary'],
        ),
        requirements=JobRequirements(
            min_experience_years=min_y,
            max_experience_years=max_y,
            qualifications=results['req'],
            keywords=[],
        ),
        responsibilities=JobResponsibilities(items=results['resp']),
        skills=JobSkills(mandatory=mandatory, preferred=preferred, general=general),
        benefits=JobBenefits(items=results['ben']),
        location=JobLocation(primary=results['loc']),
        compensation=JobCompensation(salary_range=results['sal']),
    )
