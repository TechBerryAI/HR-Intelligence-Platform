"""Legacy .media copy must not block Flask /health (WSL /mnt/d trees)."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core import media_storage as ms


@pytest.fixture(autouse=True)
def _reset_migrate():
    ms.reset_media_migrate_state_for_tests()
    yield
    ms.reset_media_migrate_state_for_tests()


def test_get_media_root_does_not_wait_for_copy(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    legacy = repo / '.media' / 'uploads'
    legacy.mkdir(parents=True)
    (legacy / 'resume.pdf').write_bytes(b'%PDF-legacy')
    dest = tmp_path / 'hcip-media'
    monkeypatch.setenv('MEDIA_ROOT', str(dest))
    monkeypatch.setattr(ms, '_REPO_ROOT', repo)

    gate = threading.Event()
    real_copy = ms.shutil.copy2

    def blocked_copy(src, dst, *args, **kwargs):
        gate.wait(timeout=5)
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(ms.shutil, 'copy2', blocked_copy)

    t0 = time.perf_counter()
    root = ms.get_media_root()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.75
    assert root == dest.resolve()
    assert not (dest / 'uploads' / 'resume.pdf').is_file()

    gate.set()
    deadline = time.time() + 5
    while time.time() < deadline:
        if (dest / 'uploads' / 'resume.pdf').is_file() and (
            dest / '.migrated_from_repo_dot_media'
        ).is_file():
            break
        time.sleep(0.05)
    assert (dest / 'uploads' / 'resume.pdf').read_bytes() == b'%PDF-legacy'
    assert (dest / '.migrated_from_repo_dot_media').is_file()


def test_marker_skips_reschedule(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    (repo / '.media' / 'uploads').mkdir(parents=True)
    (repo / '.media' / 'uploads' / 'a.pdf').write_bytes(b'x')
    dest = tmp_path / 'media'
    dest.mkdir()
    (dest / '.migrated_from_repo_dot_media').write_text('done\n', encoding='utf-8')
    monkeypatch.setenv('MEDIA_ROOT', str(dest))
    monkeypatch.setattr(ms, '_REPO_ROOT', repo)

    started = {'n': 0}
    real_thread = threading.Thread

    class CountingThread(real_thread):
        def start(self):
            started['n'] += 1
            return super().start()

    monkeypatch.setattr(ms.threading, 'Thread', CountingThread)
    ms.get_media_root()
    assert started['n'] == 0


def test_moved_txt_writes_marker_without_copy(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    legacy = repo / '.media'
    legacy.mkdir(parents=True)
    (legacy / 'MOVED.txt').write_text('already moved\n', encoding='utf-8')
    (legacy / 'uploads').mkdir()
    (legacy / 'uploads' / 'old.pdf').write_bytes(b'old')
    dest = tmp_path / 'media'
    dest.mkdir()
    monkeypatch.setenv('MEDIA_ROOT', str(dest))
    monkeypatch.setattr(ms, '_REPO_ROOT', repo)

    copied = {'n': 0}
    real_copy = ms.shutil.copy2

    def count_copy(src, dst, *args, **kwargs):
        copied['n'] += 1
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(ms.shutil, 'copy2', count_copy)
    ms.get_media_root()
    deadline = time.time() + 3
    while time.time() < deadline:
        if (dest / '.migrated_from_repo_dot_media').is_file():
            break
        time.sleep(0.05)
    assert (dest / '.migrated_from_repo_dot_media').is_file()
    assert copied['n'] == 0
    assert not (dest / 'uploads' / 'old.pdf').exists()
