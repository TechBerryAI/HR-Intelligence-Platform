"""Phase 4 section recovery — ownership tests, not acceptance counts.

No candidate names, employers-as-rules, coordinates, or resume-specific logic.
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

from app.ai.document_intelligence.section_recovery import recover_resume_sections  # noqa: E402
from app.ai.document_intelligence.sections import pick_section  # noqa: E402
from app.ai.parser.engine.sections import detect_sections  # noqa: E402


def _recover(text: str):
    spans = detect_sections(text, 'resume')
    recovered, report = recover_resume_sections(spans, text)
    return recovered, report, spans


def _exp(sections) -> str:
    return pick_section(sections, 'Experience', 'Work Experience').lower()


def test_case1_heading_plus_unclassified_body():
    text = (
        'Jordan Hale\njordan@example.com\n\n'
        'Experience\n'
        'Summary\n'
        'Seeking a challenging hospitality sales role with five years of experience.\n'
        'Education\nB.A. Hospitality, State University, 2019\n'
        'Skills\nCRM, Salesforce\n'
        'Northwind Traders\nAssociate (Sales and Marketing)\n'
        'November 2023 - August 2024\n'
        'Handled client acquisition for corporate accounts.\n'
        'Managed social media marketing activities.\n'
        'Contoso Hotels\nExecutive (Sales)\nJune 2025 - September 2025\n'
        'Generated banquet bookings in metro markets.\n'
    )
    recovered, report, before = _recover(text)
    assert any(s.label == 'Experience' for s in before)
    body = _exp(recovered)
    assert 'northwind' in body
    assert 'contoso' in body
    assert 'handled client' in body
    assert report.get('actions')


def test_case2_heading_plus_body_inside_summary():
    text = (
        'Alex Rivera\nalex@example.com\n\n'
        'Summary\n'
        'Results-driven analyst with a focus on reporting quality.\n'
        'A. Work Experience:\n'
        'Northwind Traders | Analyst | Jan 2021 - Mar 2024\n'
        'Built reporting dashboards for operations.\n'
        'Fabrikam Ltd | Senior Analyst | Apr 2024 - Present\n'
        'Led weekly stakeholder reviews.\n'
        'Education\nB.Sc. Statistics, State University, 2020\n'
    )
    recovered, report, _before = _recover(text)
    body = _exp(recovered)
    assert 'northwind' in body
    assert 'fabrikam' in body
    summary = pick_section(recovered, 'Summary').lower()
    assert 'northwind' not in summary
    assert 'results-driven' in summary
    assert report.get('actions')


def test_case3_heading_plus_body_inside_projects():
    text = (
        'Riley Chen\nriley@example.com\n\n'
        'Experience\n'
        'Projects\n'
        'Northwind Traders Pvt Ltd\nSoftware Engineer\nJan 2020 - Dec 2022\n'
        'Developed REST APIs for billing.\n'
        'Contoso Systems\nSenior Engineer\nJan 2023 - Present\n'
        'Implemented deployment pipelines.\n'
        'Education\nB.Tech, East College, 2019\n'
    )
    recovered, _report, _before = _recover(text)
    body = _exp(recovered)
    assert 'northwind' in body
    assert 'contoso' in body
    projects = pick_section(recovered, 'Projects').lower()
    assert 'northwind' not in projects


def test_case4_heading_plus_body_inside_certifications():
    text = (
        'Casey Morgan\ncasey@example.com\n\n'
        'Summary\n\n'
        'Experience\n\n'
        'Education\n\n'
        'Skills\n\n'
        'Certifications\n'
        'Casey Morgan\nSystem Engineer\n'
        'Northwind Traders Ltd | WebLogic Administrator | Jan 2022 - Present\n'
        'Managed production middleware for banking clients.\n'
        'Configured clusters and monitored JVM health.\n'
        'AWS Certified Cloud Practitioner\n'
    )
    recovered, _report, _before = _recover(text)
    body = _exp(recovered)
    assert 'northwind' in body
    assert 'weblogic' in body or 'middleware' in body


def test_case5_two_column_experience():
    text = (
        'Sam Patel\nsam@example.com\nMumbai\n\n'
        'Skills\nPython, SQL\n'
        'Experience\n'
        'Certifications\n'
        'Northwind Traders | Analyst | 2021 - 2024\n'
        'Built reporting dashboards.\n'
        'Fabrikam Inc | Senior Analyst | 2024 - Present\n'
        'Owned monthly forecasting.\n'
    )
    recovered, _report, before = _recover(text)
    before_body = _exp(before)
    assert 'northwind' not in before_body
    body = _exp(recovered)
    assert 'northwind' in body
    assert 'fabrikam' in body


def test_case6_compact_minimal_heading_body_separation():
    text = (
        'Avery Quinn\navery@example.com\n\n'
        'Experience\n'
        'Northwind Traders Pvt Ltd, Analyst, Jan 2021 - Present\n'
        'Developed internal reporting tools.\n'
        'Education\nMBA, State University, 2020\n'
    )
    recovered, report, before = _recover(text)
    before_body = _exp(before)
    after_body = _exp(recovered)
    assert 'northwind' in before_body
    assert 'northwind' in after_body
    assert not report.get('actions')


def test_case7_multiple_records_in_recovered_column():
    text = (
        'Drew Nash\ndrew@example.com\n\n'
        'Experience\n'
        'Summary\nProfessional with a record of delivery.\n'
        'Northwind Traders | Engineer | Jan 2018 - Dec 2019\n'
        'Built billing services.\n'
        'Fabrikam Ltd | Senior Engineer | Jan 2020 - Dec 2022\n'
        'Led platform migrations.\n'
        'Contoso Systems | Staff Engineer | Jan 2023 - Present\n'
        'Designed event pipelines.\n'
    )
    recovered, _report, _before = _recover(text)
    body = _exp(recovered)
    assert 'northwind' in body
    assert 'fabrikam' in body
    assert 'contoso' in body


def test_case8_experience_beside_another_section():
    text = (
        'Harper Cole\nharper@example.com\n\n'
        'Skills\nJava, Spring, SQL\n'
        'Experience\n'
        'Languages\n'
        'English, Hindi\n'
        'Northwind Traders Pvt Ltd\nJava Developer\nMar 2021 - Present\n'
        'Developed Spring Boot services for retail.\n'
        'Education\nB.E. Computer, State University, 2020\n'
    )
    recovered, _report, _before = _recover(text)
    body = _exp(recovered)
    assert 'northwind' in body
    skills = pick_section(recovered, 'Skills').lower()
    assert 'java' in skills or 'spring' in skills


def test_case9_ocr_interleaved_blocks():
    text = (
        'Quinn Blake\nquinn@example.com\n\n'
        'Experience\n'
        'Skills\nPython\n'
        'Unlabeled leftover follows.\n'
        'Northwind Traders Ltd\nBackend Engineer\nJan 2022 - Present\n'
        'Implemented order services.\n'
        'Python, Docker, SQL\n'
        'Education\nB.Tech, East College, 2021\n'
    )
    recovered, _report, _before = _recover(text)
    body = _exp(recovered)
    assert 'northwind' in body
    assert 'implemented order' in body


def test_case10_ambiguous_layout_does_not_recover():
    text = (
        'Casey Morgan\ncasey@example.com\n+919111222333\n'
        'Brightleaf Technologies, Pune\nJune 2020 - Present\n\n'
        'Summary\nData engineer with warehouse and pipeline work.\n'
        'Education\nB.E. Computer, State University, 2019\n'
        'Skills\nPython, SQL, Azure, MySQL\n'
    )
    recovered, report, before = _recover(text)
    assert 'Experience' not in [s.label for s in before]
    assert 'Experience' not in [s.label for s in recovered]
    unclassified = pick_section(recovered, 'Unclassified')
    assert 'Brightleaf Technologies' in unclassified
    assert not report.get('actions')


def test_recovery_report_is_explainable():
    text = (
        'Alex Rivera\nalex@example.com\n\n'
        'Experience\n'
        'Summary\nSeeking a sales role.\n'
        'Northwind Traders | Associate | Nov 2023 - Aug 2024\n'
        'Handled corporate client acquisition.\n'
    )
    recovered, report, _ = _recover(text)
    assert report.get('actions')
    action = report['actions'][0]
    assert action.get('section') == 'experience'
    assert action.get('evidence')
    assert 'section_recovery' not in _exp(recovered)


def test_kill_switch_skips_recovery(monkeypatch):
    monkeypatch.setenv('RESUME_SKIP_SECTION_RECOVERY', 'true')
    from app.ai.document_intelligence.pipeline import parse_resume_from_working_text
    from app.ai.document_intelligence.resume_preprocess import prepare_resume_working_text

    text = (
        'Alex Rivera\nalex@example.com\n\n'
        'Experience\n'
        'Summary\nSeeking a sales role with proven delivery.\n'
        'A. Work Experience:\n'
        'Northwind Traders | Associate | Nov 2023 - Aug 2024\n'
        'Handled corporate client acquisition.\n'
    )
    working = prepare_resume_working_text(text)
    profile, *_rest = parse_resume_from_working_text(
        working, allow_semantic=False, source_filename='recovery-skip.txt',
    )
    assert 'section_recovery' not in (profile.field_meta or {})
