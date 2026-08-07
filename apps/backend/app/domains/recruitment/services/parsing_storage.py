"""
Utility functions for file parsing workflow. TOON is the exclusive format for parsed data.
"""
import hashlib
import os
import uuid
from typing import Dict, Any, Optional, Tuple

from app.ai.toon.runtime import toon_dumps, toon_loads_flex
from app.core import media_storage
from app.core.timing import timing
from datetime import datetime

# Back-compat: callers/tests may read UPLOAD_FOLDER; maps to MEDIA_ROOT/uploads
UPLOAD_FOLDER = str(media_storage.uploads_dir())


def compute_file_hash(file_data: bytes) -> str:
    """
    Compute SHA256 hash of file content for duplicate detection
    """
    return hashlib.sha256(file_data).hexdigest()


def save_file_to_storage(file_data: bytes, filename: str, uploader_id: str) -> str:
    """
    Durable media volume under MEDIA_ROOT (S3-swappable later).
    Writes are SHA-256 verified on disk before the key is returned.
    """
    file_id = str(uuid.uuid4())
    extension = os.path.splitext(filename)[1]
    storage_filename = f"{uploader_id}_{file_id}{extension}"
    relative = f"uploads/{storage_filename}"
    return media_storage.put(relative, file_data, verify=True)


def _as_bytes(value) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, bytes):
        return value
    return None


def load_raw_file_bytes(raw_file_id: str) -> bytes | None:
    """
    Load original upload bytes.

    Prefers MEDIA_ROOT via ``storage_url``, verifying ``file_hash`` from the
    catalog. Falls back to legacy ``raw_files.file_data`` BYTEA only when media
    is missing or fails verification (migration window).
    """
    from app.database.connection.db import db_get

    row = db_get(
        """
        SELECT file_data, storage_url, storage_backend, file_hash
        FROM raw_files WHERE id = ?
        """,
        (raw_file_id,),
    )
    if not row:
        return None
    expected = (row.get('file_hash') or '').strip().lower()
    storage_url = row.get('storage_url')
    if storage_url:
        try:
            if expected:
                return media_storage.read_verified(storage_url, expected)
            return media_storage.read_bytes(storage_url)
        except media_storage.MediaIntegrityError as exc:
            print(f'[media] checksum mismatch raw_files.id={raw_file_id}: {exc}')
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f'[media] miss raw_files.id={raw_file_id} key={storage_url!r}: {exc}')

    blob = _as_bytes(row.get('file_data'))
    if blob is None:
        return None
    if expected and compute_file_hash(blob) != expected:
        print(
            f'[media] BYTEA checksum mismatch raw_files.id={raw_file_id} '
            f'(catalog={expected})'
        )
        return None
    return blob


