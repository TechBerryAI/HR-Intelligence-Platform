"""
Integration tests for Intelligence Engine text pipeline + API thin wrappers.

No live LLM required for the deterministic path. Uses Flask test client for HTTP shape.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
APP_ROOT = BACKEND_ROOT / 'app'
for p in (str(BACKEND_ROOT), str(APP_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

SAMPLE = """
Jane Doe
jane.doe@example.com
+1 (555) 010-1234
Austin, TX

Skills:
Python, SQL, Docker

Experience:
Software Engineer | Acme Corp | Jan 2020 - Present
Built APIs.

Education:
B.Tech Computer Science, State University, 2019
"""


def test_parse_resume_text_via_engine_deterministic():
    from app.ai.parser.engine import parse_resume_text_via_engine

    toon, source, notes, form = parse_resume_text_via_engine(
        SAMPLE,
        allow_llm=False,
        skip_llm_when_deterministic=True,
    )
    assert isinstance(toon, dict)
    assert toon.get('type') == 'resume' or toon.get('person')
    person = toon.get('person') or {}
    assert 'jane.doe' in str(person.get('email') or '').lower()
    assert source in ('deterministic', 'text-fallback')
    assert any('sections=' in n or n == 'parsers=resume_from_text' for n in notes)
    assert form is not None
    assert getattr(form, 'email', None) or (isinstance(form, dict) and form.get('email'))


def test_apply_hardware_sets_ollama_model_when_unset(monkeypatch):
    from app.ai.parser.engine import hardware as hw

    monkeypatch.delenv('OLLAMA_MODEL', raising=False)
    monkeypatch.setenv('HCIP_HARDWARE_PROFILE', 'cpu')
    hw.reset_hardware_env_for_tests()
    profile = hw.apply_hardware_env()
    assert profile.name == 'cpu'
    assert os_environ_model() == profile.preferred_model_hint
    assert profile.preferred_model_hint  # non-empty adaptive selection


def os_environ_model():
    import os

    return os.environ.get('OLLAMA_MODEL')


def test_engine_parsers_imported_by_text_pipeline():
    """Audit fix: engine.parsers must not be a dead façade."""
    import app.ai.parser.engine.text_pipeline as tp
    import inspect

    src = inspect.getsource(tp.parse_resume_text_via_engine)
    assert 'parse_resume_from_text' in src


def test_parse_progress_endpoint_shape():
    """HTTP: progress endpoint returns 404 for unknown job (no DB needed)."""
    from app.bootstrap.create_app import create_app

    app = create_app()
    client = app.test_client()
    res = client.get('/api/parse/jobs/does-not-exist/progress')
    assert res.status_code == 404
    body = res.get_json()
    assert body.get('status') == 'error'
    assert 'result' not in (body or {})


def test_public_resume_parse_rejects_empty_file():
    from app.bootstrap.create_app import create_app

    app = create_app()
    client = app.test_client()
    res = client.post('/api/parse/resume/public')
    assert res.status_code == 400
