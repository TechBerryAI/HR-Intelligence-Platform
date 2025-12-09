import os
import json
import requests
from flask import Blueprint, request, jsonify
from db import db_get, db_run, db_all
from utils import authenticate_token, require_candidate

applications_bp = Blueprint('applications', __name__)

# ============================================================================
# N8N ATS WORKFLOW INTEGRATION - START
# ============================================================================

# Environment variable for n8n webhook URL
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', '')

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
        
        # Fetch the most recent parsed resume for this candidate
        parsed_resume_record = db_get(
            """
            SELECT toon, confidence 
            FROM parsed_resumes 
            WHERE candidate_id = ? 
            ORDER BY created_at DESC
            """,
            (candidate_id,)
        )
        
        if not parsed_resume_record:
            return jsonify({
                'error': 'No parsed resume found. Please upload and parse your resume first.'
            }), 400
        
        # Fetch the most recent parsed JD for this job
        parsed_jd_record = db_get(
            """
            SELECT toon, confidence 
            FROM parsed_jds 
            WHERE job_id = ? 
            ORDER BY created_at DESC
            """,
            (job_id,)
        )
        
        if not parsed_jd_record:
            return jsonify({
                'error': 'No parsed job description found for this job. Please contact HR.'
            }), 400
        
        # Parse JSON strings to dictionaries
        try:
            parsed_resume = json.loads(parsed_resume_record['toon'])
            parsed_jd = json.loads(parsed_jd_record['toon'])
        except json.JSONDecodeError as e:
            print(f"[APPLY] ERROR: Failed to parse stored JSON: {e}")
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
        
        # ========================================================================
        # TRIGGER N8N WORKFLOW
        # ========================================================================
        
        n8n_result = trigger_n8n(candidate_id, job_id, parsed_resume, parsed_jd)
        
        if not n8n_result.get('success') and not n8n_result.get('skipped'):
            # Log error but don't fail the application
            print(f"[APPLY] WARNING: n8n trigger failed but application was created: {n8n_result.get('error')}")
        
        return jsonify({
            'message': 'Application submitted successfully',
            'status': 'applied',
            'n8n_triggered': n8n_result.get('success', False)
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
