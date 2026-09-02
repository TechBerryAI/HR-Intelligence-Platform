"""Unit tests for generalized resume parsing hardening (no person-specific rules)."""
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
    is_bullet_line,
    join_duty_lines,
    split_inline_bullets,
    split_bullet_items,
)
from app.ai.document_intelligence.deterministic import extract_date_range  # noqa: E402
from app.ai.document_intelligence.layout_doc import from_plain_text  # noqa: E402
from app.ai.document_intelligence.parsers.resume import (  # noqa: E402
    parse_education,
    parse_experience,
    parse_languages,
    parse_projects,
    parse_skills,
)
from app.ai.parser.engine.sections import detect_sections  # noqa: E402
from app.ai.parser.layout.heuristic import normalize_section_header  # noqa: E402


def test_inline_bullets_split_without_touching_hyphens():
    text = 'Intro. • Developed REST APIs using .NET • Improved performance by 40%'
    out = split_inline_bullets(text)
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    assert any(ln.startswith('• Developed') for ln in lines)
    assert any('40%' in ln for ln in lines)
    assert is_bullet_line('Used well-known libraries') is False
    assert is_bullet_line('- Developed REST APIs') is True
    assert 'well-known' in split_inline_bullets('Used well-known libraries')


def test_join_duty_lines_keeps_bullet_boundaries():
    blob = join_duty_lines(
        [
            '• Developed REST APIs using .NET',
            '• Improved application performance by 40%',
            '• Worked with SQL Server',
        ]
    )
    items = [ln for ln in blob.splitlines() if ln.strip()]
    assert len(items) == 3
    assert '40%' in items[1]


def test_numbered_and_lettered_lists():
    items = split_bullet_items('1. First duty\n2. Second duty\n(a) Extra\n(b) More')
    assert len(items) >= 4


def test_date_variants_including_till_date_and_ordinal():
    assert extract_date_range('May 2024 - Present')[1] == 'Present'
    assert extract_date_range('07/2022 - Present')[0].startswith('2022')
    assert extract_date_range('2019–2022') == ('2019', '2022')
    assert extract_date_range('June 2024 - Till Date')[1] == 'Present'
    assert extract_date_range('Jan 2023 - Ongoing')[1] == 'Present'
    start, _ = extract_date_range('10th May 2024 - Present')
    assert start.startswith('2024')


def test_section_aliases_are_semantic_not_sentences():
    assert normalize_section_header('Core Competencies') == 'Skills'
    assert normalize_section_header('TECHNICAL PROFICIENCY') == 'Skills'
    assert normalize_section_header('Academic Qualifications') == 'Education'
    assert normalize_section_header('Linguistic Proficiency') == 'Languages'
    assert normalize_section_header('Industrial Training') == 'Experience'
    assert normalize_section_header('Academic Projects') == 'Projects'
    assert normalize_section_header('Developed REST APIs using Python and SQL.') is None
    assert normalize_section_header('I have strong technical proficiency in Excel') is None


def test_unusual_headers_detected_as_sections():
    text = (
        'Ada Lovelace\nada@example.com\n+919876543210\n\n'
        'Core Competencies\nPython, SQL\n\n'
        'Academic Background\nB.Tech | State University | 2020\n'
    )
    labels = {s.label for s in detect_sections(text, 'resume')}
    assert 'Skills' in labels
    assert 'Education' in labels


def test_education_table_rows_do_not_mix():
    section = (
        'Year | Degree | Institution | Percentage\n'
        '2020 | B.Tech | Alpha Institute | 8.2\n'
        '2022 | MBA | Beta School | 72%\n'
    )
    rows = parse_education(section)
    assert len(rows) == 2
    degrees = { (r.degree or '').lower() for r in rows }
    inst = { (r.institution or '').lower() for r in rows }
    assert any('b.tech' in d or 'btech' in d.replace(' ', '') for d in degrees)
    assert any('mba' in d for d in degrees)
    assert any('alpha' in i for i in inst)
    assert any('beta' in i for i in inst)
    # no cross-row mix
    for r in rows:
        blob = f'{(r.degree or "")} {(r.institution or "")}'.lower()
        assert not ('b.tech' in blob and 'beta' in blob)
        assert not ('mba' in blob and 'alpha' in blob)


def test_mms_bracket_field_and_pursuing_stay_one_row():
    section = (
        'MMS [Marketing]\n'
        'Kohinoor Business School\n'
        '2023–2025\n'
        'Pursuing\n'
    )
    rows = parse_education(section)
    assert len(rows) >= 1
    row = next(r for r in rows if 'mms' in (r.degree or '').lower() or 'kohinoor' in (r.institution or '').lower())
    assert 'mms' in (row.degree or '').lower()
    assert 'market' in (row.field or '').lower() or 'market' in (row.degree or '').lower()
    assert 'kohinoor' in (row.institution or '').lower()
    assert row.end in ('2025', 'Present', '2025-01') or (row.start and '2023' in row.start)


