"""Unit tests for the benchmark's own comparators.

These guard the measuring instrument. A scorer that silently changes meaning
makes every historical number incomparable, so treat a failure here as a
benchmark-integrity bug, not a parser bug.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from resume_benchmark import normalize as nz  # noqa: E402
from resume_benchmark.config import FIELD_BY_KEY, FIELDS  # noqa: E402
from resume_benchmark.gold_parser import (  # noqa: E402
    audit_row,
    parse_certifications,
    parse_education,
    parse_experience,
)
from resume_benchmark.scoring import BLANK_OK, FALSE_POSITIVE, MATCH, MISS, score_field  # noqa: E402


# ------------------------------------------------------------------ scalars


@pytest.mark.parametrize(
    ('gold', 'pred'),
    [
        ('+91 9699525612', '9699525612'),
        ('9699525612', '+91-9699525612'),
        ('91-8655803235', '+91 8655803235'),
        ('9637195293, 8657436108', '8657436108'),
    ],
)
def test_phone_formats_are_equivalent(gold, pred):
    assert nz.phones(gold) & nz.phones(pred)


def test_phone_wrong_number_is_a_miss():
    spec = FIELD_BY_KEY['phone']
    res = score_field(spec, {'phone': '+91 9699525612'}, {'phone': '+91 9000000000'})
    assert res.verdict == MISS
    assert 'phone_wrong_number' in res.error_tags


def test_name_tolerates_a_missing_middle_name():
    assert nz.name_score('Abrar Rafik Kumbharlikar', 'Abrar Kumbharlikar') >= 0.9


def test_name_rejects_a_header_fragment():
    spec = FIELD_BY_KEY['fullName']
    res = score_field(spec, {'fullName': 'Abrar Rafik Kumbharlikar'}, {'fullName': 'Source'})
    assert res.verdict == MISS


@pytest.mark.parametrize(
    ('gold', 'pred', 'expected'),
    [
        ('https://www.linkedin.com/in/abrar-kumbharlikar', 'linkedin.com/in/abrar-kumbharlikar', MATCH),
        ('https://github.com/x', 'https://github.com/x/', MATCH),
        ('https://www.linkedin.com/in/a', 'https://www.linkedin.com/in/b', MISS),
    ],
)
def test_url_comparison_ignores_cosmetic_differences(gold, pred, expected):
    spec = FIELD_BY_KEY['linkedinUrl']
    assert score_field(spec, {'linkedinUrl': gold}, {'linkedinUrl': pred}).verdict == expected


def test_location_matches_on_the_city_token():
    assert nz.location_score('Mumbai, Maharashtra', 'Mumbai') == pytest.approx(1.0)
    assert nz.location_score('Karad', 'Mumbai') == 0.0


def test_experience_level_maps_spreadsheet_wording_to_parser_enum():
    assert nz.level_key('Experience ') == 'experienced'
    assert nz.level_key('Intern / Entry level') == 'intern'
    assert nz.level_key('Fresher') == 'fresher'


def test_blank_gold_with_a_prediction_is_a_false_positive():
    spec = FIELD_BY_KEY['portfolioUrl']
    res = score_field(spec, {'portfolioUrl': ''}, {'portfolioUrl': 'https://Salesforce.com'})
    assert res.verdict == FALSE_POSITIVE
    assert 'portfolioUrl_invented' in res.error_tags


def test_preferred_location_echo_is_designed_behaviour_not_a_false_positive():
    spec = FIELD_BY_KEY['preferredLocation']
    gold = {'preferredLocation': '', 'currentLocation': 'Mumbai'}
    res = score_field(spec, gold, {'preferredLocation': 'Mumbai', 'currentLocation': 'Mumbai'})
    assert res.verdict == BLANK_OK


# ------------------------------------------------------------------- skills


def test_skills_strip_category_labels_and_alias_variants():
    keys = nz.split_skills('PROGRAMMING LANGUAGE: Oracle SQL\nDATABASE: Oracle 12c & 19c')
    assert 'oracle' in keys
    assert not any(k.startswith('programming language') for k in keys)
    assert nz.skill_key('Node.js') == nz.skill_key('NodeJS')


def test_skills_score_is_set_f1_with_named_gaps():
    spec = FIELD_BY_KEY['skills']
    res = score_field(
        spec,
        {'skills': 'Python, Django, PostgreSQL, Redis'},
        {'skills': 'Python, Django, Kafka', '_skills': ['Python', 'Django', 'Kafka']},
    )
    assert 0.3 < res.score < 0.9
    assert 'postgresql' in res.detail['missed']
    assert 'kafka' in res.detail['extra']


# ------------------------------------------------------------------ sections


EDUCATION_CELL = (
    'Education 1: Bachelor of Science (Information Technology)\n'
    'SM Shetty College, Mumbai.\n06/2011- 04/2014.\n\n'
    'Education 2: High School/Secondary Certificate Programs\n'
    "St. Xavier's College (SCIENCE), Mumbai.\n06/2009- 02/2011."
)


def test_education_cell_splits_into_entries_with_dates():
    entries = parse_education(EDUCATION_CELL)
    assert len(entries) == 2
    assert entries[0].start == '2011-06'
    assert entries[0].end == '2014-04'
    assert any('sm shetty college' in f for f in entries[0].facts)


def test_experience_cell_splits_on_inline_numbering():
    cell = (
        "Experience 1: Natwest Group, Associate Vice President, Mar'2020- Till date"
        "          Experience 2: Royal Bank Of Scotland, Technical Lead, Feb'2014- Feb'2019."
    )
    entries = parse_experience(cell)
    assert len(entries) == 2
    assert entries[1].end == '2019-02'


def test_certification_cell_splits_name_from_issuer():
    entries = parse_certifications(
        'Certification 1:- Social Media Strategy from HubSpot Academy. (Issued May 2020).'
    )
    assert entries[0].primary.lower().startswith('social media strategy')
    assert 'hubspot' in entries[0].secondary.lower()


def test_gold_facts_drop_date_only_lines():
    entries = parse_experience(
        'Experience 1: IBINDER DIGITAL PVT LTD (APPIC MOBILE), Mumbai\nJun 2023 - Present'
    )
    assert entries[0].facts
    assert not any('present' in f for f in entries[0].facts)


def test_section_scoring_rewards_fact_recall_over_row_alignment():
    """One gold entry split across two predicted rows still scores well."""
    spec = FIELD_BY_KEY['education']
    gold = {
        'education': EDUCATION_CELL,
        '_sections': {'education': [e.to_dict() for e in parse_education(EDUCATION_CELL)]},
    }
    prediction = {
        'education': [
            {'degree': 'Bachelor of Science (Information Technology)', 'institution': '',
             'startMonth': '2011-06', 'endMonth': '2014-04'},
            {'degree': '', 'institution': 'SM Shetty College, Mumbai',
             'startMonth': '', 'endMonth': ''},
            {'degree': 'High School/Secondary Certificate Programs',
             'institution': "St. Xavier's College (SCIENCE), Mumbai",
             'startMonth': '2009-06', 'endMonth': '2011-02'},
        ]
    }
    res = score_field(spec, gold, prediction)
    assert res.detail['recall'] == pytest.approx(1.0)
    assert res.verdict == MATCH


def test_section_scoring_penalises_rows_bled_in_from_another_section():
    spec = FIELD_BY_KEY['education']
    gold = {
        'education': EDUCATION_CELL,
        '_sections': {'education': [e.to_dict() for e in parse_education(EDUCATION_CELL)]},
    }
    prediction = {
        'education': [
            {'degree': 'Senior Associate Attorney (AMEX)', 'institution': ''},
            {'degree': '', 'institution': 'Radius Global Solutions LLC'},
        ]
    }
    res = score_field(spec, gold, prediction)
    assert res.detail['precision'] < 0.5
    assert 'education_spurious_rows' in res.error_tags


# --------------------------------------------------------------- gold audit


def test_audit_flags_a_skills_string_pasted_into_the_location_cell():
    issues = audit_row({
        'Current location': 'DB Migration, Installation, Upgradation',
        'Email': 'a@b.com',
        'Phone': '9999999999',
    })
    assert any('location_looks_like_skills' in i for i in issues)


def test_audit_flags_a_non_linkedin_url_in_the_linkedin_column():
    issues = audit_row({'LinkedIn URL': 'https://example.com/me'})
    assert 'linkedin_url_not_linkedin' in issues


def test_every_field_spec_has_a_dispatchable_metric():
    known = {'name', 'email', 'phone', 'location', 'url', 'enum', 'skills', 'text', 'section'}
    assert {f.metric for f in FIELDS} <= known


def test_gold_skill_category_headers_are_not_counted_as_skills():
    cell = 'TECHNICAL SKILLS\nPROGRAMMING LANGUAGES\nC#, C++\nWEB TECHNOLOGIES\nASP.NET, HTML'
    keys = nz.split_skills(cell, drop_headers=True)
    assert 'technical skills' not in keys
    assert 'web technologies' not in keys
    assert 'csharp' in keys and 'html' in keys


def test_predicted_category_headers_stay_visible_as_precision_defects():
    """Headers are noise in gold but a real defect when the parser emits them."""
    assert 'technical skills' in nz.split_skills('TECHNICAL SKILLS, Python')


# ------------------------------------------------------------------- caching


def test_extract_cache_is_dropped_when_ocr_became_available():
    """Text cached without OCR must not be reused once an engine exists."""
    from resume_benchmark.predict import _cache_is_stale

    assert _cache_is_stale({'ocr_available': False}, ocr_available=True)
    assert _cache_is_stale({}, ocr_available=False), 'metadata-less cache is untrustworthy'
    assert not _cache_is_stale({'ocr_available': True}, ocr_available=True)
    assert not _cache_is_stale({'ocr_available': False}, ocr_available=False)
