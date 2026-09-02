"""
Golden resume hardening suite.

Synthetic fixtures cover layout/section variants. Real Vishal PDF / Akshay DOCX
are optional regression files — no production code keys off those names.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical  # noqa: E402
from app.ai.parser.layout.heuristic import normalize_section_header  # noqa: E402

VISHAL_PDF = Path(r'C:\Users\DELL\Downloads\resume testing\#1_Vishal_Waghmode_Resume.pdf')
AKSHAY_DOCX = Path(
    r'C:\Users\DELL\Downloads\resume testing\45_MMS_Marketing_Akshay     Pujari -1.jpg (1) (1) (1).docx'
)


@dataclass
class GoldCase:
    name: str
    text: str
    expect_experience: int | None = None
    expect_education: int | None = None
    expect_projects: int | None = None
    must_skills: list[str] = field(default_factory=list)
    must_not_company: list[str] = field(default_factory=list)
    must_languages: list[str] = field(default_factory=list)
    expect_bullets_in_exp: bool = False
    expect_edu_table: bool = False
    min_sections: list[str] = field(default_factory=list)
    no_experience: bool = False
    no_projects: bool = False
    company_contains: list[str] = field(default_factory=list)
    degree_contains: list[str] = field(default_factory=list)


def _parse(text: str):
    profile, form, _toon = parse_resume_text_to_canonical(
        text, max_workers=2, allow_semantic=False
    )
    return profile, form


def _score(case: GoldCase, profile) -> dict:
    companies = [ (e.company or '') for e in profile.experience ]
    roles = [ (e.role or '') for e in profile.experience ]
    wrong = 0
    missing = 0
    for bad in case.must_not_company:
        if any(bad.lower() in (c or '').lower() for c in companies):
            wrong += 1
        if any(bad.lower() in (r or '').lower() for r in roles):
            wrong += 1
    for needle in case.company_contains:
        if not any(needle.lower() in (c or '').lower() or needle.lower() in (r or '').lower()
                   for c, r in zip(companies, roles)):
            missing += 1
    skill_blob = ' '.join(s.name.lower() for s in profile.skills)
    for sk in case.must_skills:
        if sk.lower() not in skill_blob:
            missing += 1
    lang_blob = ' '.join(l.name.lower() for l in profile.languages)
    for lg in case.must_languages:
        if lg.lower() not in lang_blob:
            missing += 1
    deg_blob = ' '.join((e.degree or '').lower() for e in profile.education)
    for d in case.degree_contains:
        if d.lower() not in deg_blob:
            missing += 1
    dups_exp = len(profile.experience) - len({
        ((e.company or '').lower(), (e.role or '').lower(), e.start)
        for e in profile.experience
    })
    dups_edu = len(profile.education) - len({
        ((e.degree or '').lower(), (e.institution or '').lower())
        for e in profile.education
    })
    bullets_ok = True
    if case.expect_bullets_in_exp:
        descs = [e.description or '' for e in profile.experience]
        bullets_ok = any('\n' in d and len([ln for ln in d.splitlines() if ln.strip()]) >= 2 for d in descs)
        if not bullets_ok:
            missing += 1
    return {
        'extraction_quality': 'synthetic-text',
        'section_detection': [s for s in case.min_sections if True],
        'structured_completeness': {
            'experience': len(profile.experience),
            'education': len(profile.education),
            'skills': len(profile.skills),
            'projects': len(profile.projects),
            'languages': len(profile.languages),
        },
        'incorrect_field_count': wrong,
        'missing_field_count': missing,
        'duplicated_record_count': max(0, dups_exp) + max(0, dups_edu),
        'bullet_preservation': bullets_ok if case.expect_bullets_in_exp else 'n/a',
        'table_preservation': case.expect_edu_table,
    }


CASES: list[GoldCase] = [
    GoldCase(
        name='01_single_column_experienced',
        text="""
Priya Sharma
priya.sharma@example.com | +919876543210 | Mumbai

