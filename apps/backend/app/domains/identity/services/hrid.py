"""Collision-safe HRID allocation for hr_signup."""
from __future__ import annotations

from app.database.connection.db import db_get


def next_hrid(*, max_attempts: int = 8) -> str:
    """Allocate the next ``HRID###`` via ``hr_signup_hrid_seq`` (retry on clash)."""
    last_err: Exception | None = None
    for _ in range(max_attempts):
        try:
            row = db_get("SELECT nextval('hr_signup_hrid_seq') AS n", ())
            n = int((row or {}).get('n') or 0)
            if n < 1:
                n = 1
            candidate = f'HRID{n:03d}'
            clash = db_get('SELECT hrid FROM hr_signup WHERE hrid = ?', (candidate,))
            if not clash:
                return candidate
        except Exception as exc:
            last_err = exc
            row = db_get(
                "SELECT COALESCE(MAX(CAST(SUBSTRING(hrid FROM 5) AS INT)), 0) AS maxn "
                "FROM hr_signup WHERE hrid ~ ?",
                ('^HRID[0-9]+$',),
            )
            next_num = int(row['maxn']) + 1 if row and row.get('maxn') is not None else 1
            candidate = f'HRID{next_num:03d}'
            clash = db_get('SELECT hrid FROM hr_signup WHERE hrid = ?', (candidate,))
            if not clash:
                return candidate
    if last_err:
        raise last_err
    raise RuntimeError('Failed to allocate unique HRID')
