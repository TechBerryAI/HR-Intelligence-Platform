"""
Utility functions for file parsing workflow
"""
import hashlib
import os
import uuid
import json
from typing import Dict, Any, Optional, Tuple
import requests
from datetime import datetime

PARSING_API_URL = os.getenv('PARSING_API_URL', 'http://localhost:4000')
PARSING_API_KEY = os.getenv('PARSING_API_KEY', 'dev-api-key')
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', './uploads')


def compute_file_hash(file_data: bytes) -> str:
    """
    Compute SHA256 hash of file content for duplicate detection
    """
    return hashlib.sha256(file_data).hexdigest()


def save_file_to_storage(file_data: bytes, filename: str, uploader_id: str) -> str:
    """
    Save file to local storage or S3
    Returns storage URL
    """
    # Create upload directory if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    extension = os.path.splitext(filename)[1]
    storage_filename = f"{uploader_id}_{file_id}{extension}"
    
    # Save file
    file_path = os.path.join(UPLOAD_FOLDER, storage_filename)
    with open(file_path, 'wb') as f:
        f.write(file_data)
    
    # Return storage URL (local path for now, can be S3 URL in production)
    return f"file://{os.path.abspath(file_path)}"


def call_parsing_api(
    file_data: bytes, 
    filename: str, 
    document_type: str,
    raw_file_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Call Parsing API microservice to parse document
    
    Args:
        file_data: Binary file content
        filename: Original filename
        document_type: 'resume' or 'jd'
        raw_file_id: UUID of raw_file record (optional)
    
    Returns:
        Parsing API response dict
    
    Raises:
        requests.exceptions.RequestException: If API call fails
        ValueError: If response is invalid
    """
    endpoint = f"{PARSING_API_URL}/api/v1/parse/{document_type}"
    
    headers = {
        'X-API-Key': PARSING_API_KEY
    }
    
    files = {
        'file': (filename, file_data)
    }
    
    data = {}
    if raw_file_id:
        data['raw_file_id'] = raw_file_id
    
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            files=files,
            data=data,
            timeout=90  # 90 seconds timeout
        )
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.Timeout:
        raise Exception('Parsing API request timed out. Please try again.')
    except requests.exceptions.RequestException as e:
        error_msg = f'Parsing API error: {str(e)}'
        if hasattr(e.response, 'json'):
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', error_msg)
            except:
                pass
        raise Exception(error_msg)


def validate_toon_format(toon: Dict[str, Any], document_type: str) -> Tuple[bool, Optional[str]]:
    """
    Validate TOON format structure
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(toon, dict):
        return False, "TOON must be a dictionary"
    
    if toon.get('type') != document_type:
        return False, f"TOON type mismatch: expected {document_type}, got {toon.get('type')}"
    
    if document_type == 'resume':
        required_fields = ['person', 'skills', 'experience', 'education']
        for field in required_fields:
            if field not in toon:
                return False, f"Missing required field: {field}"
        
        # Validate person object
        if not isinstance(toon.get('person'), dict):
            return False, "person must be a dictionary"
        
        person_fields = ['name', 'email', 'phone']
        for field in person_fields:
            if field not in toon['person']:
                return False, f"Missing person field: {field}"
    
    elif document_type == 'job_description':
        required_fields = ['title', 'location', 'skills', 'responsibilities']
        for field in required_fields:
            if field not in toon:
                return False, f"Missing required field: {field}"
    
    return True, None


def store_raw_file(
    uploader_id: str,
    uploader_role: str,
    file_data: bytes,
    filename: str,
    mime_type: str,
    db_conn
) -> Dict[str, Any]:
    """
    Store raw file metadata in database
    
    Returns:
        Dict with raw_file record data
    """
    from db import db_get, db_run
    
    file_hash = compute_file_hash(file_data)
    
    # Check for duplicate
    existing = db_get(
        """
        SELECT id, storage_url, created_at 
        FROM raw_files 
        WHERE file_hash = ? AND uploader_id = ?
        """,
        (file_hash, uploader_id)
    )
    
    if existing:
        return {
            'id': existing['id'],
            'storage_url': existing['storage_url'],
            'is_duplicate': True,
            'created_at': existing['created_at']
        }
    
    # Save file to storage
    storage_url = save_file_to_storage(file_data, filename, uploader_id)
    
    # Insert into database
    raw_file_id = str(uuid.uuid4())
    db_run(
        """
        INSERT INTO raw_files 
        (id, uploader_id, uploader_role, original_filename, storage_url, mime_type, file_hash, size_bytes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (raw_file_id, uploader_id, uploader_role, filename, storage_url, mime_type, file_hash, len(file_data))
    )
    
    return {
        'id': raw_file_id,
        'storage_url': storage_url,
        'is_duplicate': False,
        'created_at': datetime.utcnow().isoformat()
    }


def store_parsed_resume(
    raw_file_id: str,
    candidate_id: Optional[str],
    toon: Dict[str, Any],
    full_text: str,
    confidence: float,
    model_version: str
) -> str:
    """
    Store parsed resume in database
    
    Returns:
        parsed_id (UUID)
    """
    from db import db_run
    
    parsed_id = str(uuid.uuid4())
    toon_json = json.dumps(toon)
    
    db_run(
        """
        INSERT INTO parsed_resumes 
        (id, raw_file_id, candidate_id, toon, full_text, confidence, model_version)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (parsed_id, raw_file_id, candidate_id, toon_json, full_text, confidence, model_version)
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
    from db import db_run
    
    parsed_id = str(uuid.uuid4())
    toon_json = json.dumps(toon)
    
    db_run(
        """
        INSERT INTO parsed_jds 
        (id, raw_file_id, job_id, toon, full_text, confidence, model_version)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (parsed_id, raw_file_id, job_id, toon_json, full_text, confidence, model_version)
    )
    
    return parsed_id


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
    from db import db_get
    
    table = 'parsed_resumes' if document_type == 'resume' else 'parsed_jds'
    
    result = db_get(
        f"""
        SELECT p.id, p.toon, p.confidence, p.model_version, p.created_at, r.id as raw_file_id
        FROM {table} p
        INNER JOIN raw_files r ON p.raw_file_id = r.id
        WHERE r.file_hash = ? AND r.uploader_id = ?
        ORDER BY p.created_at DESC
        """,
        (file_hash, uploader_id)
    )
    
    if result:
        return {
            'parsed_id': result['id'],
            'raw_file_id': result['raw_file_id'],
            'toon': json.loads(result['toon']),
            'confidence': result['confidence'],
            'model_version': result['model_version'],
            'is_cached': True
        }
    
    return None

