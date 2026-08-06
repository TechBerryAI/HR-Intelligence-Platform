"""In-memory async integration queue (swap-ready for Celery/RabbitMQ/Kafka)."""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from app.domains.integrations.config import get_worker_max_workers

logger = logging.getLogger(__name__)


class IntegrationQueue(ABC):
    @abstractmethod
    def enqueue(self, task: dict[str, Any]) -> None:
        ...

    @abstractmethod
    def pending_count(self) -> int:
        ...

    @abstractmethod
    def start(self, handler: Callable[[dict[str, Any]], None]) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...


class InMemoryAsyncQueue(IntegrationQueue):
    """Thread-pool backed queue — replaceable with broker later."""

    def __init__(self, max_workers: int | None = None):
        self._max_workers = max_workers or get_worker_max_workers()
        self._executor: ThreadPoolExecutor | None = None
        self._handler: Callable[[dict[str, Any]], None] | None = None
        self._pending = 0
        self._lock = threading.Lock()
        self._started = False

    def start(self, handler: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._handler = handler
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=self._max_workers,
                    thread_name_prefix='integration-worker',
                )
            self._started = True
        logger.info('[integrations] InMemoryAsyncQueue started (workers=%s)', self._max_workers)

    def stop(self) -> None:
        with self._lock:
            self._started = False
            ex = self._executor
            self._executor = None
        if ex:
            ex.shutdown(wait=False)

    def pending_count(self) -> int:
        with self._lock:
            return self._pending

    def enqueue(self, task: dict[str, Any]) -> None:
        with self._lock:
            if not self._started or not self._executor or not self._handler:
                raise RuntimeError('Integration queue not started')
            self._pending += 1
            handler = self._handler
            executor = self._executor

        def _run():
            try:
                handler(task)
            except Exception:
                logger.exception('[integrations] task failed: %s', task.get('type'))
            finally:
                with self._lock:
                    self._pending = max(0, self._pending - 1)

        executor.submit(_run)


_queue: IntegrationQueue | None = None
_queue_lock = threading.Lock()


def get_queue() -> IntegrationQueue:
    global _queue
    with _queue_lock:
        if _queue is None:
            _queue = InMemoryAsyncQueue()
        return _queue


def set_queue(queue: IntegrationQueue) -> None:
    """Allow tests / future brokers to replace the queue implementation."""
    global _queue
    with _queue_lock:
        _queue = queue
