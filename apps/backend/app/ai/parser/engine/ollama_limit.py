"""Bounded Ollama concurrency shared by interactive semantic + bulk paths."""
from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_semaphore: Optional[threading.Semaphore] = None
_limit: Optional[int] = None


def reset_ollama_limit_for_tests() -> None:
    """Drop the cached semaphore so tests can change OLLAMA_MAX_CONCURRENT."""
    global _semaphore, _limit
    with _LOCK:
        _semaphore = None
        _limit = None


def current_ollama_limit() -> int:
    raw = (os.getenv('OLLAMA_MAX_CONCURRENT') or '').strip()
    if raw:
        try:
            return max(1, min(8, int(raw)))
        except ValueError:
            pass
    from app.ai.parser.engine.hardware import detect_hardware_profile

    return max(1, min(8, detect_hardware_profile().ollama_max_concurrent))


def _get_semaphore() -> threading.Semaphore:
    global _semaphore, _limit
    n = current_ollama_limit()
    with _LOCK:
        if _semaphore is None or _limit != n:
            _semaphore = threading.Semaphore(n)
            _limit = n
            logger.debug('Ollama concurrency limit=%s', n)
        return _semaphore


@contextmanager
def ollama_slot() -> Iterator[None]:
    """Acquire one Ollama slot; always released on cancel/timeout/error."""
    sem = _get_semaphore()
    sem.acquire()
    try:
        yield
    finally:
        sem.release()
