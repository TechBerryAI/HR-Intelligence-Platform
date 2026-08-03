"""E2E gold: parse source.txt → compare Form DTO field-by-field (+ anti-contamination)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ai.document_intelligence.pipeline import (  # noqa: E402
    parse_jd_text_to_canonical,
    parse_resume_text_to_canonical,
)
from app.ai.document_intelligence.validation.engine import (  # noqa: E402
    validate_institution,
    validate_person_name,
    validate_skill_item,
)

LAKE = ROOT / 'ai' / 'dataset' / 'lake' / 'benchmark' / 'parsing' / 'v1'


def _resume_cases():
    base = LAKE / 'resumes'
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / 'source.txt').exists())


def _jd_cases():
    base = LAKE / 'jds'
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / 'source.txt').exists())


def _norm(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v]
    return str(v).strip() if v is not None else ''


@pytest.mark.parametrize('case_dir', _resume_cases()[:20], ids=lambda p: p.name)
def test_e2e_resume_form_fields(case_dir: Path):
    text = (case_dir / 'source.txt').read_text(encoding='utf-8')
    expected = json.loads((case_dir / 'expected_form.json').read_text(encoding='utf-8'))
    _profile, form, _toon = parse_resume_text_to_canonical(text)
    actual = form.to_autofill_dict()
    for key, value in expected.items():
        if key.startswith('_') or key == 'trace':
            continue
        got = actual.get(key)
        if isinstance(value, list):
            assert _norm(got) == _norm(value), f'{case_dir.name}.{key}'
        else:
            assert _norm(got) == _norm(value), (
                f'{case_dir.name}.{key}: expected {value!r}, got {got!r}'
            )


@pytest.mark.parametrize('case_dir', _jd_cases()[:20], ids=lambda p: p.name)
def test_e2e_jd_form_fields(case_dir: Path):
    text = (case_dir / 'source.txt').read_text(encoding='utf-8')
    expected = json.loads((case_dir / 'expected_form.json').read_text(encoding='utf-8'))
    _profile, form, _toon = parse_jd_text_to_canonical(text)
    actual = form.to_autofill_dict()
    for key, value in expected.items():
        if key.startswith('_') or key == 'trace':
            continue
        got = actual.get(key)
        if isinstance(value, list):
            assert list(got or []) == list(value), f'{case_dir.name}.{key}'
        else:
            assert _norm(got) == _norm(value), (
                f'{case_dir.name}.{key}: expected {value!r}, got {got!r}'
            )


@pytest.mark.parametrize('case_dir', _resume_cases()[:10], ids=lambda p: p.name)
def test_anti_contamination_resume(case_dir: Path):
    text = (case_dir / 'source.txt').read_text(encoding='utf-8')
    profile, form, _ = parse_resume_text_to_canonical(text)
    ok, _ = validate_person_name(profile.personal.full_name)
    assert ok or not profile.personal.full_name
    for sk in profile.skills:
        sok, reason = validate_skill_item(sk.name or sk.canonical)
        assert sok, f'skill contaminated: {sk.name!r} ({reason})'
    for edu in profile.education:
        if edu.institution:
            iok, reason = validate_institution(edu.institution)
            assert iok, f'institution contaminated: {edu.institution!r} ({reason})'
    for exp in form.experiences:
        if exp.company and exp.role:
            assert exp.company.lower() != exp.role.lower()
