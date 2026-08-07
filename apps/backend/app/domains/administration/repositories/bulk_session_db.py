"""
Persistent bulk parse session storage (PostgreSQL).
Used alongside in-memory job store during transition.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any

from app.database.connection.db import db_all, db_get, db_run


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_empty_session(created_by: str) -> str | None:
    """Create a Queued bulk_parse_sessions row with zero files. Returns session UUID or None."""
    if not created_by:
        return None
    session_id = str(uuid.uuid4())
    try:
        db_run(
            """
            INSERT INTO bulk_parse_sessions (
                id, created_by, status, progress, total_files, started_at
            ) VALUES (?, ?, 'Queued', 0, 0, NOW())
            """,
            (session_id, created_by),
        )
        return session_id
    except Exception as e:
        print(f"[bulk_session_db] create_empty_session failed: {e}")
        return None


def add_session_files(session_id: str, filenames: list[str], file_data: list[bytes]) -> None:
    """Append Queued file rows for a session (chunked upload)."""
    if not session_id or not filenames:
        return
    try:
        for fname, data in zip(filenames, file_data):
            file_id = str(uuid.uuid4())
            db_run(
                """
                INSERT INTO bulk_parse_files (
                    id, session_id, original_filename, file_hash, status
                ) VALUES (?, ?, ?, ?, 'Queued')
                """,
                (file_id, session_id, fname, _hash_bytes(data)),
            )
    except Exception as e:
        print(f"[bulk_session_db] add_session_files failed: {e}")


def bump_session_total(session_id: str, total_files: int) -> None:
    try:
        db_run(
            """
            UPDATE bulk_parse_sessions
            SET total_files = ?, updated_at = NOW()
            WHERE id = ?
            """,
            (total_files, session_id),
        )
    except Exception as e:
        print(f"[bulk_session_db] bump_session_total failed: {e}")


def mark_session_running(session_id: str, total_files: int) -> None:
    try:
        db_run(
            """
            UPDATE bulk_parse_sessions
            SET status = 'Running', total_files = ?, progress = 0,
                started_at = COALESCE(started_at, NOW()), updated_at = NOW()
            WHERE id = ?
            """,
            (total_files, session_id),
        )
    except Exception as e:
        print(f"[bulk_session_db] mark_session_running failed: {e}")


def create_session(created_by: str, filenames: list[str], file_data: list[bytes]) -> str | None:
    """Create bulk_parse_sessions + bulk_parse_files rows. Returns session UUID or None on failure."""
    if not created_by:
        return None
    session_id = str(uuid.uuid4())
    total = len(filenames)
    try:
        db_run(
            """
            INSERT INTO bulk_parse_sessions (
                id, created_by, status, progress, total_files, started_at
            ) VALUES (?, ?, 'Running', 0, ?, NOW())
            """,
            (session_id, created_by, total),
        )
        for fname, data in zip(filenames, file_data):
            file_id = str(uuid.uuid4())
            db_run(
                """
                INSERT INTO bulk_parse_files (
                    id, session_id, original_filename, file_hash, status
                ) VALUES (?, ?, ?, ?, 'Queued')
                """,
                (file_id, session_id, fname, _hash_bytes(data)),
            )
        return session_id
    except Exception as e:
        print(f"[bulk_session_db] create_session failed: {e}")
        return None



def get_session_owner(session_id: str) -> str | None:
    row = db_get(
        "SELECT created_by FROM bulk_parse_sessions WHERE id = ?",
        (session_id,),
    )
    return row.get("created_by") if row else None


def update_file_status(
    session_id: str,
    filename: str,
    status: str,
    error_message: str | None = None,
    processing_time_ms: int | None = None,
    raw_file_id: str | None = None,
    parsed_resume_id: str | None = None,
) -> None:
    try:
        if status == 'Failed':
            db_run(
                """
                UPDATE bulk_parse_files
                SET status = ?, error_message = ?, processing_time_ms = ?,
                    retry_count = retry_count + 1, updated_at = NOW(),
                    raw_file_id = COALESCE(?, raw_file_id),
                    parsed_resume_id = COALESCE(?, parsed_resume_id)
                WHERE session_id = ? AND original_filename = ?
                """,
                (
                    status,
                    error_message,
                    processing_time_ms,
                    raw_file_id,
                    parsed_resume_id,
                    session_id,
                    filename,
                ),
            )
        else:
            db_run(
                """
                UPDATE bulk_parse_files
                SET status = ?, error_message = ?, processing_time_ms = ?, updated_at = NOW(),
                    raw_file_id = COALESCE(?, raw_file_id),
                    parsed_resume_id = COALESCE(?, parsed_resume_id)
                WHERE session_id = ? AND original_filename = ?
                """,
                (
                    status,
                    error_message,
                    processing_time_ms,
                    raw_file_id,
                    parsed_resume_id,
                    session_id,
                    filename,
                ),
            )
    except Exception as e:
        print(f"[bulk_session_db] update_file_status failed: {e}")


def link_session_file(
    session_id: str,
    filename: str,
    *,
    raw_file_id: str | None = None,
    parsed_resume_id: str | None = None,
) -> None:
    """Attach raw/parsed FKs for a bulk_parse_files row."""
    if not session_id or not filename:
        return
    if not raw_file_id and not parsed_resume_id:
        return
    try:
        db_run(
            """
            UPDATE bulk_parse_files
            SET raw_file_id = COALESCE(?, raw_file_id),
                parsed_resume_id = COALESCE(?, parsed_resume_id),
                updated_at = NOW()
            WHERE session_id = ? AND original_filename = ?
            """,
            (raw_file_id, parsed_resume_id, session_id, filename),
        )
    except Exception as e:
        print(f"[bulk_session_db] link_session_file failed: {e}")


def update_session_progress(
    session_id: str,
    processed: int,
    successful: int,
    failed: int,
    status: str | None = None,
    error_summary: str | None = None,
) -> None:
    total_row = db_get(
        "SELECT total_files FROM bulk_parse_sessions WHERE id = ?",
        (session_id,),
    )
    total = (total_row or {}).get("total_files") or 0
    progress = int((processed / total) * 100) if total else 0
    try:
        if status == "Completed":
            db_run(
                """
                UPDATE bulk_parse_sessions
                SET progress = ?, successful_files = ?, failed_files = ?,
                    status = ?, completed_at = NOW(), updated_at = NOW(),
                    error_summary = ?
                WHERE id = ?
                """,
                (progress, successful, failed, status, error_summary, session_id),
            )
        elif status:
            db_run(
                """
                UPDATE bulk_parse_sessions
                SET progress = ?, successful_files = ?, failed_files = ?,
                    status = ?, updated_at = NOW(), error_summary = ?
                WHERE id = ?
                """,
                (progress, successful, failed, status, error_summary, session_id),
            )
        else:
            db_run(
                """
                UPDATE bulk_parse_sessions
                SET progress = ?, successful_files = ?, failed_files = ?, updated_at = NOW()
                WHERE id = ?
                """,
                (progress, successful, failed, session_id),
            )
    except Exception as e:
        print(f"[bulk_session_db] update_session_progress failed: {e}")


def finalize_session(session_id: str, started_at: float, successful: int, failed: int) -> None:
    elapsed_ms = int((time.time() - started_at) * 1000)
    try:
        db_run(
            """
            UPDATE bulk_parse_sessions
            SET status = 'Completed', processing_time_ms = ?, completed_at = NOW(), updated_at = NOW()
            WHERE id = ?
            """,
            (elapsed_ms, session_id),
        )
        update_session_progress(session_id, successful + failed, successful, failed, status="Completed")
    except Exception as e:
        print(f"[bulk_session_db] finalize_session failed: {e}")


def get_session_progress(session_id: str) -> dict[str, Any] | None:
    row = db_get(
        """
        SELECT id, created_by, status, progress, total_files,
               successful_files, failed_files, processing_time_ms, error_summary
        FROM bulk_parse_sessions WHERE id = ?
        """,
        (session_id,),
    )
    if not row:
        return None
    failed_rows = db_all(
        """
        SELECT original_filename, error_message FROM bulk_parse_files
        WHERE session_id = ? AND status = 'Failed'
        """,
        (session_id,),
    )
    success_rows = db_all(
        """
        SELECT original_filename FROM bulk_parse_files
        WHERE session_id = ? AND status = 'Completed'
        """,
        (session_id,),
    )
    status_map = {
        "Queued": "pending",
        "Running": "started",
        "Completed": "completed",
        "Failed": "failed",
        "Cancelled": "cancelled",
    }
    failed_details = []
    for r in failed_rows:
        err = (r.get("error_message") or "").strip()
        code = "exception"
        low = err.lower()
        if "unsupported format" in low or "legacy .doc" in low:
            code = "unsupported_format"
        elif "insufficient text" in low:
            code = "insufficient_text"
        elif "empty fields" in low:
            code = "empty_fields"
        elif "validation" in low or "person." in low or "missing" in low:
            code = "validation"
        elif "parse" in low or "llm" in low or "failed (parse" in low:
            code = "llm"
        failed_details.append(
            {
                "filename": r.get("original_filename"),
                "error": err,
                "code": code,
            }
        )
    return {
        "status": status_map.get(row.get("status"), row.get("status", "").lower()),
        "started_by": row.get("created_by"),
        "total_files": row.get("total_files", 0),
        "processed_files": (row.get("successful_files") or 0) + (row.get("failed_files") or 0),
        "failed_files": row.get("failed_files", 0),
        "message": row.get("error_summary") or "",
        "failed_filenames": [r.get("original_filename") for r in failed_rows],
        "success_filenames": [r.get("original_filename") for r in success_rows],
        "failed_details": failed_details,
        "from_db": True,
    }
