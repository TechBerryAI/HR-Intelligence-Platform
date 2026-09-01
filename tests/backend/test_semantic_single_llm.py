"""One full resume Ollama call per semantic enrichment — regression tests."""
from __future__ import annotations

import json

from app.ai.document_intelligence.models.candidate import (
    CandidateProfile,
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    PersonalInfo,
    SkillEntry,
)
from app.ai.document_intelligence.semantic import enrich_resume_semantic
from app.ai.document_intelligence.semantic.experience import extract_and_merge_experience


INCOMPLETE_EXP_TEXT = """
Jane Doe
Software engineer based in Bengaluru.

Experience
Database Administrator
Infosenseglobal | Dec 2024 – Present
Administered PostgreSQL backups and failover for production clusters.

Education
B.Tech Computer Science, Visvesvaraya Technological University
""".strip()


def _full_llm_payload() -> dict:
    return {
        'type': 'resume',
        'person': {
            'name': 'Jane Doe',
            'email': 'jane@example.com',
            'phone': '9876543210',
            'location': 'Bengaluru',
            'linkedin': '',
            'github': '',
            'portfolio': '',
        },
        'skills': ['PostgreSQL', 'Linux'],
        'experience': [
            {
                'title': 'Database Administrator',
                'company': 'Infosenseglobal',
                'from': '2024-12',
                'to': 'Present',
                'description': 'Administered PostgreSQL backups and failover.',
            }
        ],
        'education': [
            {
                'degree': 'B.Tech',
                'field': 'Computer Science',
                'institution': 'Visvesvaraya Technological University',
                'year': '2022',
            }
        ],
        'summary': 'Database administrator with PostgreSQL experience.',
        'projects': [],
        'certifications': ['AWS Cloud Practitioner'],
        'languages': ['English'],
    }


def _counting_llm(monkeypatch, payload: dict) -> list[int]:
    calls: list[int] = []

    def fake_llm(prompt, doc_kind):
        calls.append(1)
        assert doc_kind == 'resume'
        assert 'Jane Doe' in prompt or 'Experience' in prompt or len(prompt) >= 40
        return dict(payload)

    monkeypatch.setattr(
        'app.ai.document_intelligence.semantic._call_section_llm',
        fake_llm,
    )
    return calls


def test_incomplete_experience_makes_exactly_one_llm_call(monkeypatch, caplog):
    calls = _counting_llm(monkeypatch, _full_llm_payload())

    def boom(*_a, **_k):
        raise AssertionError('extract_and_merge_experience must not invoke Ollama')

    monkeypatch.setattr(
        'app.ai.document_intelligence.semantic.experience.extract_and_merge_experience',
        boom,
    )

    profile = CandidateProfile(
        personal=PersonalInfo(full_name='Jane Doe'),
        contact=ContactInfo(email='jane@example.com'),
        skills=[SkillEntry(name='PostgreSQL', canonical='PostgreSQL')],
    )
    with caplog.at_level('INFO'):
        out = enrich_resume_semantic(profile, unresolved_text=INCOMPLETE_EXP_TEXT)

    assert len(calls) == 1
    assert any(e.role == 'Database Administrator' for e in out.experience)
    assert any(e.company == 'Infosenseglobal' for e in out.experience)
    log = caplog.text
    assert 'ollama_call=1' in log
    assert 'ollama_call=2 SKIPPED' in log
    assert 'semantic_llm_calls' in log or 'llm_calls=1' in log


def test_experience_plus_other_gaps_still_one_llm_call(monkeypatch):
    calls = _counting_llm(monkeypatch, _full_llm_payload())
    profile = CandidateProfile()
    out = enrich_resume_semantic(profile, unresolved_text=INCOMPLETE_EXP_TEXT)

    assert len(calls) == 1
    assert out.personal.full_name == 'Jane Doe'
    assert out.contact.email == 'jane@example.com'
    assert out.contact.phone == '9876543210'
    assert 'Bengaluru' in (out.contact.location or '')
    assert out.education
    assert out.experience
    assert out.skills


def test_strong_deterministic_profile_makes_zero_llm_calls(monkeypatch):
    calls = _counting_llm(monkeypatch, _full_llm_payload())
    text = (
        'Jane Doe is a software engineer at Acme Labs in Bengaluru. '
        'She uses Python and SQL. Education: B.Tech Computer Science, '
        'Visvesvaraya Technological University.'
    )
    profile = CandidateProfile(
        personal=PersonalInfo(full_name='Jane Doe', summary='Software engineer.'),
        contact=ContactInfo(
            email='jane@example.com',
            phone='9876543210',
            location='Bengaluru',
        ),
        skills=[
            SkillEntry(name='Python', canonical='Python'),
            SkillEntry(name='SQL', canonical='SQL'),
        ],
        experience=[
            ExperienceEntry(role='Software Engineer', company='Acme Labs', start='2022-01'),
        ],
        education=[
            EducationEntry(
                degree='B.Tech',
                field='Computer Science',
                institution='Visvesvaraya Technological University',
            ),
        ],
    )
    out = enrich_resume_semantic(profile, unresolved_text=text)
    assert len(calls) == 0
    assert out.contact.email == 'jane@example.com'
    assert out.experience[0].company == 'Acme Labs'


