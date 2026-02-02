import os
import json
import re
import requests
from flask import Blueprint, request, jsonify
from db import db_get, db_run, db_all
from utils import authenticate_token, require_candidate
from services.ats_service import match_candidate_to_job

applications_bp = Blueprint('applications', __name__)


def _jd_toon_from_job_row(job):
    """
    Build a minimal JD TOON from a job row when no parsed_jd exists.
    Enables apply + integrated ATS to work for jobs created via the portal (no JD file upload).
    """
    desc = (job.get('description') or '').strip()
    experience_str = (job.get('experience') or '').strip()
    min_years, max_years = None, None
    if experience_str:
        nums = re.findall(r'(\d+(?:\.\d+)?)', experience_str)
        if len(nums) >= 2:
            min_years = float(nums[0])
            max_years = float(nums[1])
        elif len(nums) == 1:
            min_years = float(nums[0])
    skills = []
    if '**Required Skills:**' in desc or '**Skills:**' in desc:
        block = re.search(r'\*\*(?:Required )?Skills:\*\*\s*([^\n*]+)', desc, re.I)
        if block:
            skills = [s.strip() for s in re.split(r'[,•·]', block.group(1)) if s.strip()]
    if not skills and desc:
        for line in desc.split('\n')[:5]:
            if 'skill' in line.lower() or 'experience' in line.lower():
                parts = re.split(r'[,•·\-]', line)
                skills.extend([p.strip().strip('*') for p in parts if len(p.strip()) > 2][:15])
                break
    responsibilities = []
    if '**Responsibilities:**' in desc:
        block = re.search(r'\*\*Responsibilities:\*\*\s*([\s\S]*?)(?=\n\*\*|\Z)', desc)
        if block:
            raw = block.group(1)
            responsibilities = [s.strip().strip('•').strip() for s in re.split(r'\n', raw) if s.strip() and len(s.strip()) > 3]
    if not responsibilities and desc:
        for line in desc.split('\n'):
            line = line.strip().strip('•').strip()
            if len(line) > 10:
                responsibilities.append(line[:500])
                if len(responsibilities) >= 10:
                    break
    qualifications = []
    if '**Qualifications:**' in desc or 'qualifications' in desc.lower():
        block = re.search(r'\*\*Qualifications:\*\*\s*([\s\S]*?)(?=\n\*\*|\Z)', desc, re.I)
        if block:
            raw = block.group(1)
            qualifications = [s.strip().strip('•').strip() for s in re.split(r'\n', raw) if s.strip()]
    return {
        'type': 'job_description',
        'title': (job.get('title') or '').strip(),
        'company': (job.get('company') or job.get('company_name') or '').strip(),
        'location': (job.get('location') or '').strip(),
        'salary_range': (job.get('salary') or '').strip(),
        'min_experience_years': min_years,
        'max_experience_years': max_years,
        'skills': skills[:30],
        'responsibilities': responsibilities[:20],
        'qualifications': qualifications[:15],
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


@applications_bp.post('/')
@authenticate_token
@require_candidate
def apply_job():
    """
    Apply to a job using ATS workflow
    
    NEW WORKFLOW:
    1. Validates job and candidate profile
    2. Fetches STORED parsed_resume and parsed_jd (NO re-parsing)
    3. Creates application with status='applied'
    4. Triggers n8n webhook with parsed data
    5. n8n will analyze and send results back to /api/ats/result
    """
    try:
        data = request.get_json(force=True)
        job_id = data.get('jobId')
        candidate_id = request.user['id']
        
        if not job_id:
            return jsonify({'error': 'Job ID is required'}), 400
        
        # Validate job exists and is enabled
        job = db_get('SELECT * FROM jobs WHERE jdid = ? AND enabled = 1', (job_id,))
        if not job:
            return jsonify({'error': 'Job not found or not available'}), 404
        
        # Check for duplicate application
        existing = db_get('SELECT id FROM applications WHERE candidate_id = ? AND job_id = ?', (candidate_id, job_id))
        if existing:
            return jsonify({'error': 'Already applied to this job'}), 400
        
        # Validate candidate profile is complete
        profile = db_get('SELECT * FROM candidate_profiles WHERE candidate_id = ? AND completed = 1', (candidate_id,))
        if not profile:
            return jsonify({'error': 'Please complete your profile before applying'}), 400
        
        # ========================================================================
        # FETCH STORED PARSED DATA (NO RE-PARSING)
        # ========================================================================
        
        # Fetch the most recent parsed resume for this candidate (by candidate_id or by uploader)
        parsed_resume_record = db_get(
            """
            SELECT toon, confidence, id
            FROM parsed_resumes
            WHERE candidate_id = ?
            ORDER BY created_at DESC
            """,
            (candidate_id,)
        )
        # Fallback: resume may have been parsed before candidate_id was linked (e.g. from profile upload)
        if not parsed_resume_record:
            parsed_resume_record = db_get(
                """
                SELECT pr.toon, pr.confidence, pr.id
                FROM parsed_resumes pr
                INNER JOIN raw_files rf ON pr.raw_file_id = rf.id
                WHERE rf.uploader_id = ?
                ORDER BY pr.created_at DESC
                """,
                (candidate_id,)
            )
            if parsed_resume_record:
                # Link this parse to candidate so future applies use direct query
                db_run(
                    'UPDATE parsed_resumes SET candidate_id = ? WHERE id = ?',
                    (candidate_id, parsed_resume_record['id'])
                )
        if not parsed_resume_record:
            return jsonify({
                'error': 'No parsed resume found. Please upload and parse your resume first.'
            }), 400
        
        # Fetch the most recent parsed JD for this job (if HR uploaded a JD file)
        parsed_jd_record = db_get(
            """
            SELECT toon, confidence 
            FROM parsed_jds 
            WHERE job_id = ? 
            ORDER BY created_at DESC
            """,
            (job_id,)
        )
        
        if parsed_jd_record:
            try:
                parsed_jd = json.loads(parsed_jd_record['toon'])
            except json.JSONDecodeError as e:
                print(f"[APPLY] ERROR: Failed to parse stored JD JSON: {e}")
                return jsonify({'error': 'Invalid stored parsing data'}), 500
        else:
            # No parsed JD file for this job: build minimal TOON from job row so integrated ATS still runs
            parsed_jd = _jd_toon_from_job_row(job)
            print(f"[APPLY] No parsed_jd for job {job_id}; using minimal TOON from job row for ATS")
        
        # Parse resume TOON
        try:
            parsed_resume = json.loads(parsed_resume_record['toon'])
        except json.JSONDecodeError as e:
            print(f"[APPLY] ERROR: Failed to parse stored resume JSON: {e}")
            return jsonify({'error': 'Invalid stored parsing data'}), 500
        
        # ========================================================================
        # CREATE APPLICATION WITH STATUS='applied'
        # ========================================================================
        
        print(f"[APPLY] Creating application for candidate {candidate_id} to job {job_id}")
        
        db_run(
            """
            INSERT INTO applications 
            (candidate_id, job_id, status, matching_percentage, match_score, shortlisted, ats_reasoning) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (candidate_id, job_id, 'applied', 0, None, 0, None)  # Status set to 'applied', ATS fields null initially
        )
        
        # Get the just-inserted application id (for ATS update and later n8n)
        app_row = db_get(
            'SELECT id FROM applications WHERE candidate_id = ? AND job_id = ? ORDER BY id DESC',
            (candidate_id, job_id)
        )
        app_id = str(app_row['id']) if app_row else None
        
        # ========================================================================
        # ATS MATCHING - call HR-ATS-API internally (no duplicate logic)
        # ========================================================================
        ats_success, ats_result = match_candidate_to_job(
            candidate_id, job_id, parsed_resume, parsed_jd, apply_id=app_id
        )
        
        if ats_success and ats_result:
            json_out = ats_result.get('json_output') or {}
            final_score = json_out.get('overall_match_score') or json_out.get('final_score')
            decision = (json_out.get('decision') or '').lower()
            rationale = json_out.get('final_reasoning') or json_out.get('rationale') or ats_result.get('toon_output', '')[:2000]
            ats_analysis_json = json.dumps(ats_result) if isinstance(ats_result, dict) else None
            shortlisted = 1 if decision in ('shortlist', 'strong_match', 'partial_match') else 0
            status_after = 'shortlisted' if shortlisted else 'applied'
            db_run(
                """
                UPDATE applications SET match_score = ?, matching_percentage = ?, shortlisted = ?, ats_reasoning = ?, ats_analysis = ?, status = ?
                WHERE candidate_id = ? AND job_id = ?
                """,
                (final_score, final_score, shortlisted, rationale, ats_analysis_json, status_after, candidate_id, job_id)
            )
            # Shortlisted candidate data will later be sent to n8n (not implemented here)
            return jsonify({
                'message': 'Application submitted successfully',
                'status': status_after,
                'matchScore': final_score,
                'shortlisted': bool(shortlisted),
            }), 201
        else:
            # ATS failed or not configured - application still created; log and return success
            err = ats_result.get('error', 'Unknown ATS error') if isinstance(ats_result, dict) else str(ats_result)
            print(f"[APPLY] ATS not run or failed (non-blocking): {err}")
            return jsonify({
                'message': 'Application submitted successfully',
                'status': 'applied',
                'matchScore': None,
                'shortlisted': False,
            }), 201
        
    except Exception as e:
        print(f"[APPLY] ERROR in apply_job: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@applications_bp.get('/')
@authenticate_token
@require_candidate
def get_my_applications():
    """
    Get all applications for the authenticated candidate
    
    Now includes ATS fields:
    - match_score
    - shortlisted
    - ats_reasoning
    - ats_analysis (detailed structured matching data)
    """
    try:
        apps = db_all(
            '''
            SELECT a.*, j.title, j.company, j.location, j.salary, j.experience, j.description
            FROM applications a
            JOIN jobs j ON a.job_id = j.jdid
            WHERE a.candidate_id = ?
            ORDER BY a.applied_at DESC
            ''', (request.user['id'],)
        )
        formatted = [
            {
                'id': a['id'],
                'jobId': a['job_id'],
                'status': a['status'],
                'appliedAt': a['applied_at'],
                'matchScore': a.get('match_score'),
                'shortlisted': bool(a.get('shortlisted')),
                'atsReasoning': a.get('ats_reasoning'),
                'atsAnalysis': json.loads(a['ats_analysis']) if a.get('ats_analysis') else None,
                'job': {
                    'id': a['job_id'],
                    'title': a['title'],
                    'company': a['company'],
                    'location': a['location'],
                    'salary': a['salary'],
                    'experience': a.get('experience'),
                    'description': a['description']
                }
            }
            for a in apps
        ]
        return jsonify(formatted)
    except Exception as e:
        print(f"[GET_APPLICATIONS] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


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
        
        # Determine new status based on shortlisted flag
        # Only update status if it's still 'applied' (don't override manual status changes)
        new_status = application['status']
        if application['status'] == 'applied':
            new_status = 'shortlisted' if shortlisted else 'rejected'
        
        # ========================================================================
        # STORE DETAILED ATS ANALYSIS IN DATABASE
        # ========================================================================
        
        # Convert analysis dictionary to JSON string for storage
        analysis_json = json.dumps(analysis) if analysis else None
        
        # Update application with ATS results AND detailed analysis
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
            (match_score, 1 if shortlisted else 0, reasoning, analysis_json, new_status, candidate_id, job_id)
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
