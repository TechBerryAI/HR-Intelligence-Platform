"""Cascade-delete a job and dependent recruitment rows.

``applications.job_id`` and ``matches.job_id`` are NO ACTION, so a bare
``DELETE FROM jobs`` fails when applicants or matches exist. Child rows of
applications (e.g. interviews) cascade from applications.
"""
from __future__ import annotations

from app.database.connection.db import get_conn


def cascade_delete_job(job_id: str) -> None:
    """Delete matches + applications for the job, then the job row (one transaction)."""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                'UPDATE applications SET latest_match_id = NULL WHERE job_id = %s',
                (job_id,),
            )
            cursor.execute('DELETE FROM matches WHERE job_id = %s', (job_id,))
            cursor.execute('DELETE FROM applications WHERE job_id = %s', (job_id,))
            cursor.execute('DELETE FROM jobs WHERE jdid = %s', (job_id,))
