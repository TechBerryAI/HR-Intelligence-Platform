"""
Resume and Job Description Parsing Routes
"""
import os
import time
import uuid
from collections import defaultdict, deque
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from app.domains.identity.authorization.rbac import get_user_id, get_role, STAFF_ROLES
from app.api.middleware.auth import authenticate_token, require_recruiter
from app.ai.toon.runtime import toon_loads_flex
from app.domains.recruitment.services.parsing_storage import (
    compute_file_hash,
    store_raw_file,
    validate_toon_format,
    store_parsed_resume,
    store_parsed_jd,
    get_cached_parsing_result
)
from app.ai.parser.text_extraction import extract_text
from app.integrations.openai.llm_service import call_llm, classify_document

parsing_bp = Blueprint('parsing', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Simple in-memory rate limit for public resume parse: N requests per window per IP
_PUBLIC_PARSE_LIMIT = int(os.getenv('PUBLIC_PARSE_RATE_LIMIT', '10'))
_PUBLIC_PARSE_WINDOW_SEC = int(os.getenv('PUBLIC_PARSE_RATE_WINDOW_SEC', '600'))
_public_parse_hits: dict[str, deque] = defaultdict(deque)

MIME_TYPE_MAP = {
    'pdf': 'application/pdf',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'doc': 'application/msword'
}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _reject_legacy_doc(filename):
    """Reject legacy .doc uploads with a clear message."""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext == 'doc':
        return jsonify({
            'status': 'error',
            'error': 'Legacy .doc format is not supported. Please use DOCX or PDF.',
        }), 400
    return None


def get_mime_type(filename):
    """Get MIME type from filename extension"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return MIME_TYPE_MAP.get(ext, 'application/octet-stream')


def _client_ip() -> str:
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def _public_parse_rate_limited(ip: str) -> bool:
    now = time.time()
    q = _public_parse_hits[ip]
    while q and now - q[0] > _PUBLIC_PARSE_WINDOW_SEC:
        q.popleft()
    if len(q) >= _PUBLIC_PARSE_LIMIT:
        return True
    q.append(now)
    return False


def _model_version_label() -> str:
    if os.getenv('AI_USE_GATEWAY', 'true').lower() in ('1', 'true', 'yes'):
        try:
            from app.ai.adapter.runtime_adapter import get_model_version
            return get_model_version()
        except Exception:
            return 'ai-runtime-v1'
    return f"{os.getenv('LLM_PROVIDER', 'xai')}-v1"


def run_resume_parse_pipeline(
    file_data: bytes,
    filename: str,
    *,
    uploader_id: str,
    uploader_role: str,
    candidate_id: str | None = None,
    enrichment_context=None,
):
    """
    Shared resume parse: store raw → extract → LLM → store parsed.
    Returns (response_dict, http_status).
    """
    mime_type = get_mime_type(filename)

    if len(file_data) > MAX_FILE_SIZE:
        return {
            'status': 'error',
            'error': f'File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB',
        }, 400

    file_hash = compute_file_hash(file_data)
    cached = get_cached_parsing_result(file_hash, uploader_id, 'resume')
    if cached:
        if candidate_id:
            from app.database.connection.db import db_run
            db_run(
                'UPDATE parsed_resumes SET candidate_id = ? WHERE id = ?',
                (candidate_id, cached['parsed_id']),
            )
        return {
            'status': 'ok',
            'raw_file_id': cached['raw_file_id'],
            'parsed_id': cached['parsed_id'],
            'confidence': cached['confidence'],
            'toon': cached['toon'],
            'is_duplicate': True,
            'model_version': cached['model_version'],
            'public_uploader_id': uploader_id if uploader_role == 'public' else None,
        }, 200

    raw_file_record = store_raw_file(
        uploader_id,
        uploader_role,
        file_data,
        filename,
        mime_type,
        None,
    )
    raw_file_id = raw_file_record['id']

    try:
        raw_text = extract_text(file_data, filename)
    except Exception as e:
        return {'status': 'error', 'error': f'Text extraction failed: {str(e)}'}, 400

    text_length = len(raw_text.strip()) if raw_text else 0
    if not raw_text or text_length < 30:
        error_msg = 'Could not extract sufficient text from document'
        if text_length > 0:
            error_msg += (
                f'. Only extracted {text_length} characters. '
                'The document may be image-based (scanned) or corrupted.'
            )
        else:
            error_msg += (
                '. The document may be image-based (scanned), corrupted, '
                'or in an unsupported format.'
            )
        return {'status': 'error', 'error': error_msg}, 400

    doc_type = classify_document(raw_text)
    if doc_type == 'unknown':
        print("[WARNING] Document type unclear, proceeding as resume")

    try:
        toon = call_llm(raw_text, 'resume', enrichment_context=enrichment_context)
    except Exception as e:
        return {'status': 'error', 'error': f'LLM parsing failed: {str(e)}'}, 500

    from app.domains.recruitment.services.parsing_storage import collect_toon_validation_issues
    from app.ai.parser.pipelines.resume_toon_pipeline import log_validated_resume_toon

    validation_issues = collect_toon_validation_issues(toon, 'resume')
    is_valid, error_msg = validate_toon_format(toon, 'resume')
    log_validated_resume_toon(
        toon,
        valid=is_valid,
        error_msg=error_msg,
        validation_issues=validation_issues,
    )
    if not is_valid:
        return {'status': 'error', 'error': f'Invalid TOON format: {error_msg}'}, 400

    confidence = calculate_confidence(toon, 'resume')
    model_version = _model_version_label()
    parsed_id = store_parsed_resume(
        raw_file_id,
        candidate_id,
        toon,
        raw_text,
        confidence,
        model_version,
    )

    return {
        'status': 'ok',
        'raw_file_id': raw_file_id,
        'parsed_id': parsed_id,
        'confidence': confidence,
        'toon': toon,
        'is_duplicate': False,
        'model_version': model_version,
        'public_uploader_id': uploader_id if uploader_role == 'public' else None,
    }, 200


def calculate_confidence(toon: dict, doc_type: str) -> float:
    """
    Calculate confidence score based on field completeness and quality
    
    Args:
        toon: Parsed TOON data
        doc_type: 'resume' or 'jd'
    
    Returns:
        Confidence score between 0 and 1
    """
    if doc_type == 'resume':
        required_fields = ['person', 'skills', 'experience', 'education']
        optional_fields = ['summary', 'certifications']
        
        score = 0
        max_score = 0
        required_score = 0
        required_max = 0.7  # 4 * 0.175

        # Check required fields (70% weight)
        for field in required_fields:
            max_score += 0.175  # 0.7 / 4
            if field in toon and toon[field]:
                if field == 'person':
                    # Check person sub-fields - more lenient
                    person = toon['person']
                    # Give partial credit if at least name OR email exists
                    if person.get('name') or person.get('email'):
                        if person.get('name') and person.get('email'):
                            score += 0.175  # Full credit for both
                            required_score += 0.175
                        else:
                            score += 0.1  # Partial credit for one
                            required_score += 0.1
                elif isinstance(toon[field], list):
                    if len(toon[field]) > 0:
                        score += 0.175
                        required_score += 0.175
                elif toon[field]:  # Non-list field that exists
                    score += 0.175
                    required_score += 0.175
        
        # Check optional fields (30% weight) - bonuses; missing optional never caps at <100%
        for field in optional_fields:
            max_score += 0.15  # 0.3 / 2
            if field in toon and toon[field]:
                if isinstance(toon[field], list):
                    if len(toon[field]) > 0:
                        score += 0.15
                elif toon[field]:  # Non-list field
                    score += 0.15
        
        # When all required fields are fully present, parsing is complete -> 100%
        if required_score >= required_max:
            return 1.0
        if max_score > 0:
            base_confidence = score / max_score
            has_person = 'person' in toon and toon['person'] and (toon['person'].get('name') or toon['person'].get('email'))
            has_experience = 'experience' in toon and toon['experience'] and isinstance(toon['experience'], list) and len(toon['experience']) > 0
            has_education = 'education' in toon and toon['education'] and isinstance(toon['education'], list) and len(toon['education']) > 0
            
            if has_person and (has_experience or has_education):
                base_confidence = max(base_confidence, 0.65)
            
            return min(base_confidence, 1.0)
        else:
            return 0.5  # Default if no fields checked
    
    else:  # jd
        required_fields = ['title', 'skills', 'responsibilities']
        optional_fields = ['company', 'location', 'qualifications']
        
        score = 0
        max_score = 0
        
        for field in required_fields:
            max_score += 0.233  # 0.7 / 3
            if field in toon and toon[field]:
                score += 0.233
        
        for field in optional_fields:
            max_score += 0.1  # 0.3 / 3
            if field in toon and toon[field]:
                score += 0.1
        
        return min(score / max_score if max_score > 0 else 0.5, 1.0)


@parsing_bp.route('/parse/resume/public', methods=['POST'])
def parse_resume_public():
    """
    Public resume parse for apply-form autofill (no auth).
    Rate-limited by IP. Stores with uploader_role='public'.
    """
    try:
        ip = _client_ip()
        if _public_parse_rate_limited(ip):
            return jsonify({
                'status': 'error',
                'error': 'Too many resume parse requests. Please try again later.',
            }), 429

        if 'file' not in request.files:
            return jsonify({'status': 'error', 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'error': 'No file selected'}), 400

        doc_reject = _reject_legacy_doc(file.filename)
        if doc_reject:
            return doc_reject

        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}',
            }), 400

        file_data = file.read()
        filename = secure_filename(file.filename)
        public_uploader_id = f"PUB{(uuid.uuid4().hex[:16]).upper()}"

        body, status = run_resume_parse_pipeline(
            file_data,
            filename,
            uploader_id=public_uploader_id,
            uploader_role='public',
            candidate_id=None,
            enrichment_context=None,
        )
        return jsonify(body), status
    except Exception as e:
        print(f"Public resume parsing error: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@parsing_bp.route('/parse/resume', methods=['POST'])
@authenticate_token
def parse_resume_upload():
    """
    Upload and parse resume (authenticated staff).
    POST /api/parse/resume
    """
    try:
        current_user = request.user

        if 'file' not in request.files:
            return jsonify({'status': 'error', 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'error': 'No file selected'}), 400

        doc_reject = _reject_legacy_doc(file.filename)
        if doc_reject:
            return doc_reject

        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}',
            }), 400

        file_data = file.read()
        filename = secure_filename(file.filename)

        uploader_id = get_user_id(current_user)
        jwt_role = get_role(current_user)
        if not uploader_id:
            return jsonify({
                'status': 'error',
                'error': 'User ID not found in authentication token',
            }), 401

        uploader_role = 'recruiter' if jwt_role in STAFF_ROLES else 'recruiter'
        candidate_id = request.form.get('candidate_id') or None

        body, status = run_resume_parse_pipeline(
            file_data,
            filename,
            uploader_id=uploader_id,
            uploader_role=uploader_role,
            candidate_id=candidate_id,
            enrichment_context=None,
        )
        return jsonify(body), status
    except Exception as e:
        print(f"Resume parsing error: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@parsing_bp.route('/parse/jd', methods=['POST'])
@authenticate_token
@require_recruiter
def parse_jd_upload():
    """
    Upload and parse job description
    
    POST /api/parse/jd
    Headers: Authorization: Bearer <token>
    Body: multipart/form-data
      - file: JD file (PDF/DOCX)
      - job_id: (optional) link to job posting
    
    Returns:
      {
        "status": "ok",
        "raw_file_id": "uuid",
        "parsed_id": "uuid",
        "confidence": 0.94,
        "toon": {...},
        "is_duplicate": false
      }
    """
    try:
        # Get user from request (set by authenticate_token decorator)
        current_user = request.user
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'status': 'error', 'error': 'No file selected'}), 400

        doc_reject = _reject_legacy_doc(file.filename)
        if doc_reject:
            return doc_reject
        
        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Read file data
        file_data = file.read()
        
        # Check file size
        if len(file_data) > MAX_FILE_SIZE:
            return jsonify({
                'status': 'error',
                'error': f'File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB'
            }), 400
        
        filename = secure_filename(file.filename)
        mime_type = get_mime_type(filename)
        
        # Get uploader info from token (admin/HR)
        # Candidates have 'id', HR has 'hrId'
        uploader_id = get_user_id(current_user)
        jwt_role = get_role(current_user)
        uploader_role = 'recruiter' if jwt_role in STAFF_ROLES else 'candidate'
        
        # Validate uploader_id
        if not uploader_id:
            return jsonify({
                'status': 'error',
                'error': 'User ID not found in authentication token'
            }), 401
        
        # Get optional job_id from form
        job_id = request.form.get('job_id')
        
        # Compute file hash for duplicate detection
        file_hash = compute_file_hash(file_data)
        
        # Check if already parsed (cached result)
        cached = get_cached_parsing_result(file_hash, uploader_id, 'job_description')
        if cached:
            return jsonify({
                'status': 'ok',
                'raw_file_id': cached['raw_file_id'],
                'parsed_id': cached['parsed_id'],
                'confidence': cached['confidence'],
                'toon': cached['toon'],
                'is_duplicate': True,
                'model_version': cached['model_version']
            }), 200
        
        # Store raw file
        raw_file_record = store_raw_file(
            uploader_id,
            uploader_role,
            file_data,
            filename,
            mime_type,
            None  # db connection handled internally
        )
        
        raw_file_id = raw_file_record['id']
        
        # Extract text from file
        try:
            raw_text = extract_text(file_data, filename)
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': f'Text extraction failed: {str(e)}'
            }), 400
        
        # Check if we got sufficient text (lowered threshold and better error message)
        text_length = len(raw_text.strip()) if raw_text else 0
        if not raw_text or text_length < 30:
            # Provide more helpful error message
            error_msg = 'Could not extract sufficient text from document'
            if text_length > 0:
                error_msg += f'. Only extracted {text_length} characters. The document may be image-based (scanned) or corrupted.'
            else:
                error_msg += '. The document may be image-based (scanned), corrupted, or in an unsupported format.'
            return jsonify({
                'status': 'error',
                'error': error_msg
            }), 400
        
        # Call LLM to parse job description (repair → normalize inside call_llm)
        try:
            toon = call_llm(raw_text, 'jd')
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': f'LLM parsing failed: {str(e)}'
            }), 500
        
        # Validate TOON format
        is_valid, error_msg = validate_toon_format(toon, 'job_description')
        from app.ai.parser.pipelines.jd_toon_pipeline import log_validated_jd_toon
        log_validated_jd_toon(toon, valid=is_valid, error_msg=error_msg)
        if not is_valid:
            return jsonify({
                'status': 'error',
                'error': f'Invalid TOON format: {error_msg}'
            }), 400
        
        # Calculate confidence
        confidence = calculate_confidence(toon, 'jd')
        if os.getenv('AI_USE_GATEWAY', 'true').lower() in ('1', 'true', 'yes'):
            try:
                from app.ai.adapter.runtime_adapter import get_model_version
                model_version = get_model_version()
            except Exception:
                model_version = 'ai-runtime-v1'
        else:
            model_version = f"{os.getenv('LLM_PROVIDER', 'xai')}-v1"
        
        # Store parsed result
        parsed_id = store_parsed_jd(
            raw_file_id,
            job_id,
            toon,
            raw_text,
            confidence,
            model_version
        )
        
        return jsonify({
            'status': 'ok',
            'raw_file_id': raw_file_id,
            'parsed_id': parsed_id,
            'confidence': confidence,
            'toon': toon,
            'is_duplicate': False,
            'model_version': model_version
        }), 200
        
    except Exception as e:
        print(f"JD parsing error: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@parsing_bp.route('/parsed/resume/<parsed_id>', methods=['GET'])
@authenticate_token
def get_parsed_resume(parsed_id):
    """Get parsed resume by ID"""
    from app.database.connection.db import db_get
    
    try:
        result = db_get(
            "SELECT id, toon, confidence, model_version, created_at FROM parsed_resumes WHERE id = ?",
            (parsed_id,)
        )
        
        if not result:
            return jsonify({'status': 'error', 'error': 'Parsed resume not found'}), 404
        
        return jsonify({
            'status': 'ok',
            'parsed_id': result['id'],
            'toon': toon_loads_flex(result['toon']),
            'confidence': result['confidence'],
            'model_version': result['model_version'],
            'created_at': result['created_at'].isoformat() if hasattr(result['created_at'], 'isoformat') else str(result['created_at'])
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@parsing_bp.route('/parsed/jd/<parsed_id>', methods=['GET'])
@authenticate_token
def get_parsed_jd(parsed_id):
    """Get parsed job description by ID"""
    from app.database.connection.db import db_get
    
    try:
        result = db_get(
            "SELECT id, toon, confidence, model_version, created_at FROM parsed_jds WHERE id = ?",
            (parsed_id,)
        )
        
        if not result:
            return jsonify({'status': 'error', 'error': 'Parsed JD not found'}), 404
        
        return jsonify({
            'status': 'ok',
            'parsed_id': result['id'],
            'toon': toon_loads_flex(result['toon']),
            'confidence': result['confidence'],
            'model_version': result['model_version'],
            'created_at': result['created_at'].isoformat() if hasattr(result['created_at'], 'isoformat') else str(result['created_at'])
        }), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