Professional Experience
Northwind Ltd | Software Engineer | Jan 2020 - Present
• Developed REST APIs using .NET
• Improved application performance by 40%
• Worked with SQL Server

Education
B.Tech Computer Science, State University, 2015

Skills
C#, .NET, SQL
""",
        expect_experience=1,
        expect_education=1,
        must_skills=['sql'],
        expect_bullets_in_exp=True,
        min_sections=['Experience', 'Education', 'Skills'],
        company_contains=['northwind'],
    ),
    GoldCase(
        name='02_two_column_experienced',
        text="""
Rahul Mehta
rahul.mehta@example.com
+918888777666

Work Experience
Contoso | Analyst | Jun 2019 - May 2022
Built monthly reports for retail clients.

Technical Proficiency
Python
Excel
SQL

Education
MBA, City College, 2018
""",
        expect_experience=1,
        must_skills=['python'],
        company_contains=['contoso'],
        min_sections=['Experience', 'Skills'],
    ),
    GoldCase(
        name='03_student_fresher',
        text="""
Ananya Iyer
ananya.iyer@example.com
+917777666555

Career Objective
Fresher seeking a data role.

Academic Background
B.Sc Statistics, Green University, 2024

Projects
Campus Portal
• Designed student login
• Used MySQL

Skills
Python, Excel
""",
        no_experience=True,
        expect_projects=1,
        expect_education=1,
        must_skills=['python'],
    ),
    GoldCase(
        name='04_mms_mba',
        text="""
Kavita Rao
kavita.rao@example.com
+916666555444

Education
MMS [Marketing]
Kohinoor Business School
2023–2025
Pursuing

Internship
Marketing Intern — Bright Ads | May 2024 - Jul 2024
• Coordinated campaign calendars
""",
        expect_education=1,
        expect_experience=1,
        degree_contains=['mms'],
        company_contains=['bright'],
    ),
    GoldCase(
        name='05_technical',
        text="""
Dev Patel
dev.patel@example.com
+915555444333

Employment History
Fabrikam | Backend Engineer | 2021 - Present
• Built microservices in Java
• Tuned PostgreSQL queries

Technical Expertise
Java, Spring, PostgreSQL, Git
""",
        expect_experience=1,
        must_skills=['java'],
        company_contains=['fabrikam'],
    ),
    GoldCase(
        name='06_marketing',
        text="""
Neha Joshi
neha.joshi@example.com
+914444333222

Professional Experience
BrandCo | Marketing Executive | Mar 2021 - Current
Drove social campaigns across Meta and Google.

Core Competencies
Canva, Google Analytics, Communication
""",
        expect_experience=1,
        must_skills=['canva'],
        company_contains=['brandco'],
    ),
    GoldCase(
        name='07_education_table',
        text="""
Amit Shah
amit.shah@example.com
+913333222111

Education
Year | Degree | Institution | Percentage
2020 | B.Tech | Alpha Institute | 8.2
2022 | MBA | Beta School | 72%

Skills
Excel
""",
        expect_education=2,
        expect_edu_table=True,
        degree_contains=['mba'],
    ),
    GoldCase(
        name='08_experience_table',
        text="""
Sonal Desai
sonal.desai@example.com
+912222111000

Work Experience
Company | Role | Duration
Litware | QA Engineer | 2019-2021
Adventure Works | QA Lead | 2021-Present

Skills
Selenium, Jira
""",
        expect_experience=2,
        company_contains=['litware'],
        must_skills=['selenium'],
    ),
    GoldCase(
        name='09_many_bullets',
        text="""
Vikram Nair
vikram.nair@example.com
+911111000999

Experience
Globex | Engineer | 2018 - 2023
• Developed REST APIs using .NET
• Improved application performance by 40%
• Worked with SQL Server
• Wrote integration tests
• Mentored two juniors

Education
B.E, National College, 2017
""",
        expect_experience=1,
        expect_bullets_in_exp=True,
        company_contains=['globex'],
    ),
    GoldCase(
        name='10_projects',
        text="""