@timing
def store_raw_file(
    uploader_id: str,
    uploader_role: str,
    file_data: bytes,
    filename: str,
    mime_type: str,
    db_conn,
    *,
    bulk_session_id: str | None = None,
) -> Dict[str, Any]:
    """
    Catalog in Postgres; bytes on MEDIA_ROOT with checksum verification.

    ``file_data`` BYTEA is left NULL for new rows.
    """
    from app.database.connection.db import db_get, db_run
    
    if not isinstance(file_data, (bytes, bytearray, memoryview)):
        raise TypeError('file_data must be bytes')
    payload = bytes(file_data)
    file_hash = compute_file_hash(payload)
    
    # Check for duplicate
    existing = db_get(
        """
        SELECT id, storage_url, created_at, file_data, storage_backend, file_hash
        FROM raw_files 
        WHERE file_hash = ? AND uploader_id = ?
        """,
        (file_hash, uploader_id)
    )
    
    if existing:
        storage_url = existing.get('storage_url') or ''
        media_ok = bool(storage_url) and media_storage.verify(storage_url, file_hash)
        if not media_ok:
            storage_url = save_file_to_storage(payload, filename, uploader_id)
            db_run(
                """
                UPDATE raw_files
                SET storage_url = ?, storage_backend = 'media', size_bytes = ?
                WHERE id = ?
                """,
                (storage_url, len(payload), existing['id']),
            )
        if bulk_session_id:
            try:
                db_run(
                    'UPDATE raw_files SET bulk_session_id = COALESCE(bulk_session_id, ?) WHERE id = ?',
                    (bulk_session_id, existing['id']),
                )
            except Exception:
                pass
        return {
            'id': existing['id'],
            'storage_url': storage_url,
            'file_hash': file_hash,
            'is_duplicate': True,
            'created_at': existing['created_at'],
        }
    
    storage_url = save_file_to_storage(payload, filename, uploader_id)
    
    raw_file_id = str(uuid.uuid4())
    if bulk_session_id:
        try:
            db_run(
                """
                INSERT INTO raw_files 
                (id, uploader_id, uploader_role, original_filename, storage_url, mime_type,
                 file_hash, size_bytes, file_data, storage_backend, bulk_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'media', ?)
                """,
                (
                    raw_file_id, uploader_id, uploader_role, filename, storage_url,
                    mime_type, file_hash, len(payload), bulk_session_id,
                ),
            )
        except Exception:
            db_run(
                """
                INSERT INTO raw_files 
                (id, uploader_id, uploader_role, original_filename, storage_url, mime_type,
                 file_hash, size_bytes, file_data, storage_backend)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'media')
                """,
                (raw_file_id, uploader_id, uploader_role, filename, storage_url, mime_type, file_hash, len(payload))
            )
    else:
        db_run(
            """
            INSERT INTO raw_files 
            (id, uploader_id, uploader_role, original_filename, storage_url, mime_type,
             file_hash, size_bytes, file_data, storage_backend)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'media')
            """,
            (raw_file_id, uploader_id, uploader_role, filename, storage_url, mime_type, file_hash, len(payload))
        )
    
    return {
        'id': raw_file_id,
        'storage_url': storage_url,
        'file_hash': file_hash,
        'is_duplicate': False,
        'created_at': datetime.utcnow().isoformat()
    }


def collect_toon_validation_issues(toon: Dict[str, Any], document_type: str) -> list[str]:
    """Collect every TOON validation failure without short-circuiting."""
    issues: list[str] = []

    if not isinstance(toon, dict):
        return ["TOON must be a dictionary"]

    if toon.get('type') != document_type:
        issues.append(f"TOON type mismatch: expected {document_type}, got {toon.get('type')}")

    if document_type == 'resume':
        required_fields = ['person', 'skills', 'experience', 'education']
        for field in required_fields:
            if field not in toon:
                issues.append(f"Missing required field: {field}")

        person = toon.get('person') if isinstance(toon.get('person'), dict) else {}
        if not isinstance(toon.get('person'), dict):
            issues.append("person must be a dictionary")
        else:
            person_fields = ['name', 'email', 'phone']
            for field in person_fields:
                if field not in person:
                    issues.append(f"Missing person field: {field}")

            optional_url_fields = ['linkedin', 'github', 'portfolio', 'website', 'twitter']
            for field in optional_url_fields:
                if field in person and not isinstance(person[field], (str, type(None))):
                    issues.append(f"person.{field} must be a string or null")

            if 'otherUrls' in person and not isinstance(person.get('otherUrls'), (list, type(None))):
                issues.append("person.otherUrls must be an array or null")

        if not str(person.get('name') or '').strip():
            issues.append("person.name must not be empty")
        if not str(person.get('email') or '').strip():
            issues.append("person.email must not be empty")

        # Skills preferred but not mandatory when identity + (experience or education) exist
        skills = toon.get('skills')
        has_skills = isinstance(skills, list) and len(skills) > 0
        if 'skills' not in toon:
            issues.append("Missing required field: skills")
        elif not isinstance(skills, list):
            issues.append("skills must be an array")
        elif not has_skills:
            exp = toon.get('experience') if isinstance(toon.get('experience'), list) else []
            edu = toon.get('education') if isinstance(toon.get('education'), list) else []
            has_history = len(exp) > 0 or len(edu) > 0
            name_ok = bool(str(person.get('name') or '').strip())
            email_ok = bool(str(person.get('email') or '').strip())
            if not (name_ok and email_ok and has_history):
                issues.append("skills must be a non-empty array")

    elif document_type == 'job_description':
        required_fields = ['title', 'location', 'skills', 'responsibilities']
        for field in required_fields:
            if field not in toon:
                issues.append(f"Missing required field: {field}")
        if not (toon.get('title') or '').strip():
            issues.append("title must not be empty")
        if not (toon.get('location') or '').strip():
            issues.append("location must not be empty")
        if not isinstance(toon.get('skills'), list) or len(toon.get('skills') or []) == 0:
            issues.append("skills must be a non-empty array")
        if not isinstance(toon.get('responsibilities'), list) or len(toon.get('responsibilities') or []) == 0:
            issues.append("responsibilities must be a non-empty array")

    return issues


