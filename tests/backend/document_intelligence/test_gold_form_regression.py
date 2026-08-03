"""Gold-lake regression: expected Form DTO vs Document Intelligence mapper."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ai.document_intelligence.canonical.from_toon import (
    candidate_profile_from_toon,
    job_profile_from_toon,
)
from app.ai.document_intelligence.mapping.jd_form import map_job_to_form
from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form

LAKE = ROOT / 'ai' / 'dataset' / 'lake' / 'benchmark' / 'parsing' / 'v1'


def _resume_cases():
    base = LAKE / 'resumes'
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / 'expected_toon.json').exists())


def _jd_cases():
    base = LAKE / 'jds'
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / 'expected_toon.json').exists())


@pytest.mark.parametrize('case_dir', _resume_cases()[:20], ids=lambda p: p.name)
def test_gold_resume_form_fields(case_dir: Path):
    toon = json.loads((case_dir / 'expected_toon.json').read_text(encoding='utf-8'))
    form = map_candidate_to_form(candidate_profile_from_toon(toon))
    expected_path = case_dir / 'expected_form.json'
    if not expected_path.exists():
        pytest.skip('no expected_form.json')
    expected = json.loads(expected_path.read_text(encoding='utf-8'))
    for key, value in expected.items():
        if key.startswith('_'):
            continue
        actual = getattr(form, key, None)
        if actual is None and key in form.model_dump():
            actual = form.model_dump()[key]
        assert actual == value, f'{case_dir.name}.{key}: expected {value!r}, got {actual!r}'


@pytest.mark.parametrize('case_dir', _jd_cases()[:20], ids=lambda p: p.name)
def test_gold_jd_form_fields(case_dir: Path):
    toon = json.loads((case_dir / 'expected_toon.json').read_text(encoding='utf-8'))
    form = map_job_to_form(job_profile_from_toon(toon))
    expected_path = case_dir / 'expected_form.json'
    if not expected_path.exists():
        pytest.skip('no expected_form.json')
    expected = json.loads(expected_path.read_text(encoding='utf-8'))
    for key, value in expected.items():
        if key.startswith('_'):
            continue
        actual = getattr(form, key, None)
        if isinstance(value, list) and actual is not None:
            assert list(actual) == list(value), f'{case_dir.name}.{key}'
        else:
            assert actual == value, f'{case_dir.name}.{key}: expected {value!r}, got {actual!r}'
