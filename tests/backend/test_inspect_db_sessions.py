"""Read-only DB session inspector: no live Postgres required."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "inspect_db_sessions.py"
)


def _load_inspector():
    spec = importlib.util.spec_from_file_location("inspect_db_sessions", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inspector_sql_is_select_only():
    mod = _load_inspector()
    statements = mod.inspector_sql_statements()
    assert statements
    for sql in statements:
        assert mod.sql_is_read_only(sql)


def test_inspector_sql_constants_have_no_destructive_tokens():
    mod = _load_inspector()
    blob = "\n".join(mod.inspector_sql_statements()).lower()
    for forbidden in (
        "pg_terminate_backend",
        "pg_cancel_backend",
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "truncate ",
        "alter ",
        "create ",
    ):
        assert forbidden not in blob


def test_sql_is_read_only_rejects_mutations():
    mod = _load_inspector()
    assert not mod.sql_is_read_only("UPDATE pg_stat_activity SET query = 'x'")
    assert not mod.sql_is_read_only("SELECT pg_terminate_backend(123)")
    assert not mod.sql_is_read_only("DELETE FROM pg_stat_activity")
    assert not mod.sql_is_read_only("DROP TABLE x")
    assert not mod.sql_is_read_only("INSERT INTO x VALUES (1)")


@pytest.mark.parametrize(
    "row, expected",
    [
        ({"backend_type": "autovacuum worker", "application_name": ""}, "postgres_internal"),
        ({"backend_type": "client backend", "application_name": "hcip-diagnose"}, "inspector"),
        ({"backend_type": "client backend", "application_name": "hcip-diagnose-20260812"}, "inspector"),
        ({"backend_type": "client backend", "application_name": "hcip-web"}, "hcip_labeled"),
        ({"backend_type": "client backend", "application_name": "hcip-scheduler"}, "hcip_labeled"),
        ({"backend_type": "client backend", "application_name": "hcip-outbox"}, "hcip_labeled"),
        ({"backend_type": "client backend", "application_name": "hcip-migrate"}, "hcip_labeled"),
        ({"backend_type": "client backend", "application_name": ""}, "unknown"),
        ({"backend_type": "client backend", "application_name": "psql"}, "unknown"),
        ({"backend_type": "client backend", "application_name": None}, "unknown"),
    ],
)
def test_classify_session(row, expected):
    mod = _load_inspector()
    assert mod.classify_session(row) == expected