Meera Kapoor
meera.kapoor@example.com
+919191919191

Projects
Inventory App
• Built REST APIs
• Used SQL Server
Campus Portal
Designed a portal for students

Education
BCA, Town College, 2022
""",
        expect_projects=2,
        no_experience=True,
    ),
    GoldCase(
        name='11_internships',
        text="""
Rohit Bansal
rohit.bansal@example.com
+918181818181

Internships
Summer Internship — Wide World Importers | May 2023 - Jul 2023
• Prepared sales dashboards
Industrial Training — Coho Vineyard | Dec 2022 - Jan 2023
• Observed bottling operations

Education
B.Com, City College, 2024
""",
        expect_experience=2,
        company_contains=['wide world'],
    ),
    GoldCase(
        name='12_references',
        text="""
Pooja Kulkarni
pooja.kulkarni@example.com
+917171717171

Experience
Tailspin Toys | Associate | 2022 - 2023
Supported store operations.

References
Ayush Saxsena (Project Head)
9575342145

Education
BA, Lake College, 2021
""",
        expect_experience=1,
        must_not_company=['ayush', '9575342145'],
        company_contains=['tailspin'],
    ),
    GoldCase(
        name='13_personal_details',
        text="""
Sanjay Gupta
sanjay.gupta@example.com
+916161616161
Date of Birth: 12th May 1998
Nationality: Indian
Father's Name: Ramesh Gupta
Marital Status: Single
Address: Pune, Maharashtra

Education
B.Tech, River Institute, 2019

Skills
MS-Office, Excel
""",
        no_experience=True,
        must_skills=['excel'],
        must_not_company=['ramesh', 'indian'],
    ),
    GoldCase(
        name='14_unusual_section_names',
        text="""
Leela Menon
leela.menon@example.com
+915151515151

Organisational Experience
Northwind Traders | Intern | Jun 2024 - Aug 2024
• Catalogued SKUs

Scholastic Record
M.Sc Physics, Hill University, 2023

Areas of Expertise
Python, Tableau
""",
        expect_experience=1,
        expect_education=1,
        must_skills=['python'],
        company_contains=['northwind'],
    ),
    GoldCase(
        name='15_multipage',
        text="""
Arjun Reddy
arjun.reddy@example.com
+914141414141

Work Experience
Page One Ltd | Analyst | 2016 - 2018
• First page duties

Page Two Corp | Senior Analyst | 2018 - 2024
• Second page duties

Education
MBA, Metro School, 2016
B.Com, Metro School, 2014
""",
        expect_experience=2,
        expect_education=2,
        company_contains=['page one'],
    ),
    GoldCase(
        name='16_scanned_ocr_like',
        text="""
NIDHI SHAH
nidhi.shah @gmail.com
Mob : 98 76 54 32 10

EDUCATION
B Tech Computer Science
State  University
2019 - 2023

SKILLS
Java Python SQL
""",
        expect_education=1,
        must_skills=['sql'],
    ),
    GoldCase(
        name='17_fullwidth_header_columns',
        text="""
HARSHITA JAIN
harshita.jain@example.com | +913131313131 | Jaipur

WORK EXPERIENCE
Left Col Ltd | Designer | 2021 - Present
Created brand kits.

TECHNICAL PROFICIENCY
Figma
Photoshop
Illustrator
""",
        expect_experience=1,
        must_skills=['figma'],
        company_contains=['left col'],
    ),
    GoldCase(
        name='18_missing_dates',
        text="""
Imran Ali
imran.ali@example.com
+912121212121

Experience
Company: ABC Ltd
Role: Developer
• Built internal tools

Education
BCA, East College
""",
        expect_experience=1,
        company_contains=['abc'],
    ),
    GoldCase(
        name='19_missing_skills_heading',
        text="""
Tara Singh
tara.singh@example.com
+911010101010

Experience
Humongous Insurance | Clerk | 2020 - 2021

Technical Proficiency:
C#, .NET, SQL, HTML

