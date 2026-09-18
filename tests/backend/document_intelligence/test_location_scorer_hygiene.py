"""Phase 7 — Location scorer hygiene goldens (synthetic; no corpus PII)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'apps' / 'backend'
for p in (BACKEND, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ai.eval.apply_public_eval.score import (  # noqa: E402
    evaluate_case,
    extract_has_candidate_location_evidence,
    source_support,
)


def test_server_remote_utilities_is_not_location_evidence():
    text = (
        'Skills\n'
        'Server Remote Utilities: iDrac, iLO\n'
        'Networking Skills: VLAN\n'
    )
    assert extract_has_candidate_location_evidence(text) is False
    assert source_support(text)['location'] is False


def test_employer_city_is_not_location_evidence():
    text = (
        'Experience\n'
        'Working at Techarray Software Solutions Private Limited — Mumbai '
        'from Sep 2019 to till date.\n'
    )
    assert extract_has_candidate_location_evidence(text) is False


def test_job_from_city_is_not_location_evidence():
    text = 'Worked for Infosys from Bengaluru, 5-Feb-2018 to 9-Nov-2021.\n'
    assert extract_has_candidate_location_evidence(text) is False


def test_employer_title_city_is_not_location_evidence():
    text = 'Database Administrator, TCS Mumbai (ORACLE Certified Associate)\n'
    assert extract_has_candidate_location_evidence(text) is False


def test_education_city_is_not_location_evidence():
    text = 'B.Tech from radical institute Pune\nLinux, CCNA from Nagpur\n'
    assert extract_has_candidate_location_evidence(text) is False


def test_org_underscore_city_is_not_location_evidence():
    text = 'Organization: TJSB Bank _ Mumbai\nChief Information Security Officer\n'
    assert extract_has_candidate_location_evidence(text) is False


def test_hubs_zone_duty_city_is_not_location_evidence():
    text = 'Handling Recruitment for SVC, Hubs Mumbai zone.\n'
    assert extract_has_candidate_location_evidence(text) is False


def test_empty_location_with_job_city_only_is_na():
    text = (
        'Candidate Name\nEmail: a@b.com\nPhone: 9000000000\n'
        'Experience\nWorking at ACME Technologies, Hyderabad from Sep 2021.\n'
        'Responsible for server administration and monitoring.\n'
    )
    ev = evaluate_case(form={'currentLocation': ''}, extract=text, http_status=200)
    assert ev['fields']['location'] == 'n/a'


def test_labeled_permanent_address_is_evidence():
    text = (
        'Permanent Address: At.Post. Sample Tal. Example Dist. SampleCity, '
        'Maharashtra, 425108\n'
    )
    assert extract_has_candidate_location_evidence(text) is True


def test_contact_pipe_city_state_is_evidence():
    text = 'candidate@example.com | LinkedIn | +91 9000000000 | SampleTown – Kerala\n'
    assert extract_has_candidate_location_evidence(text) is True


def test_street_address_header_is_evidence():
    text = 'Sample Cross Road, ExampleCity No : 31\ncandidate@example.com\n'
    assert extract_has_candidate_location_evidence(text) is True


def test_empty_with_labeled_address_is_fail():
    text = (
        'Candidate Name\nEmail: a@b.com\nPhone: 9000000000\n'
        'Location: Pune, Maharashtra\n'
        'Summary\nExperienced engineer seeking a challenging role.\n'
    )
    ev = evaluate_case(form={'currentLocation': ''}, extract=text, http_status=200)
    assert ev['fields']['location'] == 'fail'
    assert any(
        i.get('reason') == 'location_supported_but_empty'
        for i in (ev.get('issues') or [])
    )


def test_populated_labeled_location_passes_when_grounded():
    text = (
        'Candidate Name\nEmail: a@b.com\nPhone: 9000000000\n'
        'Location: Pune, Maharashtra\n'
        'Summary\nExperienced engineer seeking a challenging role.\n'
    )
    ev = evaluate_case(
        form={'currentLocation': 'Pune, Maharashtra'},
        extract=text,
        http_status=200,
    )
    assert ev['fields']['location'] == 'pass'


def test_empty_place_label_is_not_evidence():
    text = (
        'Candidate Name\nEmail: a@b.com\n'
        'Declaration\nI hereby declare the above is true.\nDate:\nPlace:\n'
    )
    assert extract_has_candidate_location_evidence(text) is False


def test_dist_hyphen_city_state_paren():
    from app.ai.parser.enrichment.resume_text_inference import peel_place_from_candidate_address

    out = peel_place_from_candidate_address('Post-Sample, Dist.-SampleDistrict (U.P.)')
    assert 'sampledistrict' in out.lower()
    assert 'uttar' in out.lower() or 'pradesh' in out.lower()
