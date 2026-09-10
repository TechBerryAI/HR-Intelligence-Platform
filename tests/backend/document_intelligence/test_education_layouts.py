"""Generalized education layouts for Apply parse. Synthetic only — no corpus PII."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
ROOT = Path(__file__).resolve().parents[3]
for p in (BACKEND, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.parsers.resume import (  # noqa: E402
    parse_education,
    split_education_oneliner,
)
from app.ai.parser.layout.heuristic import normalize_section_header  # noqa: E402
from ai.eval.apply_public_eval.score import _DEGREE_CUE  # noqa: E402


def _hit(rows, *, degree=None, institution=None):
    assert rows, 'expected at least one education row'
    if degree:
        found = next(
            (r for r in rows if degree.lower() in (r.degree or '').lower()),
            None,
        )
        if found:
            return found
    if institution:
        found = next(
            (r for r in rows if institution.lower() in (r.institution or '').lower()),
            None,
        )
        if found:
            return found
    return rows[0]


def test_hyphenated_btech_from_institution_year():
    deg, inst, _gpa, year = split_education_oneliner('B-Tech from JNTU Anatapur-2017.')
    assert deg.lower().startswith('b')
    assert 'tech' in deg.lower()
    assert 'jntu' in inst.lower()
    assert year == '2017'
    rows = parse_education('Education\n• B-Tech from JNTU Anatapur-2017.\n', '')
    hit = _hit(rows, degree='tech', institution='jntu')
    assert 'tech' in (hit.degree or '').lower()
    assert 'jntu' in (hit.institution or '').lower()
    assert (hit.end or '') == '2017'


def test_spaced_b_tech_from_long_university():
    deg, inst, _gpa, year = split_education_oneliner(
        'B. Tech from Jawaharlal Nehru Technological University, Kakinada Andhra Pradhesh.'
    )
    assert 'tech' in deg.lower()
    assert 'nehru' in inst.lower()
    assert not inst.lower().startswith('from')


def test_column_padded_year_then_btech_from():
    deg, inst, _gpa, year = split_education_oneliner(
        '2018                                       B. Tech. from JNTU Hyderabad'
    )
    assert 'tech' in deg.lower()
    assert not deg.strip()[:4].isdigit()
    assert 'jntu' in inst.lower()
    assert year == '2018'


def test_completed_degree_from_institution_prose():
    rows = parse_education(
        'Academic Profile\n'
        'Completed Master in Engineering (Electrical) In 2022 from BATU, Lonare\n'
        'Completed Bachelor of Engineering (Electrical) in 2017 from Shivaji University,Kolhapur\n',
        '',
    )
    assert len(rows) >= 2
    master = _hit(rows, degree='master')
    assert 'batu' in (master.institution or '').lower()
    assert (master.end or '') == '2022'
    bach = _hit(rows, degree='bachelor')
    assert 'shivaji' in (bach.institution or '').lower()
    assert (bach.end or '') == '2017'


def test_professional_qualification_labeled_line():
    rows = parse_education(
        'Professional Qualification:- Completed Bachelor of Engineering '
        '(Electronics and Telecommunication) from Viva institute of Technology.\n',
        '',
    )
    hit = _hit(rows, degree='bachelor', institution='viva')
    assert 'bachelor' in (hit.degree or '').lower()
    assert 'viva' in (hit.institution or '').lower()


def test_spaced_ocr_btech_and_year():
    rows = parse_education(
        'Education\n'
        'B T E C H\n'
        'ADAMAS UNIVERSITY,\n'
        'KOLKATA\n'
        '2 0 2 1\n'
        '• Major: Computer Science\n'
        'and Engineering\n',
        '',
    )
    hit = _hit(rows, degree='tech', institution='adamas')
    assert 'tech' in (hit.degree or '').lower()
    assert 'adamas' in (hit.institution or '').lower()
    assert (hit.end or '') == '2021'


def test_pre_heading_bachelor_recovered_via_unlabeled():
    full = (
        'BACHELOR IN COMMERCE\n'
        '(ACCOUNTING HONOURS)\n'
        'Sashi Bhusan Rath Government\n'
        "Autonomous Women's College ,\n"
        'Odisha\n'
        'Education\n'
        'AL HISTORY\n'
        'Automation & Scripting: Cron Jobs\n'
    )
    rows = parse_education('AL HISTORY\nAutomation & Scripting: Cron Jobs\n', full)
    hit = _hit(rows, degree='bachelor', institution='college')
    assert 'bachelor' in (hit.degree or '').lower()
    assert 'college' in (hit.institution or '').lower() or 'sashi' in (hit.institution or '').lower()


def test_academic_profile_header_alias():
    assert normalize_section_header('Academic Profile') == 'Education'
    assert normalize_section_header('Professional Qualification') == 'Education'


def test_degree_cue_ignores_prose_me_be():
    assert not _DEGREE_CUE.search('drives me to continuously improve')
    assert not _DEGREE_CUE.search('provided me with hands-on experience')
    assert _DEGREE_CUE.search('Bachelor of Engineering')
    assert _DEGREE_CUE.search('B.E. in CSE')
    assert _DEGREE_CUE.search('B-Tech from JNTU')
