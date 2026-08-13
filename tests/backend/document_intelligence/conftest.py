"""Ensure synthetic gold lake is generated from version-controlled source before collection."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVAL = ROOT / 'ai' / 'eval'


def pytest_configure(config):
    if str(EVAL) not in sys.path:
        sys.path.insert(0, str(EVAL))
    from generate_gold_lake import main as generate_gold_lake

    generate_gold_lake()
