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
