"""Unit tests for Apply public eval scoring — no live backend, no parser changes."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.eval.apply_public_eval.sample import select_diverse
from ai.eval.apply_public_eval.score import (
    CLASS_A,
    CLASS_B,
    CLASS_C,
    CLASS_D,
    aggregate,
    evaluate_case,
    source_support,
)


def test_source_support_does_not_require_missing_company():
    text = (
        'Jordan Hale\nEmail: jordan@example.com\n'
        'Experience\nEngineer\nJan 2022 - Present\n'
        'Education\nB.E.\nExample University\n2018\n'
        'Skills\nPython\n'
    )
    s = source_support(text)
    assert s['role'] and s['dates'] and s['degree'] and s['institution']
    assert s['skills']


def test_missing_company_without_cue_is_source_ambiguity():
    extract = (
        'Jordan Hale\nEmail: jordan@example.com\n'
        'Experience\nMiddleware Administrator\nJuly 2022 to till date\n'
        'Education\nExample University\n'
    )
    form = {
        'fullName': 'Jordan Hale',
        'experiences': [{
            'company': '',
            'role': 'Middleware Administrator',
            'startMonth': '2022-07',
            'endMonth': '',
            'isCurrent': True,
        }],
        'education': [{'degree': '', 'institution': 'Example University', 'startMonth': '', 'endMonth': ''}],
        'skills': '',
        'summary': '',
    }
    ev = evaluate_case(form=form, extract=extract, http_status=200, inproc_form=form)
    assert ev['acceptable']
    assert any(i['class'] == CLASS_C and i['field'] == 'company' for i in ev['issues'])
    assert ev['fields']['company'] == 'n/a'


def test_job_cues_without_rows_is_parser_failure():
    extract = (
        'Jordan Hale\nEmail: jordan@example.com\n'
        'Experience\nAcme Technologies Pvt Ltd\nSoftware Engineer\nJan 2020 - Present\n'
        'Skills\nPython\n'
    )
    form = {'fullName': 'Jordan Hale', 'experiences': [], 'education': [], 'skills': 'Python', 'summary': ''}
    ev = evaluate_case(form=form, extract=extract, http_status=200, inproc_form=form)
    assert not ev['acceptable']
    assert any(i['class'] == CLASS_B and i['field'] == 'experience' for i in ev['issues'])


def test_prose_in_skills_is_parser_failure():
    extract = 'Jordan Hale\nEmail: jordan@example.com\nSkills\nPython\n'
    form = {
        'fullName': 'Jordan Hale',
        'experiences': [],
        'education': [],
        'skills': 'Python, Project Description: I am responsible for databases',
        'summary': '',
    }
    ev = evaluate_case(form=form, extract=extract, http_status=200, inproc_form=form)
    assert not ev['acceptable']
    assert any(i['class'] == CLASS_B and i['field'] == 'skills' for i in ev['issues'])


def test_short_extract_is_layout_not_parser():
    form = {'fullName': '', 'experiences': [], 'education': [], 'skills': '', 'summary': ''}
    ev = evaluate_case(form=form, extract='??', http_status=200, extract_short=True)
    assert CLASS_A in ev['classes']
    assert CLASS_B not in ev['classes']


def test_short_extract_mismatch_is_layout_not_api():
    http = {
        'fullName': 'Alex Person',
        'experiences': [],
        'education': [],
        'skills': '',
        'summary': '',
    }
    inproc = {'fullName': '', 'experiences': [], 'education': [], 'skills': '', 'summary': ''}
    ev = evaluate_case(
        form=http,
        extract='??',
        http_status=200,
        inproc_form=inproc,
        extract_short=True,
    )
    assert CLASS_A in ev['classes']
    assert CLASS_D not in ev['classes']


def test_http_mismatch_is_api_class():
    extract = 'Jordan Hale\nEmail: jordan@example.com\nSkills\nPython\n'
    http = {'fullName': 'Jordan Hale', 'experiences': [], 'education': [], 'skills': 'Python', 'summary': ''}
    inproc = {'fullName': 'Other Name', 'experiences': [], 'education': [], 'skills': 'Python', 'summary': ''}
    ev = evaluate_case(form=http, extract=extract, http_status=200, inproc_form=inproc)
    assert not ev['acceptable']
    assert any(i['class'] == CLASS_D for i in ev['issues'])


def test_reference_compare_and_aggregate():
    extract = (
        'Jordan Hale\nEmail: jordan@example.com\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\nSkills\nPython\n'
    )
    form = {
        'fullName': 'Jordan Hale',
        'experiences': [{
            'company': 'Northwind Ltd',
            'role': 'Engineer',
            'startMonth': '2022-01',
            'endMonth': '',
            'isCurrent': True,
        }],
        'education': [],
        'skills': 'Python',
        'summary': '',
    }
    ref = {
        'fullName': 'Jordan Hale',
        'experiences': [{
            'company': 'Northwind Ltd',
            'role': 'Engineer',
            'startMonth': '2022-01',
            'endMonth': 'Present',
            'isCurrent': True,
        }],
        'education': [],
        'skills': 'Python',
        'summary': '',
    }
    ev = evaluate_case(form=form, extract=extract, http_status=200, inproc_form=form, reference=ref)
    assert ev['acceptable']
    assert ev['had_reference']
    agg = aggregate([{'file': 'a.pdf', 'evaluation': ev}])
    assert agg['total'] == 1
    assert agg['acceptable'] == 1


def test_select_diverse_bounds(tmp_path):
    files = []
    for i in range(8):
        p = tmp_path / f'res_{i}.pdf'
        p.write_bytes(b'%PDF')
        files.append(p)
    for i in range(8):
        p = tmp_path / f'doc_{i}.docx'
        p.write_bytes(b'PK')
        files.append(p)
    picked = select_diverse(files, n=16)
    assert 10 <= len(picked) <= 16
    assert any(p.suffix == '.pdf' for p in picked)
    assert any(p.suffix == '.docx' for p in picked)
