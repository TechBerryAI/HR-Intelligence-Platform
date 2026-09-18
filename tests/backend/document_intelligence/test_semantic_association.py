"""Phase 3 semantic association + field-accuracy tests.

Uses the Apply parse tail (prepare + parse_resume_from_working_text) so
association runs in the same place as production. No resume-specific rules.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
HERE = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from association_gold import list_golden_stems, load_golden_case, score_profile  # noqa: E402
from app.ai.document_intelligence.association import apply_semantic_association  # noqa: E402
from app.ai.document_intelligence.association.classification import (  # noqa: E402
    classify_certificate_name,
)
from app.ai.document_intelligence.association.education import (  # noqa: E402
    associate_education,
    split_education_blocks,
)
from app.ai.document_intelligence.association.experience import (  # noqa: E402
    associate_experience,
    split_experience_blocks,
)
from app.ai.document_intelligence.association.taxonomy import (  # noqa: E402
    CROSS_RECORD_LEAK,
    ENTITY_MISASSOCIATION,
    MISASSOCIATED,
    TAXONOMY,
    UNSUPPORTED_INFERENCE,
)
from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form  # noqa: E402
from app.ai.document_intelligence.models.candidate import (  # noqa: E402
    EducationEntry,
    ExperienceEntry,
)
from app.ai.document_intelligence.pipeline import parse_resume_from_working_text  # noqa: E402
from app.ai.document_intelligence.resume_preprocess import prepare_resume_working_text  # noqa: E402
from app.ai.document_intelligence.sections import detect_sections  # noqa: E402


def _parse(text: str):
    working = prepare_resume_working_text(text)
    profile, coverage, sections, used_llm, _toon = parse_resume_from_working_text(
        working,
        allow_semantic=False,
        source_filename='association-gold.txt',
    )
    form = map_candidate_to_form(profile, coverage=coverage.as_dicts())
    return profile, form, coverage, used_llm, sections, working


def test_taxonomy_covers_association_classes():
    assert CROSS_RECORD_LEAK in TAXONOMY
    assert ENTITY_MISASSOCIATION in TAXONOMY
    assert UNSUPPORTED_INFERENCE in TAXONOMY
    assert len(TAXONOMY) >= 10


def test_experience_blocks_do_not_share_duties():
    text = (
        'Experience\n'
        'ABC Technologies\nSoftware Engineer\nJan 2020 - Mar 2022\n\n'
        'Developed REST APIs.\nManaged deployment pipelines.\n\n'
        'XYZ Solutions\nSenior Software Engineer\nApr 2022 - Present\n\n'
        'Led engineering team.\nDesigned distributed architecture.\n'
    )
    blocks = split_experience_blocks(text)
    assert len(blocks) >= 2
    first = ' '.join(blocks[0]['duties']).lower()
    second = ' '.join(blocks[-1]['duties']).lower()
    assert 'rest apis' in first
    assert 'distributed' in second
    assert 'distributed' not in first
    assert 'rest apis' not in second


def test_associate_experience_stops_duty_leak():
    leaked = [
        ExperienceEntry(
            company='ABC Technologies',
            role='Software Engineer',
            start='2020-01',
            end='2022-03',
            description=(
                'Developed REST APIs.\nManaged deployment pipelines.\n'
                'XYZ Solutions\nSenior Software Engineer\n'
                'Led engineering team.\nDesigned distributed architecture.'
            ),
        ),
        ExperienceEntry(
            company='XYZ Solutions',
            role='Senior Software Engineer',
            start='2022-04',
            end='Present',
            description='',
        ),
    ]
    text = (
        'Experience\n'
        'ABC Technologies\nSoftware Engineer\nJan 2020 - Mar 2022\n'
        'Developed REST APIs.\nManaged deployment pipelines.\n'
        'XYZ Solutions\nSenior Software Engineer\nApr 2022 - Present\n'
        'Led engineering team.\nDesigned distributed architecture.\n'
    )
    out = associate_experience(leaked, text)
    assert len(out) >= 2
    abc = next(e for e in out if 'abc' in (e.company or '').lower())
    xyz = next(e for e in out if 'xyz' in (e.company or '').lower())
    assert 'rest apis' in (abc.description or '').lower()
    assert 'distributed' not in (abc.description or '').lower()
    assert 'distributed' in (xyz.description or '').lower()
    assert 'rest apis' not in (xyz.description or '').lower()


def test_education_dates_stay_with_own_record():
    rows = [
        EducationEntry(degree='MBA', institution='University A', end='2014'),
        EducationEntry(degree='B.Tech', institution='University B', end='2018'),
    ]
    text = 'Education\nMBA\nUniversity A\n2018\n\nB.Tech\nUniversity B\n2014\n'
    blocks = split_education_blocks(text)
    assert len(blocks) >= 2
    out = associate_education(rows, text)
    mba = next(e for e in out if 'mba' in (e.degree or '').lower())
    btech = next(e for e in out if 'tech' in (e.degree or '').lower())
    assert '2018' in (mba.end or '')
    assert '2014' in (btech.end or '')


def test_classify_cert_vs_skill_vs_training():
    assert classify_certificate_name('AWS Certified Solutions Architect – Associate') == 'certification'
    assert classify_certificate_name('Completed AWS cloud training') == 'training'
    assert classify_certificate_name('AWS') == 'skill'
    assert classify_certificate_name('Docker') == 'skill'
    assert classify_certificate_name('PMP') == 'certification'
    assert classify_certificate_name('Developed Python automation scripts') == 'experience_mention'


def test_golden_two_jobs_education_association():
    text, expected = load_golden_case('two_jobs_education')
    profile, form, _c, _llm, _sec, _w = _parse(text)
    scored = score_profile(profile, expected)
    jobs = form.experiences or []
    assert len(jobs) >= 2
    first = next(j for j in jobs if 'abc' in (j.company or '').lower())
    second = next(j for j in jobs if 'xyz' in (j.company or '').lower())
    assert 'software engineer' in (first.role or '').lower()
    assert 'senior' in (second.role or '').lower()
    assert 'rest' in (first.description or '').lower()
    assert 'distributed' in (second.description or '').lower()
    assert 'distributed' not in (first.description or '').lower()
    cert_names = ' '.join(c.name or '' for c in (form.certifications or [])).lower()
    assert 'certified' in cert_names
    assert not any((c.name or '').strip().upper() == 'AWS' for c in (form.certifications or []))
    mba = next(
        (e for e in (profile.education or []) if 'mba' in (e.degree or '').lower()),
        None,
    )
    btech_b = next(
        (
            e
            for e in (profile.education or [])
            if 'university b' in (e.institution or '').lower()
            or (
                'b.tech' in (e.degree or '').lower()
                and 'university a' not in (e.institution or '').lower()
                and 'abc' not in (e.institution or '').lower()
            )
        ),
        None,
    )
    if mba:
        assert 'university a' in (mba.institution or '').lower()
        assert '2018' in f'{mba.start} {mba.end}'
        assert '2014' not in (mba.end or '')
    if btech_b:
        assert '2014' in f'{btech_b.start} {btech_b.end}'
    misassociated = [v for v in scored['verdicts'] if v['status'] == MISASSOCIATED]
    assert not misassociated, misassociated


def test_golden_university_only_does_not_invent_degree():
    text, expected = load_golden_case('university_only_no_degree')
    profile, _form, _c, _llm, _sec, _w = _parse(text)
    scored = score_profile(profile, expected)
    for row in profile.education or []:
        deg = (row.degree or '').strip().lower()
        assert deg not in {"bachelor", "bachelor's", "bachelor's degree", "degree"}
        assert 'bachelor' not in deg
    assert scored['counts'][MISASSOCIATED] == 0


def test_golden_summary_and_skill_cert_boundary():
    text, expected = load_golden_case('summary_certs_boundary')
    profile, form, _c, _llm, _sec, _w = _parse(text)
    scored = score_profile(profile, expected)
    summary = (form.summary or '').lower()
    assert 'seeking' in summary
    assert 'asha.nair@example.com' not in summary
    assert '+91' not in summary
    assert 'linkedin.com' not in summary
    cert_names = [(c.name or '').strip().lower() for c in (form.certifications or [])]
    assert not any(n == 'aws' for n in cert_names)
    skills = (form.skills or '').lower()
    assert 'sql' in skills or any('sql' in (s.canonical or s.name or '').lower() for s in profile.skills)
    assert scored['counts'][MISASSOCIATED] == 0


def test_layer_is_idempotent_on_clean_profile():
    def _snapshot(p):
        return {
            'experience': [
                (e.company, e.role, e.start, e.end, e.description)
                for e in (p.experience or [])
            ],
            'education': [
                (e.degree, e.institution, e.field, e.start, e.end)
                for e in (p.education or [])
            ],
            'certs': [(c.name, c.issuer, c.valid_till) for c in (p.certificates or [])],
            'skills': [(s.canonical or s.name) for s in (p.skills or [])],
            'summary': p.personal.summary if p.personal else '',
        }

    for stem in list_golden_stems():
        text, _expected = load_golden_case(stem)
        working = prepare_resume_working_text(text)
        profile, _c, sections, _llm, _t = parse_resume_from_working_text(
            working, allow_semantic=False, source_filename=f'idempotent-{stem}.txt'
        )
        once = apply_semantic_association(profile, sections, working)
        twice = apply_semantic_association(once, sections, working)
        assert _snapshot(once) == _snapshot(twice), stem


def test_association_report_is_internal_not_required_on_form():
    text, _expected = load_golden_case('two_jobs_education')
    profile, form, _c, _llm, _sec, _w = _parse(text)
    assert 'association_report' in (profile.field_meta or {})
    dumped = form.to_autofill_dict()
    assert 'association_report' not in dumped
    assert 'association_report' not in dumped.get('coverage', []) if isinstance(
        dumped.get('coverage'), list
    ) else True


def test_thin_experience_section_does_not_fill_summary_as_company():
    """Two-column/sidebar: Experience header exists but body is elsewhere.

    Association must not take the following Summary heading as employer
    and must not drop the already-parsed job.
    """
    _profile, form, _c, _llm, _sec, _w = _parse(
        'Devashish Example\nEmail: dev@example.com\n'
        'Experience\n'
        'The Oterra Hotel\nAssociate (Sales and Marketing)\n'
        'Nov 2023 - Aug 2024\n'
        'Handled social media marketing activities.\n'
        'Summary\n'
        'Dynamic hospitality professional with 5 years of experience driving revenue.\n'
        'Education\nB.A. Hospitality\nITM University Mumbai\n2019\n'
    )
    assert form.experiences, 'job row must survive association'
    job = form.experiences[0]
    assert (job.role or '').lower().find('associate') >= 0 or (job.company or '')
    assert (job.company or '').strip().lower() not in {'summary', 'education', 'skills'}


def test_association_does_not_wipe_only_description():
    jobs = [
        ExperienceEntry(
            company='DEVOPS & QE',
            role='PROJECT LEAD',
            start='2010-12',
            description='FIS Global Pvt Ltd, Jacksonville, Florida\nLed delivery.',
        ),
        ExperienceEntry(
            company='Infosys',
            role='AUTOMATION LEAD',
            start='2007-12',
            description='Spearheaded GenAI initiatives.',
        ),
    ]
    text = (
        'Experience\n'
        'PROJECT LEAD\nDEVOPS & QE\nDec 2010 - Present\n'
        'FIS Global Pvt Ltd, Jacksonville, Florida\nLed delivery.\n'
        'AUTOMATION LEAD\nInfosys\nDec 2007 - Nov 2010\n'
        'Spearheaded GenAI initiatives.\n'
    )
    out = associate_experience(jobs, text)
    first = next(e for e in out if 'devops' in (e.company or '').lower() or 'project' in (e.role or '').lower())
    assert (first.description or '').strip(), 'must not wipe the only description'

    text, _ = load_golden_case('two_jobs_education')
    labels = {s.label.lower() for s in detect_sections(text, 'resume')}
    assert any('experience' in lab or lab == 'experience' for lab in labels)
    assert any('education' in lab for lab in labels)
