"""Persistent file-upload cache hit must skip extract and semantic."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_cache_hit_skips_extract_and_semantic(monkeypatch):
    from app.ai.document_intelligence import pipeline as pip
    import app.ai.parser.text_extraction as te

    cached = {
        'parsed_id': 'p1',
        'raw_file_id': 'r1',
        'toon': {'person': {'email': 'a@b.c'}, 'skills': []},
        'confidence': 0.9,
        'model_version': 'canonical-v8-exp-layout',
        'raw_text': 'Jane Doe jane@x.com',
    }
    called = {'extract': 0, 'semantic': 0}

    monkeypatch.setattr(pip, 'get_cached_parsing_result', lambda *a, **k: cached)
    monkeypatch.setattr(pip, 'get_cached_parsing_result_by_hash', lambda *a, **k: None)
    monkeypatch.setattr(pip, '_refresh_resume_from_cached_text', lambda text: None)

    def boom_extract(*_a, **_k):
        called['extract'] += 1
        raise AssertionError('extract_text must not run on cache-hit')

    def boom_semantic(*_a, **_k):
        called['semantic'] += 1
        raise AssertionError('enrich_resume_semantic must not run on cache-hit')

    monkeypatch.setattr(te, 'extract_text', boom_extract)
    monkeypatch.setattr(pip, 'enrich_resume_semantic', boom_semantic)

    body, status = pip._run_resume(
        b'%PDF-cached-bytes',
        'cv.pdf',
        uploader_id='U1',
        uploader_role='recruiter',
        candidate_id=None,
        parse_job_id='job-1',
        on_stage=None,
        use_content_hash_cache=True,
    )
    assert status == 200
    assert body.get('cache_status') == 'cache-hit'
    assert body.get('is_duplicate') is True
    assert called['extract'] == 0
    assert called['semantic'] == 0