def test_experience_keeps_job_without_dates():
    section = 'Company: Northwind Ltd\nRole: Developer\n• Built APIs\n'
    jobs = parse_experience(section)
    assert len(jobs) >= 1
    assert any('northwind' in (j.company or '').lower() for j in jobs)
    assert any('developer' in (j.role or '').lower() for j in jobs)
    desc = jobs[0].description or ''
    assert 'Built APIs' in desc


def test_bullets_stay_separate_in_experience_description():
    section = (
        'Acme Corp | Software Engineer | Jan 2022 - Present\n'
        '• Developed REST APIs using .NET\n'
        '• Improved application performance by 40%\n'
        '• Worked with SQL Server\n'
    )
    jobs = parse_experience(section)
    assert jobs
    lines = [ln for ln in (jobs[0].description or '').splitlines() if ln.strip()]
    assert len(lines) >= 3
    assert not (jobs[0].description or '').startswith('Developed REST APIs using .NET Improved')


def test_internships_are_experience_not_fake_jobs_from_project_bullets():
    section = (
        'Summer Internship\n'
        'Intern — Contoso Labs | May 2024 - Jul 2024\n'
        '• Researched customer analytics\n'
    )
    jobs = parse_experience(section)
    assert any('contoso' in f'{(j.company or "")} {(j.role or "")}'.lower() for j in jobs)
    assert not any('researched customer' in (j.company or '').lower() for j in jobs)


def test_projects_group_heading_and_bullets():
    section = (
        'Inventory App\n'
        '• Built REST APIs\n'
        '• Used SQL Server\n'
        'Campus Portal\n'
        'Designed a portal for students\n'
    )
    projs = parse_projects(section)
    names = [ (p.name or '').lower() for p in projs ]
    assert any('inventory' in n for n in names)
    assert any('campus' in n for n in names)
    inv = next(p for p in projs if 'inventory' in (p.name or '').lower())
    assert 'REST' in (inv.description or '') or 'SQL' in (inv.description or '')
    assert '\n' in (inv.description or '') or 'Built' in (inv.description or '')


def test_skills_not_truncated_from_skilled_in():
    skills = parse_skills('Skilled in C#, .NET, SQL', '')
    names = [s.name.lower() for s in skills]
    assert not any(n.startswith('ed in') for n in names)
    assert any('sql' in n or 'c#' in n or '.net' in n for n in names)


def test_categorized_skills_and_contact_not_skills():
    skills = parse_skills(
        'Programming: C#, Java\nDatabase: SQL\nemail: a@b.com\n+919876543210',
        '',
    )
    names = ' '.join(s.name.lower() for s in skills)
    assert 'sql' in names or 'c#' in names or 'java' in names
    assert 'a@b.com' not in names
    assert '9876543210' not in names.replace(' ', '')


def test_languages_split_on_ampersand():
    langs = parse_languages('Marathi, Hindi & English')
    names = { (l.name or '').lower() for l in langs }
    assert {'marathi', 'hindi', 'english'} <= names


def test_references_do_not_become_experience():
    section = (
        'Acme Corp | Analyst | 2020 - 2021\n'
        'References\n'
        'Ayush Saxsena (Project Head)\n'
        '9575342145\n'
    )
    jobs = parse_experience(section)
    blob = ' '.join(f'{j.role} {j.company}' for j in jobs).lower()
    assert 'ayush' not in blob
    assert '9575342145' not in blob
    assert not any(j.company and j.company.replace(' ', '').isdigit() for j in jobs)


def test_layout_doc_from_plain_text_marks_bullets_and_headings():
    doc = from_plain_text(
        'Jane Doe\nSkills\n• Python\n• SQL\nExperience\nAcme | Engineer | 2020-2021\n'
    )
    assert doc.source == 'plain_text'
    assert any(ln.is_bullet for ln in doc.lines)
    assert any(ln.is_heading_candidate for ln in doc.lines)


def test_project_three_bullets_are_one_record():
    projs = parse_projects(
        'PROJECT A\n• Developed X\n• Implemented Y\n• Improved Z\n'
    )
    assert len(projs) == 1
    desc = projs[0].description or ''
    assert desc.count('\n') >= 2
    assert 'Developed X' in desc and 'Implemented Y' in desc and 'Improved Z' in desc
    assert not any('developed x' in (p.name or '').lower() for p in projs)


def test_project_paragraphs_without_bullets_stay_one():
    projs = parse_projects(
        'Campus Portal\n'
        'Designed a portal for students and faculty.\n'
        'The system stores attendance in MySQL.\n'
    )
    assert len(projs) == 1
    assert 'campus' in (projs[0].name or '').lower()
    assert 'MySQL' in (projs[0].description or '') or 'attendance' in (projs[0].description or '')


def test_multiple_projects_with_bullets():
    projs = parse_projects(
        'Inventory App\n• Built REST APIs\n• Used SQL\n'
        'VOLUME GENERATION TOOL (NSE MARKET)\n• Implemented multithreading\n'
    )
    assert len(projs) == 2


