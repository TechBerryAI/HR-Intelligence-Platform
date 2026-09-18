"""The apply path end to end on a real resume, without a database.

Mirrors the public apply flow in apps/backend/app/domains/recruitment/api/jobs.py:

    extract -> parse -> map_candidate_to_form        (what the Apply screen shows)
            -> candidate_to_toon -> toon_dumps       (what store_parsed_resume writes)
            -> toon_loads_flex                       (what apply reads back)
            -> apply_form_to_resume_toon             (score the submitted form)
            -> _internal_match                       (the ATS score)

Only HTTP and persistence are left out; the dumps/loads round trip stands in for
the `parsed_resumes.toon` column exactly.

The corpus holds real candidate documents and is git-ignored, so these skip
wherever it is not present (CI, a fresh clone).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

CORPUS = (
    Path(__file__).resolve().parents[3]
    / 'ai' / 'dataset' / 'lake' / 'benchmark' / 'resume_gold' / 'v1' / 'cases'
)

pytestmark = pytest.mark.skipif(
    not CORPUS.is_dir() or not any(CORPUS.iterdir()),
    reason='real-resume corpus not present (git-ignored)',
)

JD = {
    'type': 'job_description',
    'title': 'Senior Python Developer',
    'location': 'Remote',
    'mandatory_skills': ['Python', 'Django', 'PostgreSQL'],
    'preferred_skills': ['AWS'],
    'qualifications': ['Bachelor degree in Computer Science'],
    'min_experience_years': 3,
}


def _first_parsable_case():
    """The first corpus case that yields enough text, with its parsed profile."""
    from app.ai.document_intelligence.pipeline import parse_resume_from_working_text
    from app.ai.document_intelligence.resume_preprocess import prepare_resume_working_text
    from app.ai.parser.text_extraction import extract_document

    for case in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        src = next(
            (p for p in sorted(case.glob('source.*')) if p.suffix.lower() != '.txt'), None
        )
        if src is None or src.suffix.lower() == '.doc':  # .doc needs antiword
            continue
        try:
            raw = extract_document(src.read_bytes(), src.name)
            text = (raw.text or '').replace('\x00', '')
            if len(text.strip()) < 30:
                continue
            working = prepare_resume_working_text(text, file_data=src.read_bytes())
            profile, coverage, _s, _l, _t = parse_resume_from_working_text(
                working, allow_semantic=False, source_filename=src.name
            )
        except Exception:
            continue
        return case, profile, coverage
    pytest.skip('no parsable case in corpus')


@pytest.fixture(scope='module')
def parsed():
    return _first_parsable_case()


def test_stored_toon_survives_the_database_round_trip(parsed):
    from app.ai.document_intelligence.serialize.toon import candidate_to_toon
    from app.ai.toon.runtime import toon_dumps, toon_loads_flex

    _case, profile, _coverage = parsed
    original = candidate_to_toon(profile)
    assert toon_loads_flex(toon_dumps(original)) == original


def test_submitting_the_autofilled_form_unchanged_does_not_move_the_score(parsed):
    """The overlay must be a no-op when the candidate edits nothing."""
    from app.ai.document_intelligence.mapping.resume_form import (
        apply_form_to_resume_toon,
        map_candidate_to_form,
    )
    from app.ai.document_intelligence.serialize.toon import candidate_to_toon
    from app.ai.toon.runtime import toon_dumps, toon_loads_flex
    from app.domains.recruitment.services.ats_service import _internal_match

    _case, profile, coverage = parsed
    autofill = map_candidate_to_form(profile, coverage=coverage.as_dicts()).to_autofill_dict()
    autofill.pop('trace', None)
    autofill.pop('coverage', None)

    stored = toon_loads_flex(toon_dumps(candidate_to_toon(profile)))
    before = _internal_match(stored, JD, skip_narrative=True)
    after = _internal_match(
        apply_form_to_resume_toon(stored, dict(autofill)), JD, skip_narrative=True
    )
    assert after['overall_match_score'] == before['overall_match_score']


def test_a_correction_on_the_apply_screen_reaches_the_ats(parsed):
    """The PR #138 case: skills fixed on the form must change the match."""
    from app.ai.document_intelligence.mapping.resume_form import (
        apply_form_to_resume_toon,
        map_candidate_to_form,
    )
    from app.ai.document_intelligence.serialize.toon import candidate_to_toon
    from app.ai.toon.runtime import toon_dumps, toon_loads_flex
    from app.domains.recruitment.services.ats_service import _internal_match

    _case, profile, coverage = parsed
    autofill = map_candidate_to_form(profile, coverage=coverage.as_dicts()).to_autofill_dict()
    autofill.pop('trace', None)
    autofill.pop('coverage', None)

    stored = toon_loads_flex(toon_dumps(candidate_to_toon(profile)))
    before = _internal_match(stored, JD, skip_narrative=True)

    corrected = dict(autofill, _skills=list(JD['mandatory_skills']))
    after = _internal_match(
        apply_form_to_resume_toon(stored, corrected), JD, skip_narrative=True
    )

    assert after['mandatory_skills_match_pct'] == 100.0
    assert after['overall_match_score'] > before['overall_match_score']