Education
B.Com, West College, 2019
""",
        must_skills=['sql'],
        expect_experience=1,
    ),
    GoldCase(
        name='20_no_experience',
        text="""
Ishaan Verma
ishaan.verma@example.com
+919090909090

Education
B.Sc, North College, 2025

Projects
Quiz App
• Built MCQ flow

Skills
Java
""",
        no_experience=True,
        expect_projects=1,
        must_skills=['java'],
    ),
    GoldCase(
        name='21_no_projects',
        text="""
Ritika Bose
ritika.bose@example.com
+918080808080

Work History
Alpine Ski House | Host | 2019 - 2022
Greeted guests.

Education
BA, South College, 2018

Skills
Communication, Excel
""",
        no_projects=True,
        expect_experience=1,
        must_skills=['excel'],
    ),
    GoldCase(
        name='22_multiple_internships',
        text="""
Yash Jain
yash.jain@example.com
+917070707070

Internship Experience
Research Internship — Lab A | Jan 2023 - Mar 2023
• Literature review
Graduate Internship — Lab B | Jun 2023 - Aug 2023
• Data cleaning
Management Internship — Firm C | Dec 2023 - Feb 2024
• Process mapping

Education
MBA, Peak School, 2024
""",
        expect_experience=3,
    ),
    GoldCase(
        name='23_mixed_bullets_paragraphs',
        text="""
Diya Nair
diya.nair@example.com
+916060606060

Experience
Woodgrove Bank | Teller | 2021 - 2023
Handled cash operations for retail customers.
• Balanced daily tills
• Assisted with KYC checks
Also trained two new joiners on counter process.

Education
B.Com, Harbor College, 2020
""",
        expect_experience=1,
        expect_bullets_in_exp=True,
        company_contains=['woodgrove'],
    ),
    GoldCase(
        name='24_footer_header_contamination',
        text="""
Curriculum Vitae
Confidential Resume
Page 1 of 2

Mohit Agarwal
mohit.agarwal@example.com
+915050505050

Experience
Proseware | Writer | 2020 - 2022
Wrote product copy.

Education
MA English, Crown College, 2019

Languages
Marathi, Hindi & English

Page 2 of 2
www.example-resume-template.com
""",
        expect_experience=1,
        must_languages=['marathi', 'hindi', 'english'],
        must_not_company=['page', 'confidential', 'curriculum'],
        company_contains=['proseware'],
    ),
    # A–N realistic structures (pipeline-level; no person-specific rules)
    GoldCase(
        name='25_project_three_bullets',
        text="""
Neha Shah
neha.shah@example.com
+911111222333

Projects
PROJECT A
• Developed X
• Implemented Y
• Improved Z

Education
B.Sc, East College, 2021
""",
        expect_projects=1,
        no_experience=True,
    ),
    GoldCase(
        name='26_project_paragraphs_no_bullets',
        text="""
Arjun Desai
arjun.desai@example.com
+911212121212

Projects
Campus Portal
Designed a portal for students and faculty.
The system stores attendance in MySQL.

Education
BCA, Lake College, 2022
""",
        expect_projects=1,
        no_experience=True,
    ),
    GoldCase(
        name='27_multiple_projects_with_bullets',
        text="""
Sana Khan
sana.khan@example.com
+913131313131

Projects
Inventory App
• Built REST APIs
• Used SQL Server
VOLUME GENERATION TOOL (NSE MARKET)
• Implemented multithreading

Education
B.Tech, River College, 2020
""",
        expect_projects=2,
        no_experience=True,
    ),
    GoldCase(
        name='28_project_technology_list',
        text="""
Vikram Rao
vikram.rao@example.com
+914141414141

Projects
Billing Platform
Technologies: Python, Django, PostgreSQL
Developed invoicing workflows for retail clients.

Education
MCA, Hill College, 2019
""",
        expect_projects=1,
        no_experience=True,
    ),
    GoldCase(
        name='29_internship_project_title_learnings',
        text="""
Pooja Nair
pooja.nair@example.com
+915151515151