def test_project_technology_list_is_not_a_new_project():
    projs = parse_projects(
        'Billing Platform\nTechnologies: Python, Django, PostgreSQL\n'
        'Developed invoicing workflows for retail clients.\n'
    )
    assert len(projs) == 1
    blob = f'{projs[0].name} {projs[0].description}'.lower()
    assert 'billing' in blob
    assert 'python' in blob or 'django' in blob


def test_internship_project_title_and_learnings_one_job():
    jobs = parse_experience(
        'Summer Internship – Amul India Ltd (10th May 2024 – 10th July 2024)\n'
        'Project Title: Consumer Behaviour Towards Fresh Products.\n'
        'Learnings: Observed supply chain and promotional marketing.\n'
        'Conclusion: Gained practical market knowledge.\n'
    )
    assert len(jobs) == 1
    desc = jobs[0].description or ''
    assert 'Consumer Behaviour' in desc
    assert 'Learnings' in desc or 'supply chain' in desc.lower()
    assert not any('consumer behaviour' in (j.company or '').lower() for j in jobs)


def test_skills_bullet_list_and_comma_and_categories():
    a = parse_skills('Computer Skills\n• MS-Office\n• Excel', '')
    b = parse_skills('C#, .NET, SQL, HTML', '')
    c = parse_skills('Programming:\nC#, Java\nDatabases:\nSQL\nTools:\nGit, Excel', '')
    assert any('office' in s.name.lower() or 'excel' in s.name.lower() for s in a)
    assert any('sql' in s.name.lower() for s in b)
    names = ' '.join(s.name.lower() for s in c)
    assert 'sql' in names and ('c#' in names or 'java' in names)


def test_glyph_lost_duty_lines_still_separate_items():
    from app.ai.document_intelligence.bullets import join_duty_lines

    blob = join_duty_lines(
        [
            'Developed REST APIs using .NET',
            'Improved application performance by 40%',
            'Worked with SQL Server',
        ]
    )
    lines = [ln for ln in blob.splitlines() if ln.strip()]
    assert len(lines) == 3
    assert '\n' in blob


def test_lowercase_wrap_is_not_a_new_list_item():
    from app.ai.document_intelligence.bullets import join_duty_lines

    blob = join_duty_lines(
        [
            'Implemented multithreading in a real-time data',
            'processing system using C# Task Parallel Library',
        ]
    )
    assert blob.count('\n') == 0
    assert 'processing system' in blob


def test_two_column_like_project_block_does_not_explode():
    projs = parse_projects(
        'TATA GROUP & AMERICAN INTERNATIONAL\n'
        'GROUP (TATA AIG) Client: American\n'
        'International Group (AIG) (07/2022 - Present)\n'
        'Designing and developing web applications using java\n'
        'Developed user interfaces to interact with databases\n'
        'VOLUME GENERATION TOOL (NSE MARKET)\n'
        '(06/2024 - Present)\n'
        'Implemented multithreading in a real-time data\n'
        'processing system using C#\n'
        'STRENGTHS\n'
        'Proficient in C#\n'
    )
    assert 1 <= len(projs) <= 3
    names = ' '.join(p.name.lower() for p in projs)
    assert 'tata' in names or 'aig' in names
    assert 'volume' in names or 'nse' in names
    assert not any('proficient' in (p.name or '').lower() for p in projs)


def test_shared_client_projects_meta_does_not_drop_jobs():
    jobs = parse_experience(
        'Digital Marketing Executive -  Hawkium  -  (Sep 2024 -  Now)\n'
        'Digital Marketing Executive -  Tridhya Tech Public Limited  -  (Dec 2023 -  Sep 2024)\n'
        'Client Name/Projects -  Silwatech UAE ,  Vibing Tech , TridhyaTech\n'
        'Responsibilities\n'
        '• Managed and optimized social media platforms for multiple brands\n'
        'Resource Manager - Tridhya Tech - (Dec 2022 - Dec 2023)\n'
        '• Managed resource allocation and task coordination\n'
    )
    assert len(jobs) == 3
    companies = [ (j.company or '').lower() for j in jobs ]
    assert companies[0] == 'hawkium'
    assert 'tridhya tech public limited' in companies[1]
    assert companies[2] == 'tridhya tech'
    assert not any(c == 'responsibilities' for c in companies)
    desc = jobs[0].description or ''
    assert 'Managed' in desc
    assert '\n' in desc or '•' in desc


def test_indented_duty_without_glyph_is_list_item():
    from app.ai.document_intelligence.bullets import restore_inferred_list_markers

    restored = restore_inferred_list_markers(
        'Acme | Engineer | 2020-2021\n'
        '  Developed REST APIs using .NET\n'
        '  Improved application performance by 40%\n'
        'Handled cash operations for retail customers.\n'
    )
    assert restored.count('•') >= 2
    assert 'Handled cash operations' in restored
    assert not restored.split('Handled')[1].strip().startswith('•')
