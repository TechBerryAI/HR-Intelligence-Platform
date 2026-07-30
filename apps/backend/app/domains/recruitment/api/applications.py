import os
import re
import traceback
import requests
from flask import Blueprint, request, jsonify
from app.database.connection.db import db_get, db_run, db_all, BACKEND, TRUE_SQL, get_conn, _pg_query
from app.ai.toon.runtime import toon_dumps
from app.common.application_status import (
    STATUS_APPLIED,
    STATUS_SHORTLISTED,
    STATUS_REJECTED,
    normalize_status,
)
from app.ai.parser.enrichment.jd_text_inference import (
    extract_experience_years,
    extract_qualifications_from_text,
    extract_responsibilities_from_text,
    extract_skills_from_text,
)

applications_bp = Blueprint('applications', __name__)


def _apply_debug(stage: str, **fields):
    """Structured debug logging for POST /api/applications only."""
    parts = [f"[APPLY][{stage}]"]
    for key, value in fields.items():
        parts.append(f"{key}={value}")
    print(" ".join(parts))


def _apply_log_exception(exc: Exception):
    tb = traceback.extract_tb(exc.__traceback__)
    location = f"{tb[-1].filename}:{tb[-1].lineno}" if tb else "unknown"
    print(
        f"[APPLY][EXCEPTION] type={type(exc).__name__} message={exc} file={location}"
    )
    traceback.print_exc()


def _shortlisted_from_decision(decision: str) -> bool:
    return (decision or '').lower() in ('shortlist', 'strong_match', 'partial_match')


def _extract_ats_result(ats_result: dict) -> tuple:
    """Return (final_score, shortlisted, rationale, ats_analysis_toon, status)."""
    json_out = ats_result.get('json_output') or {}
    final_score = json_out.get('overall_match_score') or json_out.get('final_score')
    decision = (json_out.get('decision') or '').lower()
    rationale = (
        json_out.get('final_reasoning')
        or json_out.get('rationale')
        or (ats_result.get('toon_output', '') or '')[:2000]
    )
    ats_analysis_toon = toon_dumps(ats_result) if isinstance(ats_result, dict) else None
    shortlisted = _shortlisted_from_decision(decision)
    status = STATUS_SHORTLISTED if shortlisted else STATUS_APPLIED
    return final_score, shortlisted, rationale, ats_analysis_toon, status


def _persist_application_atomic(
    candidate_id: str,
    job_id: str,
    parsed_resume_id,
    parsed_jd_id,
    status: str,
    match_score,
    shortlisted: bool,
    ats_reasoning,
    ats_analysis_toon,
):
    """
    Atomically create match row + application row in a single transaction.
    Rolls back entirely if either insert fails.
    """
    shortlisted_val = shortlisted if BACKEND == 'postgresql' else (1 if shortlisted else 0)
    matching_pct = match_score if match_score is not None else 0

    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                _pg_query(
                    """
                    UPDATE matches
                    SET is_latest = false
                    WHERE candidate_id = ? AND job_id = ? AND is_latest = true
                    """
                ),
                (candidate_id, job_id),
            )

            cursor.execute(
                _pg_query(
                    """
                    INSERT INTO matches (
                        candidate_id, job_id, parsed_resume_id, parsed_jd_id,
                        match_score, matching_percentage, match_type,
                        rationale, analysis_toon, is_latest, created_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'ats', ?, ?, true, ?)
                    RETURNING id
                    """
                ),
                (
                    candidate_id,
                    job_id,
                    parsed_resume_id,
                    parsed_jd_id,
                    match_score,
                    matching_pct,
                    ats_reasoning,
                    ats_analysis_toon,
                    candidate_id,
                ),
            )
            match_row = cursor.fetchone()
            match_id = match_row[0] if match_row else None

            cursor.execute(
                _pg_query(
                    """
                    INSERT INTO applications (
                        candidate_id, job_id, status, matching_percentage, match_score,
                        shortlisted, ats_reasoning, ats_analysis, latest_match_id, created_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                    """
                ),
                (
                    candidate_id,
                    job_id,
                    status,
                    matching_pct,
                    match_score,
                    shortlisted_val,
                    ats_reasoning,
                    ats_analysis_toon,
                    match_id,
                    candidate_id,
                ),
            )
            app_row = cursor.fetchone()
            app_id = int(app_row[0]) if app_row else None

    return app_id, match_id