def validate_toon_format(toon: Dict[str, Any], document_type: str) -> Tuple[bool, Optional[str]]:
    """
    Validate TOON format structure
    
    Returns:
        (is_valid, error_message)
    """
    issues = collect_toon_validation_issues(toon, document_type)
    if issues:
        return False, "; ".join(issues)
    return True, None


def _bulk_resume_has_excel_signal(toon: Dict[str, Any]) -> bool:
    """True when there is enough signal to keep a bulk Excel row."""
    if not isinstance(toon, dict):
        return False
    person = toon.get('person') if isinstance(toon.get('person'), dict) else {}
    name = str(person.get('name') or '').strip()
    email = str(person.get('email') or '').strip()
    phone = str(person.get('phone') or '').strip()
    skills = toon.get('skills') if isinstance(toon.get('skills'), list) else []
    exp = toon.get('experience') if isinstance(toon.get('experience'), list) else []
    return bool(name or email or phone or skills or exp)


def validate_toon_format_bulk(
    toon: Dict[str, Any], document_type: str = 'resume'
) -> Tuple[bool, Optional[str], str]:
    """
    Bulk-relaxed validation for Excel export.

    Accepts a row when name OR email/phone OR skills/experience exist.
    Does not require non-empty email. Strict issues become ParseNotes.

    Returns:
        (accept_row, notes_or_error, parse_status) where parse_status is
        'ok' | 'partial' | 'failed'.
    """
    if not isinstance(toon, dict):
        return False, 'TOON must be a dictionary', 'failed'

    if document_type != 'resume':
        is_valid, error_msg = validate_toon_format(toon, document_type)
        return is_valid, error_msg, 'ok' if is_valid else 'failed'

    if not _bulk_resume_has_excel_signal(toon):
        return False, 'Insufficient fields for Excel (need name, contact, skills, or experience)', 'failed'

    is_valid, error_msg = validate_toon_format(toon, document_type)
    if is_valid:
        return True, None, 'ok'
    return True, error_msg or 'Partial validation', 'partial'


def store_parsed_resume(
    raw_file_id: str,
    candidate_id: Optional[str],
    toon: Dict[str, Any],
    full_text: str,
    confidence: float,
    model_version: str,
    *,
    bulk_session_id: str | None = None,
) -> str:
    """
    Store parsed resume in database
    
    Returns:
        parsed_id (UUID)
    """
    from app.database.connection.db import db_run
    
    parsed_id = str(uuid.uuid4())
    toon_text = toon_dumps(toon)
    
    if bulk_session_id:
        try:
            db_run(
                """
                INSERT INTO parsed_resumes 
                (id, raw_file_id, candidate_id, toon, full_text, confidence, model_version, bulk_session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parsed_id, raw_file_id, candidate_id, toon_text, full_text,
                    confidence, model_version, bulk_session_id,
                ),
            )
            return parsed_id
        except Exception:
            pass

    db_run(
        """
        INSERT INTO parsed_resumes 
        (id, raw_file_id, candidate_id, toon, full_text, confidence, model_version)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (parsed_id, raw_file_id, candidate_id, toon_text, full_text, confidence, model_version)
    )
    
    return parsed_id