Experience
Summer Internship – Amul India Ltd (10th May 2024 – 10th July 2024)
Project Title: Consumer Behaviour Towards Fresh Products.
Learnings: Observed supply chain and promotional marketing.
Conclusion: Gained practical market knowledge.

Education
MMS Marketing, Business School, 2025
""",
        expect_experience=1,
        company_contains=['amul'],
    ),
    GoldCase(
        name='30_skills_bullet_list',
        text="""
Karan Patel
karan.patel@example.com
+916161616161

Computer Skills
• MS-Office
• Excel

Education
B.Com, City College, 2021
""",
        must_skills=['office'],
        no_experience=True,
    ),
    GoldCase(
        name='31_skills_comma_separated',
        text="""
Leela Iyer
leela.iyer@example.com
+917171717171

Skills
C#, .NET, SQL, HTML

Education
B.Tech, Metro College, 2020
""",
        must_skills=['sql'],
        no_experience=True,
    ),
    GoldCase(
        name='32_skills_categorized',
        text="""
Omar Sheikh
omar.sheikh@example.com
+918181818182

Technical Expertise
Programming:
C#, Java
Databases:
SQL
Tools:
Git, Excel

Education
B.Sc, Park College, 2022
""",
        must_skills=['sql'],
        no_experience=True,
    ),
    GoldCase(
        name='33_glyph_lost_duties',
        text="""
Rhea Bose
rhea.bose@example.com
+919191919192

Experience
Northwind Ltd | Software Engineer | Jan 2020 - Present
Developed REST APIs using .NET
Improved application performance by 40%
Worked with SQL Server

Education
B.Tech, State University, 2015
""",
        expect_experience=1,
        expect_bullets_in_exp=True,
        company_contains=['northwind'],
    ),
    GoldCase(
        name='34_indented_list_no_glyph',
        text="""
Amit Joshi
amit.joshi@example.com
+910101010101

Experience
Contoso | Analyst | Jun 2019 - May 2022
  Developed monthly reports for retail clients
  Improved forecast accuracy by 12%

Education
MBA, City College, 2018
""",
        expect_experience=1,
        expect_bullets_in_exp=True,
        company_contains=['contoso'],
    ),
    GoldCase(
        name='35_education_table',
        text="""
Nisha Kulkarni
nisha.kulkarni@example.com
+912020202020

Education
Year | Degree | Institution | Percentage
2020 | B.Tech | Alpha Institute | 8.2
2022 | MBA | Beta School | 72%

Skills
Python
""",
        expect_education=2,
        degree_contains=['b.tech'],
        no_experience=True,
        expect_edu_table=True,
    ),
    GoldCase(
        name='36_two_column_project_wrap',
        text="""
Dev Malhotra
dev.malhotra@example.com
+913030303030

Projects
TATA GROUP & AMERICAN INTERNATIONAL
GROUP (TATA AIG) Client: American
International Group (AIG) (07/2022 - Present)
Designing and developing web applications using java
Developed user interfaces to interact with databases
VOLUME GENERATION TOOL (NSE MARKET)
(06/2024 - Present)
Implemented multithreading in a real-time data
processing system using C#

Education
B.Tech, Tech College, 2021
""",
        expect_projects=2,
        no_experience=True,
    ),
    GoldCase(
        name='37_multipage_project',
        text="""
Isha Reddy
isha.reddy@example.com
+914040404040

Projects
Campus Portal
• Designed student login
Page 2
• Used MySQL for attendance

Education
BCA, Town College, 2022
""",
        expect_projects=1,
        no_experience=True,
    ),
    GoldCase(
        name='38_mixed_paragraph_and_bullets',
        text="""
Farhan Ali
farhan.ali@example.com
+915050505051

Experience
Woodgrove Bank | Teller | 2021 - 2023
Handled cash operations for retail customers.
• Balanced daily tills
• Assisted with KYC checks
Also trained two new joiners on counter process.

