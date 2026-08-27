"""Semantic residual path must use the full resume contract, one bounded attempt."""
from __future__ import annotations

from app.ai.document_intelligence.models.candidate import CandidateProfile
from app.ai.document_intelligence.semantic import enrich_resume_semantic


def test_enrich_resume_semantic_passes_resume_text_not_fragment(monkeypatch):
    monkeypatch.setenv('DOCUMENT_INTELLIGENCE_SEMANTIC_TIMEOUT_SEC', '90')
    captured: dict = {}

    def fake_parse(text, doc_type, **kwargs):
        captured['text'] = text
        captured['doc_type'] = doc_type
        captured['kwargs'] = kwargs
        return {
            'type': 'resume',
            'person': {'name': 'Jane Doe', 'email': 'jane@example.com', 'phone': '1'},
            'skills': ['Python'],
            'experience': [],
            'education': [],
            'summary': 'Engineer',
        }

    monkeypatch.setattr('app.ai.adapter.runtime_adapter.parse_via_runtime', fake_parse)
    profile = CandidateProfile()
    text = (
        'Jane Doe\nSoftware engineer with Python experience across backend services. '
        * 8
    )
    out = enrich_resume_semantic(profile, unresolved_text=text, force=True)
    assert captured['doc_type'] == 'resume'
    assert 'Extract ONLY missing' not in captured['text']
    assert 'Jane Doe' in captured['text']
    assert captured['kwargs'].get('max_attempts') == 1
    assert float(captured['kwargs'].get('timeout_seconds')) == 90.0
    assert out.personal.full_name or out.skills


def test_semantic_timeout_default_is_bounded():
    import app.ai.document_intelligence.semantic as semantic

    src = open(semantic.__file__, encoding='utf-8').read()
    assert "DOCUMENT_INTELLIGENCE_SEMANTIC_TIMEOUT_SEC', '90'" in src
    assert 'max_attempts=1' in src
    assert 'wait=False' in src
    assert 'abort_in_flight_requests' in src
    assert 'cancel_event' in src


def test_section_llm_timeout_does_not_deadlock_when_slot_held(monkeypatch):
    """Bulk used to hold ollama_slot while semantic waited on the same slot."""
    import time

    from app.ai.document_intelligence.semantic import _call_section_llm
    from app.ai.parser.engine.ollama_limit import ollama_slot, reset_ollama_limit_for_tests

    monkeypatch.setenv('OLLAMA_MAX_CONCURRENT', '1')
    monkeypatch.setenv('DOCUMENT_INTELLIGENCE_SEMANTIC_TIMEOUT_SEC', '1')
    reset_ollama_limit_for_tests()

    def never_return(*_args, **_kwargs):
        time.sleep(30)
        return {}

    monkeypatch.setattr('app.ai.adapter.runtime_adapter.parse_via_runtime', never_return)
    started = time.perf_counter()
    with ollama_slot():
        result = _call_section_llm('hello', 'resume')
    elapsed = time.perf_counter() - started
    reset_ollama_limit_for_tests()
    assert result is None
    assert elapsed < 8


def test_section_llm_timeout_aborts_in_flight_http(monkeypatch):
    import time

    from app.ai.document_intelligence.semantic import _call_section_llm

    abort_calls: list[int] = []
    captured: dict = {}

    def fake_abort():
        abort_calls.append(1)
        return 1

    def never_return(*_args, **kwargs):
        captured['metadata'] = kwargs.get('metadata') or {}
        time.sleep(30)
        return {}

    monkeypatch.setenv('DOCUMENT_INTELLIGENCE_SEMANTIC_TIMEOUT_SEC', '1')
    monkeypatch.setattr('app.ai.adapter.runtime_adapter.parse_via_runtime', never_return)
    monkeypatch.setattr('providers.ollama.client.abort_in_flight_requests', fake_abort)

    started = time.perf_counter()
    result = _call_section_llm('hello world ' * 8, 'resume')
    elapsed = time.perf_counter() - started
    assert result is None
    assert elapsed < 8
    assert abort_calls == [1]
    event = captured['metadata'].get('cancel_event')
    assert event is not None
    assert event.is_set()


def test_bulk_llm_path_does_not_wrap_engine_in_ollama_slot():
    from app.workers import bulk_parser

    src = open(bulk_parser.__file__, encoding='utf-8').read()
    assert 'skip_llm_when_deterministic=False' in src
    engine_call = src.split('skip_llm_when_deterministic=False', 1)[0]
    assert 'with ollama_slot():' not in engine_call[-400:]
