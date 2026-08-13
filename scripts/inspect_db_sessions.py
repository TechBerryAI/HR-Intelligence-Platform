#!/usr/bin/env python3
"""Read-only PostgreSQL session inspector for release verification.

Reports active application connections, client addresses, application names,
truncated queries, long-running transactions, and locks.

Never terminates backends, never issues DML/DDL, never prints secrets.
Exit 1 when unknown (non-hcip) client sessions exist unless --report-only.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

INSPECTOR_ROLE = "diagnose"
INSPECTOR_NAME = "hcip-diagnose"
QUERY_PREVIEW_LEN = 120

# SELECT-only. Do not add pg_terminate_backend / pg_cancel_backend / DML.
SESSIONS_SQL = """
SELECT
    pid,
    usename,
    application_name,
    client_addr::text AS client_addr,
    backend_start,
    state,
    state_change,
    xact_start,
    CASE WHEN xact_start IS NULL THEN NULL ELSE now() - xact_start END AS xact_age,
    CASE
        WHEN state = 'idle in transaction' THEN now() - state_change
        ELSE NULL
    END AS idle_in_xact_age,
    wait_event_type,
    wait_event,
    left(query, 120) AS query,
    backend_type
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY backend_start
"""

LOCKS_SQL = """
SELECT
    l.locktype,
    l.mode,
    l.granted,
    l.pid,
    l.relation::regclass::text AS relation,
    a.application_name,
    a.client_addr::text AS client_addr,
    a.state,
    left(a.query, 80) AS query
FROM pg_locks l
LEFT JOIN pg_stat_activity a ON a.pid = l.pid
WHERE a.datname = current_database()
  AND l.locktype NOT IN ('virtualxid', 'transactionid', 'extend')
ORDER BY l.granted, l.pid
LIMIT 80
"""

LONG_XACT_SQL = """
SELECT
    pid,
    application_name,
    client_addr::text AS client_addr,
    state,
    now() - xact_start AS xact_age,
    left(query, 120) AS query
FROM pg_stat_activity
WHERE datname = current_database()
  AND xact_start IS NOT NULL
  AND now() - xact_start > interval '30 seconds'