def store_parsed_jd(
    raw_file_id: str,
    job_id: Optional[str],
    toon: Dict[str, Any],
    full_text: str,
    confidence: float,
    model_version: str
) -> str:
    """
    Store parsed job description in database
    
    Returns:
        parsed_id (UUID)
    """
    from app.database.connection.db import db_run
    
    parsed_id = str(uuid.uuid4())
    toon_text = toon_dumps(toon)
    
    db_run(
        """
        INSERT INTO parsed_jds 
        (id, raw_file_id, job_id, toon, full_text, confidence, model_version)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (parsed_id, raw_file_id, job_id, toon_text, full_text, confidence, model_version)
    )
    
    return parsed_id


def _cache_model_acceptable(model_version: str | None) -> bool:
    """
    Skip stale cache entries from pre-canonical / broken parsers.
    Require DOCUMENT_INTELLIGENCE_CACHE_TAG (default 'canonical') in model_version.
    """
    import os

    tag = (os.getenv('DOCUMENT_INTELLIGENCE_CACHE_TAG') or 'canonical-v6-jd-coverage').strip()
    if not tag:
        return True
    return tag.lower() in str(model_version or '').lower()


def get_cached_parsing_result(
    file_hash: str,
    uploader_id: str,
    document_type: str
) -> Optional[Dict[str, Any]]:
    """
    Get cached parsing result if file was already processed
    
    Returns:
        Dict with parsed data or None if not found
    """
    from app.database.connection.db import db_get
    
    table = 'parsed_resumes' if document_type == 'resume' else 'parsed_jds'
    
    result = db_get(
        f"""
        SELECT p.id, p.toon, p.confidence, p.model_version, p.created_at, p.full_text, r.id as raw_file_id
        FROM {table} p
        INNER JOIN raw_files r ON p.raw_file_id = r.id
        WHERE r.file_hash = ? AND r.uploader_id = ?
        ORDER BY p.created_at DESC
        """,
        (file_hash, uploader_id)
    )
    
    if result and _cache_model_acceptable(result.get('model_version')):
        return {
            'parsed_id': result['id'],
            'raw_file_id': result['raw_file_id'],
            'toon': toon_loads_flex(result['toon']),
            'confidence': result['confidence'],
            'model_version': result['model_version'],
            'raw_text': result.get('full_text') or '',
            'is_cached': True
        }
    
    return None


def get_cached_parsing_result_by_hash(
    file_hash: str,
    document_type: str,
) -> Optional[Dict[str, Any]]:
    """
    Content-hash cache independent of uploader_id.

    Used for public resume apply (unique PUB* uploader each request) and
    cross-uploader JD/resume reuse of identical bytes. Returns a TOON copy
    reference; callers should treat parsed_id as shared read-only cache hit
    metadata (is_duplicate=True). Does not expose other users' PII beyond
    the parsed document content already derived from the same file bytes.
    """
    from app.database.connection.db import db_get

    table = 'parsed_resumes' if document_type == 'resume' else 'parsed_jds'

    result = db_get(
        f"""
        SELECT p.id, p.toon, p.confidence, p.model_version, p.created_at, p.full_text, r.id as raw_file_id
        FROM {table} p
        INNER JOIN raw_files r ON p.raw_file_id = r.id
        WHERE r.file_hash = ?
        ORDER BY p.created_at DESC
        """,
        (file_hash,),
    )

    if result and _cache_model_acceptable(result.get('model_version')):
        return {
            'parsed_id': result['id'],
            'raw_file_id': result['raw_file_id'],
            'toon': toon_loads_flex(result['toon']),
            'confidence': result['confidence'],
            'model_version': result['model_version'],
            'raw_text': result.get('full_text') or '',
            'is_cached': True,
            'content_hash_hit': True,
        }

    return None


def update_parsed_jd_toon(
    parsed_id: str,
    toon: Dict[str, Any],
    confidence: float,
    model_version: Optional[str] = None,
) -> None:
    """Refresh a stored JD parse after repair/enrichment improvements."""
    from app.database.connection.db import db_run

    toon_text = toon_dumps(toon)
    if model_version:
        db_run(
            """
            UPDATE parsed_jds
            SET toon = ?, confidence = ?, model_version = ?
            WHERE id = ?
            """,
            (toon_text, confidence, model_version, parsed_id),
        )
    else:
        db_run(
            """
            UPDATE parsed_jds
            SET toon = ?, confidence = ?
            WHERE id = ?
            """,
            (toon_text, confidence, parsed_id),
        )

