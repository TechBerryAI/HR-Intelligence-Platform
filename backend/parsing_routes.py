"""
Resume and Job Description Parsing Routes
"""
import os
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from rbac import get_user_id, get_role, STAFF_ROLES, ROLE_CANDIDATE
from utils import authenticate_token
from toon import toon_loads_flex
from parsing_utils import (
    compute_file_hash,
    store_raw_file,
    validate_toon_format,
    store_parsed_resume,
    store_parsed_jd,
    get_cached_parsing_result
)
from text_extraction import extract_text
from llm_service import call_llm, classify_document

parsing_bp = Blueprint('parsing', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

MIME_TYPE_MAP = {
    'pdf': 'application/pdf',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'doc': 'application/msword'
}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_mime_type(filename):
    """Get MIME type from filename extension"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return MIME_TYPE_MAP.get(ext, 'application/octet-stream')


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


@parsing_bp.route('/parse/resume', methods=['POST'])
@authenticate_token
def parse_resume_upload():
    """
    Upload and parse resume
    
    POST /api/parse/resume
    Headers: Authorization: Bearer <token>
    Body: multipart/form-data
      - file: resume file (PDF/DOCX)
      - candidate_id: (optional) link to candidate
    
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
        
        # Get uploader info from token
        # Candidates have 'id', HR has 'hrId'
        uploader_id = get_user_id(current_user)
        jwt_role = get_role(current_user) or ROLE_CANDIDATE
        uploader_role = 'recruiter' if jwt_role in STAFF_ROLES else 'candidate'
        
        # Validate uploader_id
        if not uploader_id:
            return jsonify({
                'status': 'error',
                'error': 'User ID not found in authentication token'
            }), 401
        
        # Get optional candidate_id from form; for candidates, default to authenticated user
        candidate_id = request.form.get('candidate_id')
        if jwt_role == ROLE_CANDIDATE and not candidate_id:
            candidate_id = uploader_id
        
        # Compute file hash for duplicate detection
        file_hash = compute_file_hash(file_data)
        
        # Check if already parsed (cached result)
        cached = get_cached_parsing_result(file_hash, uploader_id, 'resume')
        if cached:
            # Link cached parse to candidate so apply can find it
            if jwt_role == ROLE_CANDIDATE and uploader_id:
                from db import db_run
                db_run(
                    'UPDATE parsed_resumes SET candidate_id = ? WHERE id = ?',
                    (uploader_id, cached['parsed_id'])
                )
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
        
        # Classify document (optional verification)
        doc_type = classify_document(raw_text)
        if doc_type == 'unknown':
            print(f"[WARNING] Document type unclear, proceeding as resume")
        
        # Call LLM to parse resume
        try:
            toon = call_llm(raw_text, 'resume')
            
            # Post-process: Extract URLs from raw text if LLM missed them
            import re
            # More comprehensive URL pattern
            url_pattern = r'(https?://[^\s<>"\'\)]+|www\.[^\s<>"\'\)]+|linkedin\.com/[^\s<>"\'\)]+|github\.com/[^\s<>"\'\)]+|twitter\.com/[^\s<>"\'\)]+|x\.com/[^\s<>"\'\)]+|[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}[^\s<>"\'\)]*)'
            found_urls = re.findall(url_pattern, raw_text, re.IGNORECASE)
            
            # Ensure person object exists
            if 'person' not in toon:
                toon['person'] = {}
            
            # Extract and categorize URLs if not already extracted
            if not toon['person'].get('linkedin'):
                linkedin_urls = [url for url in found_urls if 'linkedin' in url.lower() or 'linked.in' in url.lower()]
                if linkedin_urls:
                    url = linkedin_urls[0].strip('.,;:')
                    toon['person']['linkedin'] = url if url.startswith('http') else f"https://{url}"
            
            if not toon['person'].get('github'):
                github_urls = [url for url in found_urls if 'github' in url.lower()]
                if github_urls:
                    url = github_urls[0].strip('.,;:')
                    toon['person']['github'] = url if url.startswith('http') else f"https://{url}"
            
            if not toon['person'].get('twitter'):
                twitter_urls = [url for url in found_urls if 'twitter' in url.lower() or 'x.com' in url.lower()]
                if twitter_urls:
                    url = twitter_urls[0].strip('.,;:')
                    toon['person']['twitter'] = url if url.startswith('http') else f"https://{url}"
            
            if not toon['person'].get('portfolio') and not toon['person'].get('website'):
                # Look for portfolio/website URLs (not linkedin, github, twitter, email domains, or common email providers)
                excluded_domains = ['linkedin', 'github', 'twitter', 'x.com', 'gmail', 'yahoo', 'outlook', 'hotmail', 'email', 'mail', 'edu', 'ac.', '.gov']
                portfolio_urls = [url for url in found_urls 
                                 if not any(x in url.lower() for x in excluded_domains) and 
                                 '.' in url and len(url) > 5]
                if portfolio_urls:
                    url = portfolio_urls[0].strip('.,;:')
                    toon['person']['portfolio'] = url if url.startswith('http') else f"https://{url}"
            
            # Collect any remaining URLs into otherUrls
            if 'otherUrls' not in toon['person']:
                toon['person']['otherUrls'] = []
            
            # Add URLs that weren't categorized
            categorized = set()
            if toon['person'].get('linkedin'): categorized.add(toon['person']['linkedin'].lower())
            if toon['person'].get('github'): categorized.add(toon['person']['github'].lower())
            if toon['person'].get('twitter'): categorized.add(toon['person']['twitter'].lower())
            if toon['person'].get('portfolio'): categorized.add(toon['person']['portfolio'].lower())
            if toon['person'].get('website'): categorized.add(toon['person']['website'].lower())
            
            for url in found_urls:
                url_clean = url.strip('.,;:')
                if url_clean.lower() not in categorized and url_clean not in toon['person']['otherUrls']:
                    url_final = url_clean if url_clean.startswith('http') else f"https://{url_clean}"
                    toon['person']['otherUrls'].append(url_final)

            # Post-process: Extract location from raw text if LLM did not return it
            if not toon['person'].get('location') or not str(toon['person'].get('location', '')).strip():
                import re
                # Patterns: "Location: Mumbai", "Address: Bangalore", "City: Delhi", "Based in Mumbai"
                location_patterns = [
                    r'(?:location|current\s*location|address|city|based\s*in)\s*[:\-]\s*([A-Za-z\s,\.\-]+?)(?:\n|$|\.|;)',
                    r'(?:location|address|city)\s*[:\-]\s*([A-Za-z\s,\.\-]+)',
                ]
                for pat in location_patterns:
                    m = re.search(pat, raw_text, re.IGNORECASE)
                    if m and m.group(1):
                        loc = m.group(1).strip().strip('.,;:')
                        if len(loc) >= 2 and len(loc) <= 80:
                            toon['person']['location'] = loc
                            break
                # Fallback: common Indian cities if they appear in the first ~500 chars (header area)
                if not toon['person'].get('location') or not str(toon['person'].get('location', '')).strip():
                    header_text = raw_text[:500] if len(raw_text) > 500 else raw_text
                    cities = ['Mumbai', 'Delhi', 'Bangalore', 'Bengaluru', 'Hyderabad', 'Chennai', 'Kolkata', 'Pune', 'Ahmedabad', 'Gurgaon', 'Gurugram', 'Noida', 'Faridabad', 'Jaipur', 'Lucknow']
                    for city in cities:
                        if city in header_text:
                            toon['person']['location'] = city
                            break
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': f'LLM parsing failed: {str(e)}'
            }), 500
        
        # Validate TOON format
        is_valid, error_msg = validate_toon_format(toon, 'resume')
        if not is_valid:
            return jsonify({
                'status': 'error',
                'error': f'Invalid TOON format: {error_msg}'
            }), 400
        
        # Calculate confidence (simple heuristic based on field completeness)
        confidence = calculate_confidence(toon, 'resume')
        if os.getenv('AI_USE_GATEWAY', 'true').lower() in ('1', 'true', 'yes'):
            try:
                from ai_runtime_adapter import get_model_version
                model_version = get_model_version()
            except Exception:
                model_version = 'ai-runtime-v1'
        else:
            model_version = f"{os.getenv('LLM_PROVIDER', 'xai')}-v1"
        
        # Store parsed result
        parsed_id = store_parsed_resume(
            raw_file_id,
            candidate_id,
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
        print(f"Resume parsing error: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@parsing_bp.route('/parse/jd', methods=['POST'])
@authenticate_token
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
        
        # Call LLM to parse job description
        try:
            toon = call_llm(raw_text, 'jd')
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': f'LLM parsing failed: {str(e)}'
            }), 500
        
        # Validate TOON format
        is_valid, error_msg = validate_toon_format(toon, 'job_description')
        if not is_valid:
            return jsonify({
                'status': 'error',
                'error': f'Invalid TOON format: {error_msg}'
            }), 400
        
        # Calculate confidence
        confidence = calculate_confidence(toon, 'jd')
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
    from db import db_get
    
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
    from db import db_get
    
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