def _jd_toon_from_job_row(job):
    """
    Build a minimal JD TOON from a job row when no parsed_jd exists.
    Enables apply + integrated ATS to work for jobs created via the portal (no JD file upload).
    """
    desc = (job.get('description') or '').strip()
    experience_str = (job.get('experience') or '').strip()
    min_years, max_years = extract_experience_years(experience_str)
    mandatory_skills, preferred_skills, skills = extract_skills_from_text(desc)
    responsibilities = extract_responsibilities_from_text(desc)
    qualifications = extract_qualifications_from_text(desc)
    return {
        'type': 'job_description',
        'title': (job.get('title') or '').strip(),
        'company': (job.get('company') or job.get('company_name') or '').strip(),
        'location': (job.get('location') or '').strip(),
        'salary_range': (job.get('salary') or '').strip(),
        'min_experience_years': min_years,
        'max_experience_years': max_years,
        'skills': skills,
        'mandatory_skills': mandatory_skills,
        'preferred_skills': preferred_skills,
        'responsibilities': responsibilities,
        'qualifications': qualifications,
        'keywords': [],
    }

# ============================================================================
# N8N ATS WORKFLOW INTEGRATION - START
# ============================================================================

# Environment variables for n8n workflow integration
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', '')
N8N_CALLBACK_SECRET = os.getenv('N8N_CALLBACK_SECRET', '')  # Optional security token

def trigger_n8n(candidate_id, job_id, parsed_resume, parsed_jd):
    """
    Helper function to trigger n8n ATS workflow
    
    Sends a POST request to n8n webhook with:
    - candidate_id
    - job_id
    - parsed_resume (TOON format JSON)
    - parsed_jd (TOON format JSON)
    
    Returns:
        dict: Response from n8n or error details
    """
    if not N8N_WEBHOOK_URL:
        print("[N8N] WARNING: N8N_WEBHOOK_URL not configured, skipping n8n trigger")
        return {'error': 'N8N_WEBHOOK_URL not configured', 'skipped': True}
    
    payload = {
        'candidate_id': candidate_id,
        'job_id': job_id,
        'parsed_resume': parsed_resume,
        'parsed_jd': parsed_jd
    }
    
    try:
        print(f"[N8N] Triggering n8n workflow for candidate {candidate_id} applying to job {job_id}")
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10  # 10 second timeout for webhook
        )
        
        response.raise_for_status()
        
        print(f"[N8N] Successfully triggered n8n workflow. Status: {response.status_code}")
        return {
            'success': True,
            'status_code': response.status_code,
            'response': response.text
        }
        
    except requests.exceptions.Timeout:
        error_msg = "n8n webhook request timed out"
        print(f"[N8N] ERROR: {error_msg}")
        return {'error': error_msg, 'success': False}
        
    except requests.exceptions.RequestException as e:
        error_msg = f"n8n webhook request failed: {str(e)}"
        print(f"[N8N] ERROR: {error_msg}")
        return {'error': error_msg, 'success': False}

# ============================================================================
# N8N ATS WORKFLOW INTEGRATION - END
# ============================================================================


# Candidate self-apply removed: use POST /api/jobs/<job_id>/apply (public).


# ============================================================================
# N8N ATS CALLBACK ENDPOINT - START
# ============================================================================

