"""Generalized section-detection regressions.

No candidate names, employers, filenames, coordinates, or resume-specific rules.
Uncertain boundaries must preserve lines as Unclassified — never invent jobs.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.parsers.resume import (  # noqa: E402
    parse_resume_from_sections,
)
from app.ai.document_intelligence.sections import pick_section  # noqa: E402
from app.ai.parser.engine.sections import detect_sections  # noqa: E402
from app.ai.parser.layout.heuristic import normalize_section_header  # noqa: E402


def _labels(text: str) -> list[str]:
    return [s.label for s in detect_sections(text, 'resume')]


def _unclassified(text: str) -> str:
    return pick_section(detect_sections(text, 'resume'), 'Unclassified')


def test_unusual_headings_map_to_canonical_labels():
    assert normalize_section_header('Curriculum Vitae') is None
    assert normalize_section_header('CV') is None
    assert normalize_section_header('RESUME') is None
    assert normalize_section_header('Work Summary') == 'Summary'
    assert normalize_section_header('WORKSUMMARY') == 'Summary'
    assert normalize_section_header('Personal Summary') == 'Summary'
    assert normalize_section_header('EXPERIENCESUMMARY') == 'Summary'
    assert normalize_section_header('Experience Summary') == 'Summary'
    assert normalize_section_header('EXPERIEN C E SUMMA R Y') == 'Summary'
    assert normalize_section_header('Personalinformation') == 'Personal Information'
    assert normalize_section_header('PERSONALINFORMATION:') == 'Personal Information'
    assert normalize_section_header('Other Technical Skills') == 'Skills'
    assert normalize_section_header('Skillset') == 'Skills'
    assert normalize_section_header('Skill Set') == 'Skills'


def test_short_skills_section_preserves_sidebar_evidence():
    text = (
        'Jordan Hale\njordan@example.com\n9876543210\n\n'
        'Skills\nMS-Office\n\n'
        'Achievements\nCompleted a Python and SQL workshop.\n'
        'Personal Details\nTechnical Skills: Linux, Ansible, AWS\n'
        'Education\nB.Com, City College, 2018\n'
    )
    spans = detect_sections(text, 'resume')
    skills = [s for s in spans if s.label == 'Skills']
    assert skills
    assert any(s.source == 'uncertain' for s in skills)
    unclassified = pick_section(spans, 'Unclassified').lower()
    assert 'python' in unclassified or 'linux' in unclassified or 'ansible' in unclassified
    profile = parse_resume_from_sections(spans, text)
    names = ' '.join(s.name.lower() for s in profile.skills)
    assert 'office' in names or 'ms-office' in names
    assert 'linux' in names or 'ansible' in names or 'python' in names or 'aws' in names
    assert profile.experience == []


def test_short_education_section_preserves_following_evidence():
    text = (
        'Alex Rivera\nalex@example.com\n\n'
        'Education\n\n'
        'Personal Details\nB.Sc. Information Technology, State University, 2022\n'
        'Skills\nPython, SQL, Linux\n'
    )
    spans = detect_sections(text, 'resume')
    education = [s for s in spans if s.label == 'Education']
    assert education
    assert any(s.source == 'uncertain' for s in education)
    unclassified = pick_section(spans, 'Unclassified').lower()
    assert 'b.sc' in unclassified or 'university' in unclassified or 'information' in unclassified
    profile = parse_resume_from_sections(spans, text)
    assert any((r.degree or '').strip() or (r.institution or '').strip() for r in profile.education)
    assert profile.experience == []


def test_content_after_empty_heading_is_not_discarded():
    text = (
        'Riley Chen\nriley@example.com\n\n'
        'Skills\n'
        'Contact\nPython, SQL, Linux\n'
        'Experience\nNorthwind Traders | Analyst | 2021 - 2024\n'
        'Built reporting dashboards.\n'
        'Education\nB.Tech, State University, 2020\n'
    )
    spans = detect_sections(text, 'resume')
    skills = [s for s in spans if s.label == 'Skills']
    assert skills
    assert any(s.source == 'uncertain' for s in skills)
    labels = [s.label for s in spans]
    assert labels.count('Experience') == 1
    profile = parse_resume_from_sections(spans, text)
    assert len(profile.experience) == 1
    job_blob = f"{profile.experience[0].company or ''} {profile.experience[0].role or ''}".lower()
    assert 'northwind' in job_blob
    names = ' '.join(s.name.lower() for s in profile.skills)
    assert 'python' in names or 'sql' in names or 'linux' in names


def test_missing_experience_heading_does_not_invent_jobs():
    text = (
        'Casey Morgan\ncasey@example.com\n+919111222333\n'
        'Brightleaf Technologies, Pune\nJune 2020 - Present\n\n'
        'Summary\nData engineer with warehouse and pipeline work.\n'
        'Education\nB.E. Computer, State University, 2019\n'
        'Skills\nPython, SQL, Azure, MySQL\n'
    )
    spans = detect_sections(text, 'resume')
    assert 'Experience' not in [s.label for s in spans]
    unclassified = pick_section(spans, 'Unclassified')
    assert 'Brightleaf Technologies' in unclassified
    assert 'June 2020' in unclassified
    profile = parse_resume_from_sections(spans, text)
    # Parser recovery (not section detection) may emit one credible job.
    names = ' '.join(s.name.lower() for s in profile.skills)
    assert 'python' in names or 'sql' in names
    if profile.experience:
        blob = ' '.join(f'{j.company} {j.role}' for j in profile.experience).lower()
        assert 'brightleaf' in blob or 'technolog' in blob


def test_two_column_duplicate_sections_keep_unique_lines():
    text = (
        'Sam Patel\nsam@example.com\n\n'
        'Education\nB.Tech, East College, 2018\n'
        'Skills\nPython, SQL\n'
        'Experience\nContoso | Developer | 2019-2021\nBuilt APIs.\n'
        'Education\nB.Tech, East College, 2018\n'
        'Skills\nPython, SQL, Linux\n'
    )
    spans = detect_sections(text, 'resume')
    labels = [s.label for s in spans]
    assert labels.count('Experience') == 1
    # Second Education is a near-echo and must not be dropped silently.
    unclassified = pick_section(spans, 'Unclassified').lower()
    assert 'east college' in unclassified or 'b.tech' in unclassified or 'linux' in unclassified
    profile = parse_resume_from_sections(spans, text)
    assert len(profile.experience) == 1
    names = ' '.join(s.name.lower() for s in profile.skills)
    assert 'linux' in names or 'python' in names
    degrees = ' '.join((e.degree or '').lower() for e in profile.education)
    assert 'b.tech' in degrees or 'btech' in degrees.replace(' ', '')


def test_unlabeled_preamble_is_preserved_not_turned_into_jobs():
    text = (
        'Morgan Lee\nmorgan@example.com\n8217276434\n'
        'Employment background reflects well over 2 years in document stores.\n'
        'B.E. Information Science, State University, 2021\n'
        'Python, AWS, Linux, MongoDB\n'
    )
    spans = detect_sections(text, 'resume')
    labels = [s.label for s in spans]
    assert 'Preamble' in labels
    assert 'Unclassified' in labels
    assert 'Experience' not in labels
    unclassified = pick_section(spans, 'Unclassified')
    assert '2 years' in unclassified
    assert 'Information Science' in unclassified
    profile = parse_resume_from_sections(spans, text)
    assert profile.experience == []
    names = ' '.join(s.name.lower() for s in profile.skills)
    assert 'python' in names or 'linux' in names or 'aws' in names
    # Preamble dumps are preserved, not parsed as jobs. Education recovery from
    # unlabeled text is a later bottleneck; the lines must remain visible.


def test_weak_closer_after_short_experience_does_not_steal_later_sections():
    text = (
        'Dana Cole\ndana@example.com\n\n'
        'Experience\nContact\n'
        'Languages\nEnglish, Hindi\n'
        'Summary\nDatabase administrator with cluster work.\n'
        'Skills\nOracle, Linux, Azure\n'
        'Education\nMCA, State University, 2006\n'
        'Experience\nFabrikam | DBA | 2018 - 2023\nManaged production clusters.\n'
    )
    spans = detect_sections(text, 'resume')
    labels = [s.label for s in spans]
    assert 'Skills' in labels
    assert 'Education' in labels
    profile = parse_resume_from_sections(spans, text)
    job_blob = ' '.join(f'{j.company or ""} {j.role or ""}' for j in profile.experience).lower()
    assert 'fabrikam' in job_blob
    assert 'english' not in job_blob
    names = ' '.join(s.name.lower() for s in profile.skills)
    assert 'oracle' in names or 'linux' in names


def test_curriculum_vitae_title_stays_in_preamble():
    text = (
        'Curriculum Vitae\n'
        'Taylor Reed\ntaylor@example.com\n+915050505050\n\n'
        'Experience\nProseware | Writer | 2020 - 2022\nWrote product copy.\n'
        'Education\nMA English, Crown College, 2019\n'
    )
    spans = detect_sections(text, 'resume')
    labels = [s.label for s in spans]
    assert 'Curriculum Vitae' not in labels
    preamble = pick_section(spans, 'Preamble')
    assert 'Taylor Reed' in preamble
    profile = parse_resume_from_sections(spans, text)
    assert len(profile.experience) == 1
    job_blob = f"{profile.experience[0].company or ''} {profile.experience[0].role or ''}".lower()
    assert 'proseware' in job_blob
    assert 'curriculum' not in job_blob


def test_experience_summary_heading_does_not_invent_jobs():
    text = (
        'Jamie Fox\njamie@example.com\n\n'
        'Skills\nPython, SQL\n'
        'EXPERIENCESUMMARY\n'
        'Rebuilding indexes at regular intervals for better performance.\n'
        'Education\nB.E. Computer, State University, 2018\n'
    )
    spans = detect_sections(text, 'resume')
    labels = [s.label for s in spans]
    assert 'Summary' in labels
    profile = parse_resume_from_sections(spans, text)
    assert profile.experience == []


def test_unclassified_is_never_fed_to_experience():
    text = (
        'Jamie Fox\njamie@example.com\n\n'
        'Skills\n\n'
        'Personal Details\nWorked at Wide World Importers from 2019 to 2022 as Analyst.\n'
        'Education\nB.Sc, Harbor College, 2018\n'
    )
    spans = detect_sections(text, 'resume')
    profile = parse_resume_from_sections(spans, text)
    assert profile.experience == []
    unclassified = pick_section(spans, 'Unclassified')
    assert 'Wide World Importers' in unclassified