ORDER BY xact_start
"""

_FORBIDDEN_SQL_TOKENS = (
    "pg_terminate_backend",
    "pg_cancel_backend",
    "pg_reload_conf",
    "insert ",
    "update ",
    "delete ",
    "drop ",
    "truncate ",
    "alter ",
    "create ",
    "grant ",
    "revoke ",
    "copy ",
    "vacuum ",
    "reindex ",
    "kill ",
)


def inspector_sql_statements() -> tuple[str, ...]:
    return (SESSIONS_SQL, LOCKS_SQL, LONG_XACT_SQL)


def sql_is_read_only(sql: str) -> bool:
    lowered = " ".join(sql.lower().split())
    if not lowered.lstrip().startswith("select"):
        return False
    return not any(token in lowered for token in _FORBIDDEN_SQL_TOKENS)


def classify_session(row: Mapping[str, Any]) -> str:
    """Classify a pg_stat_activity row. Does not invent process owners.

    Returns:
        postgres_internal | inspector | hcip_labeled | unknown
    """
    backend_type = str(row.get("backend_type") or "").strip()
    if backend_type and backend_type != "client backend":
        return "postgres_internal"
    app_name = str(row.get("application_name") or "").strip()
    if app_name == INSPECTOR_NAME or app_name.startswith(f"{INSPECTOR_NAME}-"):
        return "inspector"
    if app_name.startswith("hcip-"):
        return "hcip_labeled"
    return "unknown"


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).replace("\n", " ").strip()
    return text if text else "-"


def _print_rows(title: str, rows: list[Mapping[str, Any]], keys: list[str]) -> None:
    print(f"{title} ({len(rows)})")
    if not rows:
        print("  (none)")
        return
    for row in rows:
        parts = [f"{key}={_fmt(row.get(key))}" for key in keys]
        print("  " + "  ".join(parts))


def _connect():
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
    os.environ["HCIP_PROCESS_ROLE"] = INSPECTOR_ROLE

    from app.database.connection.db import postgres_application_name

    host = os.getenv("POSTGRES_HOST", os.getenv("PGHOST", "localhost"))
    port = os.getenv("POSTGRES_PORT", os.getenv("PGPORT", "5432"))
    dbname = os.getenv("POSTGRES_DB", os.getenv("PGDATABASE", "JobPortal"))
    user = os.getenv("POSTGRES_USER", os.getenv("PGUSER", "postgres"))
    password = os.getenv("POSTGRES_PASSWORD", os.getenv("PGPASSWORD", ""))
    print(f"inspect-db-sessions target={host}:{port}/{dbname} user={user}")
    print(f"inspect-db-sessions application_name={postgres_application_name()}")

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise SystemExit(f"inspect-db-sessions FAIL: psycopg is required ({exc})") from exc

    try:
        conn = psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=10,
            application_name=postgres_application_name(),
            autocommit=True,
        )
    except Exception as exc:
        raise SystemExit(f"inspect-db-sessions FAIL: cannot connect ({type(exc).__name__})") from None
    conn.row_factory = dict_row
    return conn


def inspect_sessions(*, report_only: bool = False) -> int:
    for sql in inspector_sql_statements():
        if not sql_is_read_only(sql):
            raise SystemExit("inspect-db-sessions FAIL: internal SQL is not read-only")

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT inet_client_addr() AS client_addr, pg_backend_pid() AS pid")
            me = cur.fetchone() or {}
            print(f"inspect-db-sessions inspector_client={_fmt(me.get('client_addr'))} pid={_fmt(me.get('pid'))}")

            cur.execute(SESSIONS_SQL)
            sessions = [dict(r) for r in cur.fetchall()]
            cur.execute(LONG_XACT_SQL)
            long_xacts = [dict(r) for r in cur.fetchall()]
            cur.execute(LOCKS_SQL)
            locks = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    buckets: dict[str, list[dict[str, Any]]] = {
        "postgres_internal": [],
        "inspector": [],
        "hcip_labeled": [],
        "unknown": [],
    }
    classified: list[dict[str, Any]] = []
    for row in sessions:
        item = dict(row)
        item["class"] = classify_session(item)
        classified.append(item)
        buckets[item["class"]].append(item)
    sessions = classified

    _print_rows(
        "SESSIONS",
        sessions,
        [
            "class",
            "pid",
            "usename",
            "application_name",
            "client_addr",
            "state",
            "xact_age",
            "idle_in_xact_age",
            "wait_event",
            "query",
        ],
    )
    _print_rows(
        "LONG_TRANSACTIONS>30s",
        long_xacts,
        ["pid", "application_name", "client_addr", "state", "xact_age", "query"],
    )
    _print_rows(
        "LOCKS",
        locks,
        [
            "pid",
            "locktype",
            "mode",
            "granted",
            "relation",
            "application_name",
            "client_addr",
            "state",
        ],
    )

    unknown = buckets["unknown"]
    print("SUMMARY")
    print(f"  hcip_labeled={len(buckets['hcip_labeled'])}")
    print(f"  inspector={len(buckets['inspector'])}")
    print(f"  postgres_internal={len(buckets['postgres_internal'])}")
    print(f"  unknown={len(unknown)}")
    if unknown:
        print("  NEEDS OPERATIONAL VERIFICATION: unknown client sessions")
        print("  Stop those processes on their client_addr hosts before production deploy.")
        print("  This tree cannot terminate remote backends.")
        if report_only:
            print("inspect-db-sessions REPORT: unknown sessions present")
            return 0
        print("inspect-db-sessions FAIL: unknown sessions present")
        return 1
    print("inspect-db-sessions OK: no unknown client sessions")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only PostgreSQL session report for HCIP release verification."
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print the report and exit 0 even when unknown sessions exist.",
    )
    args = parser.parse_args(argv)
    return inspect_sessions(report_only=args.report_only)


if __name__ == "__main__":
    sys.exit(main())
