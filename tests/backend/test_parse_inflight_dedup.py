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
from app.ai.parser.engine.progress import (
    get_parse_job,
    parse_job_statuses_for_tests,
    reset_parse_jobs_for_tests,
)


def setup_function():
    reset_parse_inflight_for_tests()
    reset_parse_jobs_for_tests()


def teardown_function():
    reset_parse_inflight_for_tests()
    reset_parse_jobs_for_tests()


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


def _assert_no_running_jobs():
    statuses = parse_job_statuses_for_tests()
    assert 'running' not in statuses.values(), statuses
    for jid, status in statuses.items():
        job = get_parse_job(jid)
        assert job is not None
        assert job['status'] in ('completed', 'failed')


def test_pipeline_public_join(monkeypatch):
    from app.ai.document_intelligence import pipeline as pip

    reset_parse_inflight_for_tests()
    reset_parse_jobs_for_tests()
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
        out.append((body, status))

    t1 = threading.Thread(target=go, args=('PUB1',))
    t2 = threading.Thread(target=go, args=('PUB2',))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert calls['n'] == 1
    assert all(status == 200 for _body, status in out)
    job_ids = {body.get('parse_job_id') for body, _status in out}
    assert len(job_ids) == 1
    _assert_no_running_jobs()
    reset_parse_inflight_for_tests()
    reset_parse_jobs_for_tests()


def test_pipeline_join_failure_terminals(monkeypatch):
    from app.ai.document_intelligence import pipeline as pip

    def fake_resume(**kwargs):
        time.sleep(0.05)
        return {'status': 'error', 'error': 'parse boom'}, 500

    monkeypatch.setattr(pip, '_run_resume', lambda *a, **k: fake_resume())
    monkeypatch.setattr(pip, 'apply_hardware_env', lambda: None)

    payload = b'%PDF-fail-same'
    out = []

    def go():
        out.append(
            pip.run_document_intelligence(
                'resume',
                payload,
                'cv.pdf',
                uploader_id='PUBX',
                uploader_role='public',
            )
        )

    t1 = threading.Thread(target=go)
    t2 = threading.Thread(target=go)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert all(status == 500 for _body, status in out)
    _assert_no_running_jobs()
    for body, _status in out:
        job = get_parse_job(body['parse_job_id'])
        assert job['status'] == 'failed'


def test_pipeline_exception_terminals(monkeypatch):
    from app.ai.document_intelligence import pipeline as pip

    def fake_resume(**kwargs):
        raise RuntimeError('explode')

    monkeypatch.setattr(pip, '_run_resume', lambda *a, **k: fake_resume())
    monkeypatch.setattr(pip, 'apply_hardware_env', lambda: None)
    body, status = pip.run_document_intelligence(
        'resume',
        b'%PDF-x',
        'cv.pdf',
        uploader_id='PUB1',
        uploader_role='public',
    )
    assert status == 500
    job = get_parse_job(body['parse_job_id'])
    assert job['status'] == 'failed'
    _assert_no_running_jobs()


def test_distinct_hashes_two_executions(monkeypatch):
    from app.ai.document_intelligence import pipeline as pip

    calls = {'n': 0}

    def fake_resume(**kwargs):
        calls['n'] += 1
        return {'status': 'ok'}, 200

    monkeypatch.setattr(pip, '_run_resume', lambda *a, **k: fake_resume())
    monkeypatch.setattr(pip, 'apply_hardware_env', lambda: None)
    pip.run_document_intelligence(
        'resume', b'aaa', 'a.pdf', uploader_id='PUB1', uploader_role='public'
    )
    pip.run_document_intelligence(
        'resume', b'bbb', 'b.pdf', uploader_id='PUB2', uploader_role='public'
    )
    assert calls['n'] == 2
    _assert_no_running_jobs()
    assert len(parse_job_statuses_for_tests()) == 2
