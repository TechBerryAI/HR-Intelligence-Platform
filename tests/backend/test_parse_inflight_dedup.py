"""Stream/sync fallback must join in-flight public parses of the same bytes."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser.engine.parse_inflight import inflight_key, reset_parse_inflight_for_tests, run_or_join


def setup_function():
    reset_parse_inflight_for_tests()


def teardown_function():
    reset_parse_inflight_for_tests()


def test_overlapping_same_key_runs_once():
    runs = []
    started = threading.Event()
    release = threading.Event()

    def work():
        started.set()
        release.wait(timeout=2)
        runs.append(1)
        return {'status': 'ok', 'n': len(runs)}

    key = inflight_key('abc', 'resume', 'tag')
    results = []

    def caller():
        results.append(run_or_join(key, work))

    t1 = threading.Thread(target=caller)
    t2 = threading.Thread(target=caller)
    t1.start()
    assert started.wait(timeout=2)
    t2.start()
    time.sleep(0.05)
    release.set()
    t1.join(timeout=2)
    t2.join(timeout=2)
    assert runs == [1]
    assert results[0] == results[1]
    assert results[0]['status'] == 'ok'


def test_recent_hit_does_not_rerun():
    n = {'c': 0}

    def work():
        n['c'] += 1
        return n['c']

    key = inflight_key('same', 'resume', 'v1')
    assert run_or_join(key, work, ttl_sec=30) == 1
    assert run_or_join(key, work, ttl_sec=30) == 1
    assert n['c'] == 1


def test_different_hash_parses_separately():
    n = {'c': 0}

    def work():
        n['c'] += 1
        return n['c']

    assert run_or_join(inflight_key('a', 'resume', 'v1'), work) == 1
    assert run_or_join(inflight_key('b', 'resume', 'v1'), work) == 2
    assert n['c'] == 2


def test_failure_allows_retry():
    n = {'c': 0}

    def boom():
        n['c'] += 1
        if n['c'] == 1:
            raise RuntimeError('parse failed')
        return 'ok'

    key = inflight_key('x', 'resume', 'v1')
    try:
        run_or_join(key, boom)
        assert False, 'expected failure'
    except RuntimeError:
        pass
    assert run_or_join(key, boom) == 'ok'
    assert n['c'] == 2


def test_pipeline_public_join(monkeypatch):
    from app.ai.document_intelligence import pipeline as pip
    from app.ai.parser.engine.parse_inflight import reset_parse_inflight_for_tests

    reset_parse_inflight_for_tests()
    calls = {'n': 0}

    def fake_resume(**kwargs):
        calls['n'] += 1
        time.sleep(0.05)
        return {'status': 'ok', 'form': {'email': 'a@b.c'}}, 200

    monkeypatch.setattr(pip, '_run_resume', lambda *a, **k: fake_resume())
    monkeypatch.setattr(pip, 'apply_hardware_env', lambda: None)

    payload = b'%PDF-fake-bytes-same'
    out = []

    def go(uploader):
        body, status = pip.run_document_intelligence(
            'resume',
            payload,
            'cv.pdf',
            uploader_id=uploader,
            uploader_role='public',
        )
        out.append((body.get('status'), status, calls['n']))

    t1 = threading.Thread(target=go, args=('PUB1',))
    t2 = threading.Thread(target=go, args=('PUB2',))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert calls['n'] == 1
    assert all(status == 200 for _st, status, _n in out)
    reset_parse_inflight_for_tests()
