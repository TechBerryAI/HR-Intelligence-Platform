#!/usr/bin/env python3
"""Quick PostgreSQL connectivity check using apps/backend/.env settings."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "apps" / "backend"
load_dotenv(BACKEND / ".env")

host = os.getenv("POSTGRES_HOST", "localhost")
port = os.getenv("POSTGRES_PORT", "5432")
db = os.getenv("POSTGRES_DB", "HRMS")
user = os.getenv("POSTGRES_USER", "postgres")
password = os.getenv("POSTGRES_PASSWORD", "")

print("Testing PostgreSQL connection...")
print(f"  host={host} port={port} db={db} user={user}")

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg not installed. Run: pip install psycopg[binary]")
    sys.exit(1)

dsn = f"host={host} port={port} dbname={db} user={user} password={password} connect_timeout=5"
try:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), inet_server_addr(), version()")
            row = cur.fetchone()
    print("SUCCESS")
    print(f"  database: {row[0]}")
    print(f"  server:   {row[1]}")
    print(f"  version:  {row[2].split(',')[0]}")
except Exception as exc:
    print(f"FAILED: {exc}")
    msg = str(exc).lower()
    if "no route to host" in msg or "connection refused" in msg or "timeout" in msg:
        print()
        print("Network unreachable. From your PC, verify the VM allows port", port)
        print("  Test:  psql -h", host, "-p", port, "-U", user, "-d", db, '-c "SELECT 1"')
        print("  On VM: run scripts/vm-postgres-setup.sh")
    sys.exit(1)
