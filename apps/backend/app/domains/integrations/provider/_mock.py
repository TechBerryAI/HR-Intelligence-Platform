"""Shared mock helpers for placeholder providers."""
from __future__ import annotations

import itertools
import threading
from typing import Dict

_lock = threading.Lock()
_counters: Dict[str, itertools.count] = {}


def next_external_id(prefix: str, start: int = 100001) -> str:
    with _lock:
        if prefix not in _counters:
            _counters[prefix] = itertools.count(start)
        n = next(_counters[prefix])
    return f'{prefix}-{n}'
