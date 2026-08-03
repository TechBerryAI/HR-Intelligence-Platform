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
    extract_location_from_text,
    extract_qualifications_from_text,
    extract_responsibilities_from_text,
    extract_salary_from_text,
    extract_skills_from_text,
    extract_title_from_text,
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
    # Labeled first line: "Job Title: Backend Developer"
    m = re.search(
        r'(?im)^(?:job\s+title|title|position|role)\s*[:\-]\s*(.+)$',
        full_text[:800],
    )
    if m:
        return m.group(1).strip()[:120]
    for line in (section_text or full_text).splitlines()[:8]:
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if low.startswith(('job description', 'about', 'company', 'location', 'salary', 'employment')):
            continue
        # Strip leading label if present
        s2 = re.sub(r'(?i)^(?:job\s+title|title|position)\s*[:\-]\s*', '', s).strip()
        if s2 and len(s2) <= 120:
            return s2
    return extract_title_from_text(full_text)


def parse_jd_summary(section_text: str, full_text: str) -> str:
    if section_text.strip():
        return section_text.strip()[:4000]
    return ''


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
        return _bullets(section_text)[:30]
    _, preferred, _ = extract_skills_from_text(full_text)
    return preferred


def parse_mandatory_skills(section_text: str, full_text: str) -> list[str]:
    if section_text.strip():
        return _bullets(section_text)[:40]
    mandatory, _, general = extract_skills_from_text(full_text)
    return mandatory or general


def parse_benefits(section_text: str, full_text: str) -> list[str]:
    if section_text.strip():
        return _bullets(section_text)[:20]
    return []


def parse_location(section_text: str, full_text: str) -> str:
    if section_text.strip():
        line = section_text.strip().splitlines()[0].strip()
        if line:
            return line[:120]
    return extract_location_from_text(full_text)


def parse_salary(section_text: str, full_text: str) -> str:
    if section_text.strip():
        return section_text.strip().splitlines()[0].strip()[:120]
    return extract_salary_from_text(full_text)


def parse_experience_range(section_text: str, full_text: str) -> tuple[Optional[float], Optional[float]]:
    src = section_text or full_text
    return extract_experience_years(src)


def parse_jd_from_sections(
    sections: list[SectionSpan],
    full_text: str,
    *,
    max_workers: int = 4,
) -> JobProfile:
    title_text = pick_section(sections, 'Title', 'Job Title', 'Position')
    summary_text = pick_section(sections, 'Summary', 'About the Role', 'Overview', 'Job Description')
    resp_text = pick_section(sections, 'Responsibilities', 'Key Responsibilities', 'Duties', 'Role')
    req_text = pick_section(sections, 'Requirements', 'Qualifications')
    mand_text = pick_section(sections, 'Required Skills', 'Mandatory Skills', 'Core Skills', 'Skills')
    pref_text = pick_section(sections, 'Preferred Skills', 'Nice to Have', 'Nice-to-Have')
    ben_text = pick_section(sections, 'Benefits')
    loc_text = pick_section(sections, 'Location')
    sal_text = pick_section(sections, 'Salary', 'Compensation')
    exp_text = pick_section(sections, 'Experience')

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
    company = extract_company_from_text(full_text)
    employment = extract_employment_type_from_text(full_text)
    mandatory = results['mand']
    preferred = results['pref']
    general = list(mandatory)

    return JobProfile(
        basic=JobBasicInfo(
            title=results['title'],
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
