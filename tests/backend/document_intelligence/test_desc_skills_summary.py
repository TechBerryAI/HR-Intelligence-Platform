"""Company descriptions, summary lists, and grounded skills.

No candidate names, employers, filenames, coordinates, or resume-specific rules.
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

from app.ai.document_intelligence.bullets import (  # noqa: E402
    has_list_evidence,
    is_glyph_crumb,
    is_wrap_continuation,
    join_duty_lines,
    split_bullet_items,
)
from app.ai.document_intelligence.parsers.resume import (  # noqa: E402
    parse_experience,
    parse_resume_from_sections,
    parse_skills,
    parse_summary,
)
from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical  # noqa: E402
from app.ai.document_intelligence.validation.engine import validate_skill_item  # noqa: E402
from app.ai.parser.engine.sections import detect_sections  # noqa: E402
from app.ai.parser.enrichment.resume_text_inference import (  # noqa: E402
    _normalize_summary_body,
    extract_skills_from_text,
)


def test_glyph_bullets_stay_separate_description_lines():
    jobs = parse_experience(
        'Northwind Ltd | Software Engineer | Jan 2022 - Present\n'
        '• Developed REST APIs using .NET\n'
        '• Improved application performance by 40%\n'
        '• Worked with SQL Server\n',
        '',
    )
    assert len(jobs) == 1
    lines = [ln for ln in (jobs[0].description or '').splitlines() if ln.strip()]
    assert len(lines) >= 3
    assert '40%' in (jobs[0].description or '')


def test_glyphless_duty_verbs_stay_separate_items():
    blob = join_duty_lines(
        [
            'Developed REST APIs using .NET',
            'Improved application performance by 40%',
            'Worked with SQL Server',
        ]
    )
    lines = [ln for ln in blob.splitlines() if ln.strip()]
    assert len(lines) == 3
    assert has_list_evidence(
        [
            'Developed REST APIs using .NET',
            'Improved application performance by 40%',
            'Worked with SQL Server',
        ]
    )


def test_wrapped_paragraph_is_not_fake_bullets():
    blob = join_duty_lines(
        [
            'I am working as a Senior Analyst of the',
            'Data Warehousing platform on cloud environments.',
        ]
    )
    assert blob.count('\n') == 0
    assert 'Data Warehousing' in blob
    assert '•' not in blob


def test_uppercase_wrap_stays_on_same_bullet():
    blob = join_duty_lines(
        [
            '• I am working as a Senior Analyst of the',
            '• Data Warehousing platform.',
        ]
    )
    lines = [ln for ln in blob.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert 'Analyst of the Data Warehousing' in blob
    assert is_wrap_continuation(
        'I am working as a Senior Analyst of the',
        'Data Warehousing platform.',
        nxt_had_bullet=True,
    )


def test_leftover_glyph_does_not_split_wrap_in_experience():
    jobs = parse_experience(
        'Northwind Ltd | Analyst | Jan 2022 - Present\n'
        '• I am working as a Senior Analyst of the\n'
        '• Data Warehousing platform on cloud environments.\n'
        '• Developed REST APIs using .NET\n'
        '• Improved application performance by 40%\n',
        '',
    )
    assert len(jobs) == 1
    desc = jobs[0].description or ''
    lines = [ln for ln in desc.splitlines() if ln.strip()]
    assert len(lines) == 3
    assert 'Analyst of the Data Warehousing' in desc
    assert not any(ln.strip().lstrip('• ').startswith('Data Warehousing') for ln in lines)


def test_duty_verbs_stay_three_items_after_wrap_fix():
    items = split_bullet_items(
        '• Developed REST APIs using .NET\n'
        '• Improved application performance by 40%\n'
        '• Worked with SQL Server\n'
    )
    assert len(items) == 3


def test_empty_glyph_crumb_is_not_an_item():
    assert is_glyph_crumb('') is True
    blob = join_duty_lines(
        [
            '• ',
            '• Conduct keyword research and competitor analysis',
            '• Managed social media profiles',
        ]
    )
    lines = [ln for ln in blob.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert not any(is_glyph_crumb(ln) for ln in lines)


def test_job_header_is_not_used_as_description():
    jobs = parse_experience(
        'HR Recruiter – Contoso Overseas – 01st Jan 2015 to 31st Aug 2018\n'
        'HR Recruiter – Contoso Overseas – 01st Jan 2015 to 31st Aug 2018\n',
        '',
    )
    assert jobs
    desc = (jobs[0].description or '').strip()
    assert desc == '' or 'developed' in desc.lower()


def test_summary_bullet_list_keeps_newlines():
    text = (
        'Summary\n'
        '• Available to work in 24X7 capability.\n'
        '• Installing and maintaining Oracle database software 11g, 12c and 19c\n'
        '• Strong DBA skills and relevant working experience with Oracle Database 11g\n'
    )
    value = parse_summary(text, text)
    lines = [ln for ln in value.splitlines() if ln.strip()]
    assert len(lines) >= 2
    assert 'database software' in value.lower() or '24X7' in value or '24x7' in value.lower()
    cleaned = _normalize_summary_body(text)
    assert '\n' in cleaned
    assert 'database software' in cleaned.lower()
    assert '\n' in cleaned
    assert 'database software' in cleaned.lower()


def test_summary_paragraph_objective_stays_one_paragraph():
    text = (
        'Career Objective\n'
        'To obtain a challenging position in enterprise application integration '
        'where technology integrates with business functionalities.\n'
    )
    value = parse_summary(text, text)
    assert value.count('\n') == 0
    assert 'challenging position' in value.lower()


def test_skills_bullets_are_only_listed_tokens():
    skills = parse_skills('Skills\n• Python\n• SQL\n• Linux\n', '')
    names = [s.name.strip().lower() for s in skills]
    assert names == ['python', 'sql', 'linux'] or set(names) == {'python', 'sql', 'linux'}


def test_personal_details_labeled_skills_only():
    text = (
        'Skills\nMS-Office\n'
        'Personal Details\n'
        "Father's Name: Alex Parent\n"
        'Hobbies: Swimming\n'
        'Technical Skills: Linux, AWS\n'
        'Certificate of Participation: Visit to Exchange Program.\n'
        'Branding and Marketing committee of State Business School\n'
    )
    skills = parse_skills('Skills\nMS-Office', text)
    names = ' '.join(s.name.lower() for s in skills)
    assert 'office' in names or 'ms-office' in names
    assert 'linux' in names or 'aws' in names
    assert 'father' not in names
    assert 'swimming' not in names
    assert 'committee' not in names
    assert 'participation' not in names
    assert validate_skill_item('Work experience = fresher')[0] is False
    assert validate_skill_item('Certificate of Participation: Visit')[0] is False


def test_experience_duties_do_not_become_skills():
    text = (
        'Casey Ng\ncasey@example.com\n\n'
        'Experience\n'
        'Database Administrator — Contoso | Jan 2020 - Present\n'
        '• Administer Oracle databases and perform backups.\n'
        'Education\nB.Com, City College, 2021\n'
    )
    skills = parse_skills('', text)
    names = ' '.join(s.name.lower() for s in skills)
    assert 'oracle' not in names
    assert extract_skills_from_text(text, allow_unlabeled_lists=False) == []


def test_sidebar_unclassified_does_not_dump_biodata_as_skills():
    text = (
        'Alex Rivera\nalex@example.com\n\n'
        'Education\nB.Sc, State University, 2022\n'
        'Skills\n\n'
        'Personal Details\n'
        "Father's Name: Alex Parent\n"
        'Hobbies: Cricket\n'
        'Technical Skills: Linux, AWS\n'
    )
    profile = parse_resume_from_sections(detect_sections(text, 'resume'), text)
    names = ' '.join(s.name.lower() for s in profile.skills)
    assert 'linux' in names or 'aws' in names
    assert 'father' not in names
    assert 'cricket' not in names


def test_end_to_end_bullets_and_grounded_skills():
    text = (
        'Jordan Hale\njordan@example.com\n\n'
        'Summary\n'
        '• Available to work in 24X7 capability.\n'
        '• Installing and maintaining database software on Linux\n\n'
        'Experience\n'
        'Software Engineer | Northwind Ltd | Jan 2022 - Present\n'
        '• Developed REST APIs using .NET\n'
        '• Improved application performance by 40%\n\n'
        'Skills\nPython, SQL, Linux\n'
        'Education\nB.E. Computer, Harbor College, 2021\n'
    )
    profile, form, _ = parse_resume_text_to_canonical(text, allow_semantic=False)
    assert profile.experience
    desc_lines = [ln for ln in (profile.experience[0].description or '').splitlines() if ln.strip()]
    assert len(desc_lines) >= 2
    assert profile.personal.summary.count('\n') >= 1
    skill_names = [s.name.lower() for s in profile.skills]
    assert 'python' in skill_names
    assert 'sql' in skill_names
    assert not any('developed rest' in n for n in skill_names)
    assert '40%' in (form.experiences[0].description or '')


def test_skill_wrap_joins_cert_and_paren_tails():
    skills = parse_skills(
        'Skills\n'
        'Microsoft Certified: Azure Data\n'
        'Fundamentals\n'
        'Python\n'
        'SQL\n'
        'Red hat& CentOS Linux (6.x\n'
        'x)\n',
        '',
    )
    names = [s.name.lower() for s in skills]
    blob = ' '.join(names)
    assert any('azure data fundamentals' in n for n in names)
    assert 'python' in names
    assert 'sql' in names
    assert not any(n.strip() == 'fundamentals' for n in names)
    assert '6.x' in blob and 'linux' in blob
    assert not any(n.strip() in {'x)', ')'} for n in names)


def test_skill_crumbs_and_address_are_rejected():
    skills = parse_skills(
        'Skills\n'
        'Python\n'
        'Certification\n'
        'and troubleshoot\n'
        'configure\n'
        'University/Board\n'
        '% Of Marks\n'
        'District – North Zone\n'
        'Temporary Address: 12 Main Street\n'
        '& PLATFORMS\n'
        'A L E X\n'
        'SKILLS: PROFESSIONAL SUMMARY:\n'
        'unwanted user process.\n',
        '',
    )
    names = [s.name.lower() for s in skills]
    blob = ' '.join(names)
    assert 'python' in names
    assert 'certification' not in names
    assert 'configure' not in names
    assert 'troubleshoot' not in blob
    assert 'university' not in blob
    assert 'marks' not in blob
    assert 'district' not in blob
    assert 'address' not in blob
    assert 'platforms' not in blob
    assert 'a l e x' not in blob
    assert 'summary' not in blob
    assert 'unwanted' not in blob
    assert validate_skill_item('Certification')[0] is False
    assert validate_skill_item('and troubleshoot')[0] is False
    assert validate_skill_item('University/Board')[0] is False
    assert validate_skill_item('Project Name : Xerox')[0] is False
    assert validate_skill_item('7 years of experience (from June')[0] is False
    assert validate_skill_item('55 2.: HSC')[0] is False
    assert validate_skill_item('Role: manual Tester with Database')[0] is False


def test_skill_category_wrap_stays_one_item():
    skills = parse_skills(
        'Skills\n'
        'SEO: Keyword research\n'
        'on-page & off-page\n'
        'and website auditing\n'
        'Python\n',
        '',
    )
    names = [s.name.lower() for s in skills]
    blob = ' '.join(names)
    assert 'python' in names
    assert 'keyword research' in blob
    assert 'on-page' in blob
    assert not any(n.startswith('and website') for n in names)
