"""Phase 7 — candidate Location layout goldens (synthetic; no corpus PII)."""
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

from app.ai.document_intelligence.deterministic import extract_simple_location  # noqa: E402
from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical  # noqa: E402
from app.ai.parser.enrichment.resume_text_inference import (  # noqa: E402
    peel_place_from_candidate_address,
)


def _form_location(text: str) -> str:
    _profile, form, *_ = parse_resume_text_to_canonical(
        text, allow_semantic=False, source_filename='synthetic.txt'
    )
    if isinstance(form, dict):
        return (form.get('currentLocation') or '').strip()
    return (getattr(form, 'currentLocation', '') or '').strip()


def test_peel_dist_city_state_pin():
    out = peel_place_from_candidate_address(
        'Permanent Address: At.Post. Sample Tal. Example Dist. Riverdale, '
        'Maharashtra, 425108'
    )
    assert 'riverdale' in out.lower()
    assert 'maharashtra' in out.lower()


def test_peel_city_dash_state():
    out = peel_place_from_candidate_address('Lakeside – Kerala')
    assert 'lakeside' in out.lower()
    assert 'kerala' in out.lower()


def test_peel_street_with_known_city():
    out = peel_place_from_candidate_address(
        'Harbor Cross Road,Mumbai No : 31'
    )
    assert out.lower() == 'mumbai'


def test_permanent_address_labeled_line():
    text = (
        'Candidate Name\n'
        'Email: person@example.com\n'
        'Contact No: +91-9000000000\n'
        'OBJECTIVE :- Seek a role.\n'
        'Experience\n'
        'Engineer at ACME from 2020.\n'
        'Permanent Address: At.Post. Hingone Tal. Chopda Dist. Riverdale, '
        'Maharashtra, 425108\n'
    )
    loc = extract_simple_location(text)
    assert 'riverdale' in loc.lower()
    assert 'maharashtra' in loc.lower()
    form_loc = _form_location(text)
    assert 'riverdale' in form_loc.lower() or 'maharashtra' in form_loc.lower()


def test_contact_pipe_trailing_city_state():
    text = (
        'ASWIN CANDIDATE\n'
        'person@example.com | LinkedIn | +91 7902670228 | Lakeside – Kerala\n'
        'CAREER OBJECTIVE:\n'
        'Network engineer seeking a role.\n'
        'Experience\n'
        'Network Engineering Analyst | June 2023 – Present | Bengaluru Karnataka\n'
    )
    loc = extract_simple_location(text)
    assert 'lakeside' in loc.lower()
    assert 'kerala' in loc.lower()
    # Must prefer header place over job Bengaluru
    assert 'bengaluru' not in loc.lower()
    assert 'bangalore' not in loc.lower()
    form_loc = _form_location(text)
    assert 'lakeside' in form_loc.lower()
    assert 'bengaluru' not in form_loc.lower()


def test_street_address_near_contact():
    text = (
        'CAREER OBJECTIVE\n'
        'Harbor Cross Road,Mumbai No : 31\n'
        'person@example.com\n'
        '9000000000\n'
        'CANDIDATE NAME\n'
        'Service Desk Engineer\n'
        'Experience\n'
        'Working as Service Desk Engineer.\n'
    )
    loc = extract_simple_location(text)
    assert loc.lower() == 'mumbai'
    form_loc = _form_location(text)
    assert 'mumbai' in form_loc.lower()


def test_employer_city_alone_does_not_populate():
    text = (
        'Candidate Name\n'
        'a@b.com\n'
        '+91 9000000000\n'
        'Experience\n'
        'Working at Techarray Software Solutions Private Limited — Mumbai '
        'from Sep 2019 to till date.\n'
        'Installation on Local System and Remote System.\n'
    )
    loc = extract_simple_location(text)
    # May be empty; must not be Mumbai from employer line alone via labeled path.
    # extract_location_from_text historically may still find bare cities in early body —
    # form path should stay blank when only employer evidence exists after coverage hygiene.
    form_loc = _form_location(text)
    assert form_loc == '' or 'mumbai' not in form_loc.lower() or loc == ''
    # Stronger: if no candidate-owned cues, prefer blank
    assert form_loc == ''
