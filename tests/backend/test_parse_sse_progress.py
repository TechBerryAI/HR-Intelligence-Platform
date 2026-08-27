"""SSE parse progress must flush stage events before the pipeline finishes."""
from __future__ import annotations

import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser.engine.types import StageEvent
from app.domains.recruitment.api.parsing import iter_parse_sse


def test_iter_parse_sse_yields_stages_before_result():
    def run(on_stage):
        on_stage(StageEvent(stage='cache', status='started', message='Checking parse cache'))
        time.sleep(0.35)
        on_stage(StageEvent(stage='text', status='started', message='Extracting text'))
        time.sleep(0.15)
        return ({'status': 'ok', 'form': {'fullName': 'Ada'}}, 200)

    chunks = []
    saw_stage_before_result = False
    for chunk in iter_parse_sse(run, lambda body: body):
        chunks.append(chunk)
        if 'event: stage' in chunk and '"stage": "cache"' in chunk:
            saw_stage_before_result = True
        if 'event: result' in chunk:
            break

    joined = ''.join(chunks)
    assert saw_stage_before_result, 'cache stage must stream before the parse finishes'
    assert 'event: result' in joined
    assert '"stage": "text"' in joined
    assert 'Checking parse cache' in joined


def test_stage_event_includes_duration_ms():
    ev = StageEvent(
        stage='text',
        status='completed',
        message='Extracted 1200 chars',
        duration_ms=180000.4,
    )
    payload = ev.to_dict()
    assert payload['stage'] == 'text'
    assert payload['duration_ms'] == 180000.4


def test_iter_parse_sse_forwards_stage_duration_ms():
    def run(on_stage):
        on_stage(StageEvent(stage='text', status='completed', duration_ms=27100))
        return ({'status': 'ok', 'form': {'fullName': 'Ada'}}, 200)

    joined = ''.join(iter_parse_sse(run, lambda body: body))
    assert 'event: stage' in joined
    assert '27100' in joined
    assert 'duration_ms' in joined
    assert 'event: result' in joined


def test_iter_parse_sse_error_event_on_nonzero_status():
    def run(on_stage):
        on_stage(StageEvent(stage='cache', status='started'))
        return ({'status': 'error', 'error': 'Unable to parse this document'}, 400)

    joined = ''.join(iter_parse_sse(run, lambda body: body))
    assert 'event: error' in joined
    assert 'Unable to parse this document' in joined
    assert 'event: result' not in joined