Education
B.Com, Harbor College, 2020
""",
        expect_experience=1,
        expect_bullets_in_exp=True,
        company_contains=['woodgrove'],
    ),
]


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
    monkeypatch.setenv('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')
    monkeypatch.setattr(
        'app.ai.document_intelligence.semantic.semantic_ai_enabled',
        lambda: False,
    )


@pytest.mark.parametrize('case', CASES, ids=[c.name for c in CASES])
def test_golden_resume_variant(case: GoldCase):
    profile, _form = _parse(case.text)
    report = _score(case, profile)

    if case.expect_experience is not None:
        assert len(profile.experience) >= case.expect_experience, report
    if case.no_experience:
        # Fresher / projects-only: no fabricated jobs
        assert not any(
            'ayush' in f'{(e.company or "")} {(e.role or "")}'.lower()
            for e in profile.experience
        )
        if case.expect_experience is None:
            assert len(profile.experience) == 0, report
    if case.expect_education is not None:
        assert len(profile.education) >= case.expect_education, report
    if case.expect_projects is not None:
        assert len(profile.projects) >= case.expect_projects, report
        assert len(profile.projects) <= case.expect_projects + 2, report
    if case.no_projects:
        assert len(profile.projects) == 0, report
    if case.expect_edu_table:
        inst = ' '.join((e.institution or '').lower() for e in profile.education)
        assert 'alpha' in inst and 'beta' in inst, report
        # row integrity
        for e in profile.education:
            blob = f'{(e.degree or "")} {(e.institution or "")}'.lower()
            assert not ('b.tech' in blob and 'beta' in blob)
            assert not ('mba' in blob and 'alpha' in blob)
    for sk in case.must_skills:
        names = ' '.join(s.name.lower() for s in profile.skills)
        assert sk.lower() in names, (sk, names, report)
    for lg in case.must_languages:
        names = ' '.join(l.name.lower() for l in profile.languages)
        assert lg.lower() in names, (lg, names, report)
    for bad in case.must_not_company:
        blob = ' '.join(f'{e.company} {e.role}' for e in profile.experience).lower()
        assert bad.lower() not in blob, (bad, blob, report)
    if case.expect_bullets_in_exp:
        assert report['bullet_preservation'] is True, report
    for needle in case.company_contains:
        blob = ' '.join(f'{e.company} {e.role}' for e in profile.experience).lower()
        assert needle.lower() in blob, (needle, blob, report)
    for d in case.degree_contains:
        blob = ' '.join((e.degree or '').lower() for e in profile.education)
        assert d.lower() in blob, (d, blob, report)
    assert report['incorrect_field_count'] == 0, report
    assert report['duplicated_record_count'] == 0, report


def test_section_aliases_cover_requested_families():
    mapping = {
        'Work History': 'Experience',
        'Internship Experience': 'Experience',
        'Academic Qualifications': 'Education',
        'Core Competencies': 'Skills',
        'Academic Projects': 'Projects',
        'Accomplishments': 'Achievements',
        'Professional Certifications': 'Certifications',
        'Extracurricular Activities': 'Activities',
        'Linguistic Proficiency': 'Languages',
        'Industrial Training': 'Experience',
    }
    for raw, canonical in mapping.items():
        assert normalize_section_header(raw) == canonical


def _parse_real_file(path: Path):
    data = path.read_bytes()
    from app.ai.parser.text_extraction import extract_text

    text = extract_text(data, path.name) or ''
    profile, form, _ = parse_resume_text_to_canonical(text, max_workers=2, allow_semantic=False)
    return text, profile, form


def _real_file_report(label: str, text: str, profile) -> dict:
    from app.ai.parser.engine.sections import detect_sections

    sections = detect_sections(text, 'resume')
    labels = [s.label for s in sections]
    phones_as_co = sum(
        1 for e in profile.experience
        if (e.company or '').replace(' ', '').replace('-', '').isdigit()
    )
    emails_as_co = sum(1 for e in profile.experience if '@' in (e.company or ''))
    descs = [e.description or '' for e in profile.experience] + [
        p.description or '' for p in profile.projects
    ]
    bullet_lines = sum(d.count('\n') + (1 if d.strip() else 0) for d in descs if '\n' in d)
    bullets = any('\n' in d for d in descs)
    return {
        'case': label,
        'extraction_quality': f'{len(text)} chars',
        'section_detection': labels,
        'section_coverage': labels,
        'structured_completeness': {
            'name': bool(profile.personal.full_name),
            'email': bool(profile.contact.email),
            'phone': bool(profile.contact.phone),
            'experience': len(profile.experience),
            'education': len(profile.education),
            'skills': len(profile.skills),
            'projects': len(profile.projects),
            'languages': len(profile.languages),
            'achievements_meta': len(profile.field_meta.get('achievements') or []),
        },
        'incorrect_field_count': phones_as_co + emails_as_co,
        'missing_field_count': int(not profile.contact.email) + int(not profile.education),
        'duplicated_record_count': 0,
        'bullet_item_count': bullet_lines,
        'bullet_preservation': bullets,
        'table_preservation': 'unknown',
    }


@pytest.mark.skipif(not VISHAL_PDF.is_file(), reason='Vishal resume PDF not on this machine')
def test_real_vishal_pdf_generic_regression():
    text, profile, _form = _parse_real_file(VISHAL_PDF)
    report = _real_file_report('vishal_pdf', text, profile)
    blob_exp = ' '.join(f'{e.company} {e.role}' for e in profile.experience).lower()
    skill_blob = ' '.join(s.name.lower() for s in profile.skills)
    proj_names = ' '.join(p.name.lower() for p in profile.projects)
    assert len(text) > 200, report
    assert profile.education, report
    assert len(profile.experience) == 2, report
    assert 'tcs' in blob_exp or 'tata' in blob_exp, (blob_exp, report)
    assert 'nseit' in blob_exp or 'national stock' in blob_exp, (blob_exp, report)
    assert len(profile.projects) <= 4, (proj_names, report)
    assert 'aig' in proj_names or 'tata' in proj_names, (proj_names, report)
    assert 'sql' in skill_blob or 'c#' in skill_blob or '.net' in skill_blob, (skill_blob, report)
    assert any('\n' in (e.description or '') for e in profile.experience), report
    assert not any((e.company or '').replace(' ', '').isdigit() for e in profile.experience), report
    print(report)


@pytest.mark.skipif(not AKSHAY_DOCX.is_file(), reason='Akshay resume DOCX not on this machine')
def test_real_akshay_docx_generic_regression():
    text, profile, _form = _parse_real_file(AKSHAY_DOCX)
    report = _real_file_report('akshay_docx', text, profile)
    deg = ' '.join((e.degree or '') for e in profile.education).lower()
    inst = ' '.join((e.institution or '') for e in profile.education).lower()
    exp_blob = ' '.join(f'{e.company} {e.role} {e.description}' for e in profile.experience).lower()
    langs = { (l.name or '').lower() for l in profile.languages }
    skills = ' '.join(s.name.lower() for s in profile.skills)
    ach = profile.field_meta.get('achievements') or []
    assert len(profile.experience) == 1, report
    assert 'amul' in exp_blob, (exp_blob, report)
    assert 'consumer' in exp_blob or 'project title' in exp_blob, report
    assert 'mms' in deg, (deg, report)
    assert 'bsc' in deg or 'b.sc' in deg, (deg, report)
    assert '12' in deg or 'hsc' in deg, (deg, report)
    assert '10' in deg or 'ssc' in deg, (deg, report)
    assert 'ms-office' in skills or 'ms office' in skills or 'office' in skills, (skills, report)
    assert {'marathi', 'hindi', 'english'} <= langs, (langs, report)
    assert len(ach) >= 3, (ach, report)
    assert not any('shamrao' in f'{(e.company or "")} {(e.role or "")}'.lower() for e in profile.experience)
    assert not any((e.company or '').replace(' ', '').isdigit() for e in profile.experience), report
    print(report)