@applications_bp.post('/ats/result')
def receive_ats_result():
    """
    Receive ATS match results from n8n workflow
    
    POST /api/applications/ats/result
    
    SECURITY:
    If N8N_CALLBACK_SECRET environment variable is set, the request must include
    a matching 'X-N8N-Callback-Secret' header for authentication.
    
    Body (JSON):
    {
        "candidate_id": "CID001",
        "job_id": "SE001",
        "match_score": 85.5,
        "shortlisted": true,
        "reasoning": "Overall summary...",
        "analysis": {
            "matched_skills": ["Python", "React", "AWS"],
            "additional_skills": ["Docker", "Kubernetes"],
            "missing_skills": ["Go", "GraphQL"],
            "education": {
                "required": "Bachelor's in Computer Science",
                "candidate": "BS Computer Science, MIT",
                "match": true,
                "score": 100
            },
            "experience": {
                "required": "5+ years",
                "candidate": "6 years",
                "match": true,
                "score": 90
            },
            "location": {
                "required": "San Francisco",
                "candidate": "Willing to relocate",
                "match": true,
                "score": 80
            },
            "decision": {
                "recommendation": "SHORTLIST",
                "reasoning": "Strong overall fit...",
                "strengths": ["Technical skills", "Experience level"],
                "concerns": ["Missing some nice-to-have skills"]
            }
        }
    }
    
    Updates the application record with detailed ATS analysis results.
    Stores structured matching data (skills, education, experience) in ats_analysis JSON field.
    Also updates status to 'shortlisted' or 'rejected' based on shortlisted flag.
    """
    try:
        # ========================================================================
        # OPTIONAL SECURITY: Verify callback secret if configured
        # ========================================================================
        if N8N_CALLBACK_SECRET:
            provided_secret = request.headers.get('X-N8N-Callback-Secret', '')
            if provided_secret != N8N_CALLBACK_SECRET:
                print(f"[ATS_RESULT] SECURITY: Invalid or missing callback secret")
                return jsonify({'error': 'Unauthorized - invalid callback secret'}), 401
        
        data = request.get_json(force=True)
        
        # Validate required fields
        candidate_id = data.get('candidate_id')
        job_id = data.get('job_id')
        match_score = data.get('match_score')
        shortlisted = data.get('shortlisted')
        reasoning = data.get('reasoning', '')
        
        # NEW: Get detailed analysis structure from n8n
        analysis = data.get('analysis', {})
        
        if not candidate_id or not job_id:
            return jsonify({'error': 'candidate_id and job_id are required'}), 400
        
        if match_score is None:
            return jsonify({'error': 'match_score is required'}), 400
        
        if shortlisted is None:
            return jsonify({'error': 'shortlisted is required'}), 400
        
        # Validate match_score is numeric
        try:
            match_score = float(match_score)
        except (ValueError, TypeError):
            return jsonify({'error': 'match_score must be a number'}), 400
        
        # Validate shortlisted is boolean
        if not isinstance(shortlisted, bool):
            # Try to convert string to boolean
            if isinstance(shortlisted, str):
                shortlisted = shortlisted.lower() in ('true', '1', 'yes')
            else:
                shortlisted = bool(shortlisted)
        
        print(f"[ATS_RESULT] Received ATS result for candidate {candidate_id}, job {job_id}")
        print(f"[ATS_RESULT] Match Score: {match_score}, Shortlisted: {shortlisted}")
        
        # Log detailed analysis structure if provided
        if analysis:
            print(f"[ATS_RESULT] Detailed analysis included:")
            if 'matched_skills' in analysis:
                print(f"[ATS_RESULT]   - Matched Skills: {len(analysis.get('matched_skills', []))} skills")
            if 'additional_skills' in analysis:
                print(f"[ATS_RESULT]   - Additional Skills: {len(analysis.get('additional_skills', []))} skills")
            if 'education' in analysis:
                print(f"[ATS_RESULT]   - Education Match: {analysis['education'].get('match', 'N/A')}")
            if 'experience' in analysis:
                print(f"[ATS_RESULT]   - Experience Match: {analysis['experience'].get('match', 'N/A')}")
        
        # Find the application
        application = db_get(
            'SELECT id, status FROM applications WHERE candidate_id = ? AND job_id = ?',
            (candidate_id, job_id)
        )
        
        if not application:
            print(f"[ATS_RESULT] WARNING: Application not found for candidate {candidate_id}, job {job_id}")
            return jsonify({'error': 'Application not found'}), 404
        
        # Determine new status based on shortlisted flag (canonical PostgreSQL values)
        new_status = normalize_status(application['status'])
        if normalize_status(application['status']) == STATUS_APPLIED:
            new_status = STATUS_SHORTLISTED if shortlisted else STATUS_REJECTED
        
        # ========================================================================
        # STORE DETAILED ATS ANALYSIS IN DATABASE
        # ========================================================================
        
        analysis_toon = toon_dumps(analysis) if analysis else None
        
        # Update application with ATS results AND detailed analysis
        _shortlisted_val = shortlisted if BACKEND == 'postgresql' else (1 if shortlisted else 0)
        db_run(
            """
            UPDATE applications
            SET match_score = ?,
                shortlisted = ?,
                ats_reasoning = ?,
                ats_analysis = ?,
                status = ?
            WHERE candidate_id = ? AND job_id = ?
            """,
            (match_score, _shortlisted_val, reasoning, analysis_toon, new_status, candidate_id, job_id)
        )
        
        print(f"[ATS_RESULT] Successfully updated application with detailed analysis. New status: {new_status}")
        
        return jsonify({
            'status': 'ok',
            'message': 'ATS results and detailed analysis recorded successfully',
            'application_id': application['id'],
            'new_status': new_status,
            'analysis_stored': bool(analysis)
        }), 200
        
    except Exception as e:
        print(f"[ATS_RESULT] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# N8N ATS CALLBACK ENDPOINT - END
# ============================================================================