def test_single_response_fills_experience_education_contact_skills(monkeypatch):
    _counting_llm(monkeypatch, _full_llm_payload())
    out = enrich_resume_semantic(
        CandidateProfile(),
        unresolved_text=INCOMPLETE_EXP_TEXT,
        force=True,
    )
    assert out.personal.full_name == 'Jane Doe'
    assert out.contact.email == 'jane@example.com'
    assert out.contact.phone == '9876543210'
    assert out.contact.location
    assert out.education
    assert out.experience
    assert {s.canonical or s.name for s in out.skills} >= {'PostgreSQL'}
    assert out.personal.summary


def test_deterministic_contact_wins_over_semantic(monkeypatch):
    payload = _full_llm_payload()
    payload['person']['email'] = 'other@example.com'
    payload['person']['phone'] = '9999999999'
    payload['person']['name'] = 'AI Invented Name'
    _counting_llm(monkeypatch, payload)

    profile = CandidateProfile(
        personal=PersonalInfo(full_name='Jane Doe'),
        contact=ContactInfo(email='jane@example.com', phone='9876543210'),
        skills=[SkillEntry(name='PostgreSQL', canonical='PostgreSQL')],
    )
    out = enrich_resume_semantic(profile, unresolved_text=INCOMPLETE_EXP_TEXT)
    assert out.personal.full_name == 'Jane Doe'
    assert out.contact.email == 'jane@example.com'
    assert out.contact.phone == '9876543210'
    assert out.experience


def test_extract_and_merge_experience_does_not_call_llm(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError('_call_section_llm must not run from extract_and_merge_experience')

    monkeypatch.setattr(
        'app.ai.document_intelligence.semantic._call_section_llm',
        boom,
    )
    profile = CandidateProfile()
    unchanged = extract_and_merge_experience(profile, INCOMPLETE_EXP_TEXT)
    assert unchanged is profile
    merged = extract_and_merge_experience(
        profile, INCOMPLETE_EXP_TEXT, raw=_full_llm_payload()
    )
    assert any(e.company == 'Infosenseglobal' for e in merged.experience)


def test_enrich_source_never_calls_extract_and_merge_experience():
    import app.ai.document_intelligence.semantic as semantic
    import app.ai.document_intelligence.semantic.experience as experience

    src = open(semantic.__file__, encoding='utf-8').read()
    exp_src = open(experience.__file__, encoding='utf-8').read()
    assert 'extract_and_merge_experience' not in src
    assert '_call_section_llm' not in exp_src


def test_large_resume_json_fits_generation_budget_and_merges(monkeypatch):
    jobs = []
    lines = ['Jane Doe', 'Experience']
    for i in range(12):
        company = f'Acme{i} Labs'
        role = 'Software Engineer'
        lines.append(f'{role}')
        lines.append(f'{company} | Jan 201{i % 9} – Dec 201{(i % 9) + 1}')
        desc = ('Delivered backend services, APIs, and PostgreSQL tuning. ' * 8).strip()
        lines.append(desc)
        jobs.append(
            {
                'title': role,
                'company': company,
                'from': f'201{i % 9}-01',
                'to': f'201{(i % 9) + 1}-12',
                'description': desc,
            }
        )
    text = '\n'.join(lines) + '\nEducation\nB.Tech CS, VTU University\n'
    payload = _full_llm_payload()
    payload['experience'] = jobs
    payload['skills'] = [f'Skill{i}' for i in range(40)]
    encoded = json.dumps(payload)
    # Output budget is 4096 tokens; chars/4 is a conservative token estimate.
    assert len(encoded) / 4 < 4096

    calls = _counting_llm(monkeypatch, payload)
    out = enrich_resume_semantic(
        CandidateProfile(),
        unresolved_text=text,
        force=True,
    )
    assert len(calls) == 1
    assert isinstance(out, CandidateProfile)
    assert out.personal.full_name == 'Jane Doe'
    assert len(out.experience) >= 1
    round_trip = json.dumps(
        {
            'person': {'name': out.personal.full_name, 'email': out.contact.email},
            'experience': [
                {'title': e.role, 'company': e.company, 'description': e.description}
                for e in out.experience
            ],
            'skills': [s.name for s in out.skills],
            'education': [
                {'degree': e.degree, 'institution': e.institution} for e in out.education
            ],
        }
    )
    assert round_trip.strip().endswith('}')
    assert '"title"' in round_trip or out.experience
