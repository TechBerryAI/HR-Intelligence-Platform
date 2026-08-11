"""Golden regression tests for resume parsing + coverage (JD-parity Phase 5)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical
from app.ai.parser.enrichment.resume_text_inference import is_plausible_location_value
from app.workers.bulk_parser import _apply_coverage_parse_honesty, _coverage_gaps_from_form

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'resume_gold'


@pytest.fixture(autouse=True)
def _force_offline(monkeypatch):
    monkeypatch.setenv('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
    monkeypatch.setenv('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')
    monkeypatch.setattr(
        'app.ai.document_intelligence.semantic.semantic_ai_enabled',
        lambda: False,
    )
    monkeypatch.setattr('app.ai.document_intelligence.semantic._ENABLED', False)


def _parse(name: str):
    text = (FIXTURES / name).read_text(encoding='utf-8')
    profile, form, toon = parse_resume_text_to_canonical(text, max_workers=2)
    return text, profile, form, toon


def test_form_dto_includes_coverage():
    _text, profile, form, _toon = _parse('labeled_contact_mumbai.txt')
    assert isinstance(form.coverage, list)
    assert form.coverage
    fields = {c.get('field') for c in form.coverage if isinstance(c, dict)}
    assert {'email', 'phone', 'location', 'education', 'experience'} <= fields
    autofill = form.to_autofill_dict()
    assert isinstance(autofill.get('coverage'), list)


def test_labeled_contact_and_location():
    _text, profile, form, _toon = _parse('labeled_contact_mumbai.txt')
    assert 'priya' in (form.fullName or '').lower() or 'priya' in (
        profile.personal.full_name or ''
    ).lower()
    assert 'priya.sharma@example.com' in (form.email or '').lower()
    assert form.phone
    loc = (form.currentLocation or '').lower()
    assert 'mumbai' in loc
    assert is_plausible_location_value(form.currentLocation)
    assert any((e.degree or '').strip() and (e.institution or '').strip() for e in profile.education)
    assert len(profile.experience) >= 1


def test_internship_section_yields_experience():
    _text, profile, form, _toon = _parse('internship_section_pune.txt')
    assert len(form.experiences) >= 1 or len(profile.experience) >= 1
    joined = ' '.join(
        f'{e.role} {e.company}' for e in (form.experiences or [])
    ).lower()
    assert 'intern' in joined or 'valuedx' in joined or any(
        'intern' in (e.role or '').lower() or 'valuedx' in (e.company or '').lower()
        for e in profile.experience
    )


def test_company_city_pipe_and_em_dash():
    _t, p1, f1, _ = _parse('company_city_pipe_thane.txt')
    assert len(p1.experience) >= 1
    loc = (f1.currentLocation or '').lower()
    assert 'thane' in loc or is_plausible_location_value(f1.currentLocation)

    _t2, p2, f2, _ = _parse('em_dash_intern.txt')
    assert len(p2.experience) >= 1
    roles = ' '.join(e.role for e in p2.experience).lower()
    cos = ' '.join(e.company for e in p2.experience).lower()
    assert 'intern' in roles or 'edviron' in cos


def test_date_first_and_pipe_header_location():
    _t, p1, f1, _ = _parse('date_first_remote.txt')
    assert len(p1.experience) >= 1
    assert 'hyderabad' in (f1.currentLocation or '').lower()

    _t2, _p2, f2, _ = _parse('pipe_header_location.txt')
    loc = (f2.currentLocation or '').lower()
    assert 'thane' in loc or 'mumbai' in loc


def test_location_not_skill_pollution():
    _t, _p, form, _ = _parse('location_not_skills.txt')
    loc = (form.currentLocation or '').lower()
    assert 'html' not in loc
    assert 'typescript' not in loc
    assert is_plausible_location_value(form.currentLocation) or 'bangalore' in loc


def test_fresher_without_experience_section_no_invented_jobs():
    _t, profile, form, _ = _parse('fresher_no_experience_section.txt')
    assert profile.education
    # No Experience section → should not invent jobs
    assert not profile.experience or all(
        not (e.role or e.company) for e in profile.experience
    )
    statuses = {
        c.get('field'): c.get('status')
        for c in (form.coverage or [])
        if isinstance(c, dict)
    }
    assert statuses.get('experience') in (
        'missing_no_evidence',
        'filled',
        'recovered',
        None,
    )


def test_navi_mumbai_address_location():
    _t, _p, form, _ = _parse('address_navi_mumbai.txt')
    loc = (form.currentLocation or '').lower()
    assert 'mumbai' in loc or 'navi' in loc


def test_bulk_coverage_honesty_helper():
    class _FakeForm:
        coverage = [
            {'field': 'email', 'status': 'filled'},
            {'field': 'experience', 'status': 'missing_with_evidence'},
            {'field': 'education', 'status': 'missing_with_evidence'},
        ]

    assert _coverage_gaps_from_form(_FakeForm()) == ['experience', 'education']
    row = {'ParseStatus': 'ok', 'ParseNotes': ''}
    status = _apply_coverage_parse_honesty(
        row,
        _FakeForm(),
        parse_status='ok',
        note_bits=['source=engine:deterministic'],
    )
    assert status == 'partial'
    assert row['ParseStatus'] == 'partial'
    assert 'coverage_gaps=' in row['ParseNotes']
    assert 'experience' in row['ParseNotes']
