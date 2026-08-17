"""Unit tests for Intelligence Engine stages (no LLM / no DB)."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
APP_ROOT = BACKEND_ROOT / 'app'
for p in (str(BACKEND_ROOT), str(APP_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.ai.parser.engine.sections import detect_sections, unresolved_semantic_text
from app.ai.parser.engine.knowledge import normalize_skill, apply_knowledge_to_resume
from app.ai.parser.engine.deterministic_jd import parse_jd_deterministic, score_jd_toon
from app.ai.parser.engine.hardware import detect_hardware_profile
from app.ai.parser.engine.confidence import prefer_deterministic_person, prefer_deterministic_jd


SAMPLE_RESUME = """
Jane Doe
jane.doe@example.com
+1 555-0100

Skills:
Python, SQL, Docker

Experience:
Software Engineer | Acme Corp | Jan 2020 - Present
Built APIs.

Education:
B.Tech Computer Science, State University, 2019
"""

SAMPLE_JD = """
Job Title: Backend Developer
Company: TechNova
Location: Bengaluru
Experience: 3-5 years

**Responsibilities:**
• Build APIs
• Own services

**Required Skills:**
Python, SQL, Docker

**Preferred Skills:**
Kubernetes, AWS
"""


def test_detect_sections_resume():
    sections = detect_sections(SAMPLE_RESUME, 'resume')
    labels = {s.label.lower() for s in sections}
    assert any('skill' in l for l in labels) or len(sections) >= 1
    semantic = unresolved_semantic_text(sections, 'resume')
    assert 'Python' in semantic or 'Experience' in semantic or len(semantic) > 20


def test_detect_sections_jd():
    sections = detect_sections(SAMPLE_JD, 'jd')
    assert len(sections) >= 1


def test_normalize_skill_builtin():
    display, _ = normalize_skill('js')
    assert display == 'JavaScript'
    display2, _ = normalize_skill('k8s')
    assert display2 == 'Kubernetes'


def test_apply_knowledge_resume():
    toon = {'type': 'resume', 'skills': ['js', 'python'], 'person': {}, 'experience': [], 'education': []}
    out = apply_knowledge_to_resume(toon)
    assert 'JavaScript' in out['skills']
    assert 'Python' in out['skills']


def test_parse_jd_deterministic_gate():
    toon, conf, missing, passes = parse_jd_deterministic(SAMPLE_JD)
    assert toon.get('type') == 'job_description'
    assert toon.get('title')
    assert toon.get('skills') or toon.get('responsibilities')
    # Well-formed JD should usually pass
    assert passes or conf >= 0.5


def test_score_jd_requires_title():
    conf, missing, passes = score_jd_toon({'type': 'job_description', 'title': '', 'skills': ['x'], 'location': 'Remote'})
    assert not passes
    assert 'title' in missing


def test_prefer_deterministic_person():
    llm = {'person': {'email': 'wrong@x.com', 'phone': '', 'name': 'A'}}
    det = {'person': {'email': 'right@x.com', 'phone': '123', 'name': 'A'}}
    out = prefer_deterministic_person(llm, det)
    assert out['person']['email'] == 'right@x.com'
    assert out['person']['phone'] == '123'


def test_prefer_deterministic_jd():
    llm = {'title': 'Engineer', 'salary_range': '', 'location': ''}
    det = {'title': 'Engineer', 'salary_range': '10-15 LPA', 'location': 'Remote'}
    out = prefer_deterministic_jd(llm, det)
    assert out['salary_range'] == '10-15 LPA'
    assert out['location'] == 'Remote'


def test_hardware_profile_detects():
    profile = detect_hardware_profile()
    assert profile.name in ('gpu_high', 'gpu_mid', 'unknown', 'cpu')
    assert profile.ollama_max_concurrent >= 1
