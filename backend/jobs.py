import re
from datetime import datetime
from flask import Blueprint, request, jsonify
from db import db_all, db_get, db_run, BACKEND, TRUE_SQL, FALSE_SQL
from utils import authenticate_token, require_hr, optional_authenticate_token
from toon import toon_loads_flex
from services.candidate_notification_service import send_and_get_output

jobs_bp = Blueprint('jobs', __name__)


def _resume_bytes(data):
    if data is None:
        return None
    if isinstance(data, bytes):
        return data
    if isinstance(data, memoryview):
        return data.tobytes()
    if isinstance(data, bytearray):
        return bytes(data)
    try:
        return bytes(data)
    except (TypeError, ValueError):
        return None


def generate_jdid_from_title(title):
    """
    Generate jdid from job title.
    Pattern: First letter of each word + 3-digit sequence number
    Examples:
    - "data analyst" -> "DA001"
    - "software developer" -> "SD001"
    - "engineer" -> "E001"
    """
    if not title:
        return "JD001"
    
    # Extract first letter of each word (uppercase)
    words = re.findall(r'\b\w', title.upper())
    if not words:
        prefix = "JD"
    else:
        # Take first letter of each word, up to reasonable length
        prefix = ''.join(words[:5])  # Max 5 letters for prefix
    
    # Find the last jdid with this prefix (e.g. DA001, SD002)
    if BACKEND == "postgresql":
        # PostgreSQL: use SUBSTRING and ~ for numeric suffix
        existing = db_get(
            '''
            SELECT jdid FROM jobs
            WHERE jdid LIKE ?
            ORDER BY
              CASE WHEN SUBSTRING(jdid FROM LENGTH(?) + 1) ~ '^[0-9]+$'
                THEN CAST(SUBSTRING(jdid FROM LENGTH(?) + 1) AS INT)
                ELSE 0
              END DESC NULLS LAST,
              jdid DESC
            LIMIT 1
            ''',
            (f'{prefix}%', prefix, prefix)
        )
    else:
        existing = db_get(
            '''
            SELECT TOP 1 jdid
            FROM jobs
            WHERE jdid LIKE ?
            ORDER BY
              CASE
                WHEN ISNUMERIC(SUBSTRING(jdid, LEN(?) + 1, 10)) = 1
                THEN CAST(SUBSTRING(jdid, LEN(?) + 1, 10) AS INT)
                ELSE 0
              END DESC,
              jdid DESC
            ''',
            (f'{prefix}%', prefix, prefix)
        )
    
    if existing and existing.get('jdid'):
        try:
            # Extract number part after prefix
            existing_jdid = str(existing['jdid'])
            if len(existing_jdid) > len(prefix):
                num_part = existing_jdid[len(prefix):]
                # Extract only numeric part (in case of old INT jdid)
                num_part = ''.join(filter(str.isdigit, num_part))
                if num_part:
                    next_num = int(num_part) + 1
                else:
                    next_num = 1
            else:
                next_num = 1
        except (ValueError, IndexError, TypeError):
            next_num = 1
    else:
        next_num = 1
    
    # Format: PREFIX + 3-digit number (e.g., DA001, SD001)
    return f"{prefix}{next_num:03d}"


@jobs_bp.get('/')
@optional_authenticate_token
def get_jobs_public():
    """List jobs. If authenticated as HR, return only jobs posted by that HR. Otherwise return enabled jobs (public)."""
    try:
        user = getattr(request, 'user', None)
        if user and user.get('role') == 'HR' and user.get('hrId'):
            # Admin: only jobs posted by this HR
            jobs = db_all(
                '''
                SELECT j.*, hs.company as company_name
                FROM jobs j
                LEFT JOIN hr_signup hs ON j.posted_by = hs.hrid
                WHERE j.posted_by = ?
                ORDER BY j.posted_on DESC
                ''',
                (user.get('hrId'),)
            )
            # Optionally restrict to jobs whose company matches JWT; if that would hide all, show all (avoid data mismatch hiding jobs)
            hr_company = (user.get('company') or '').strip()
            if hr_company:
                hr_company_lower = hr_company.lower()
                filtered = [j for j in jobs if (j.get('company') or '').strip().lower() == hr_company_lower]
                if len(filtered) > 0 or len(jobs) == 0:
                    jobs = filtered
                # else: keep full list so HR still sees their jobs
        else:
            # Public / candidate: only enabled jobs (treat NULL enabled as visible)
            jobs = db_all(
                '''
                SELECT j.*, hs.company as company_name
                FROM jobs j
                LEFT JOIN hr_signup hs ON j.posted_by = hs.hrid
                WHERE (j.enabled = ''' + TRUE_SQL + ''' OR j.enabled IS NULL)
                ORDER BY j.posted_on DESC
                '''
            )
        formatted = [
            {
                'id': j['jdid'],
                'title': j['title'],
                'company': j.get('company') or j.get('company_name'),
                'location': j['location'],
                'salary': j['salary'],
                'experience': j.get('experience'),
                'description': j['description'],
                'enabled': bool(j['enabled']),
                'postedOn': j['posted_on'],
            }
            for j in jobs
        ]
        return jsonify(formatted)
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.get('/all')
@authenticate_token
@require_hr
def get_jobs_all():
    try:
        user = request.user
        jobs = db_all(
            '''
            SELECT j.*, hs.company as company_name
            FROM jobs j
            LEFT JOIN hr_signup hs ON j.posted_by = hs.hrid
            WHERE j.posted_by = ?
            ORDER BY j.posted_on DESC
            ''', (user.get('hrId'),)
        )
        formatted = [
            {
                'id': j['jdid'],
                'title': j['title'],
                'company': j.get('company') or j.get('company_name'),
                'location': j['location'],
                'salary': j['salary'],
                'experience': j.get('experience'),
                'description': j['description'],
                'enabled': bool(j['enabled']),
                'postedOn': j['posted_on'],
            }
            for j in jobs
        ]
        return jsonify(formatted)
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.get('/<string:job_id>')
@optional_authenticate_token
def get_job(job_id: str):
    """Get one job. HR sees only their own; candidates/public see enabled jobs only."""
    try:
        job = db_get(
            '''
            SELECT j.*, hs.company as company_name
            FROM jobs j
            LEFT JOIN hr_signup hs ON j.posted_by = hs.hrid
            WHERE j.jdid = ?
            ''', (job_id,)
        )
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        user = getattr(request, 'user', None)
        if user and user.get('role') == 'HR':
            # HR may only view/edit jobs they posted
            if job.get('posted_by') != user.get('hrId'):
                return jsonify({'error': 'Job not found or access denied'}), 404
        else:
            # Candidate/public: only enabled jobs
            if not job.get('enabled'):
                return jsonify({'error': 'Job not found'}), 404
        return jsonify({
            'id': job['jdid'],
            'title': job['title'],
            'company': job.get('company') or job.get('company_name'),
            'location': job['location'],
            'salary': job['salary'],
            'experience': job.get('experience'),
            'description': job['description'],
            'enabled': bool(job['enabled']),
            'postedOn': job['posted_on'],
        })
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.get('/<string:job_id>/applications')
@authenticate_token
@require_hr
def get_job_applications(job_id: str):
    try:
        # Verify job belongs to HR user
        job = db_get('SELECT * FROM jobs WHERE jdid = ? AND posted_by = ?', (job_id, request.user.get('hrId')))
        if not job:
            # Return 200 with empty list so UI shows "No candidates" instead of errors; avoids 404 in terminal
            return jsonify({'applications': []}), 200

        # Get applications with candidate details (include ATS: match_score, shortlisted, ats_reasoning, ats_analysis)
        applications = db_all(
            '''
            SELECT 
                a.id,
                a.candidate_id,
                a.job_id,
                a.status,
                a.applied_at,
                a.matching_percentage,
                a.match_score,
                a.shortlisted,
                a.ats_reasoning,
                a.ats_analysis,
                cp.full_name,
                cp.email,
                cp.phone,
                cp.current_location,
                cp.preferred_location,
                cp.experience_level,
                cp.serving_notice,
                cp.notice_period,
                cp.last_working_day,
                cp.linkedin_url,
                cp.portfolio_url,
                CASE WHEN cp.resume IS NOT NULL THEN 1 ELSE 0 END as has_resume,
                cs.name as candidate_name
            FROM applications a
            INNER JOIN candidate_profiles cp ON a.candidate_id = cp.candidate_id
            LEFT JOIN candidate_signup cs ON a.candidate_id = cs.cid
            WHERE a.job_id = ?
            ORDER BY a.matching_percentage DESC, a.applied_at DESC
            ''',
            (job_id,)
        )
        
        # Get related data (education, experiences, certifications)
        formatted_apps = []
        for app in applications:
            candidate_id = app['candidate_id']
            
            # Get education
            _cgpa_col = '"cgpa/percentage"' if BACKEND == "postgresql" else "[cgpa/percentage]"
            education = db_all(
                'SELECT degree, institution, ' + _cgpa_col + ' as cgpa, start_date, end_date FROM candidate_education WHERE candidate_id = ?',
                (candidate_id,)
            )
            
            # Get experiences
            experiences = db_all(
                'SELECT company, role, start_date, end_date, present FROM candidate_experiences WHERE candidate_id = ?',
                (candidate_id,)
            )
            
            # Get certifications
            certifications = db_all(
                'SELECT certification, issuer, end_month FROM candidate_certifications WHERE candidate_id = ?',
                (candidate_id,)
            )
            
            # Prefer ATS match_score when present; fallback to matching_percentage
            match_score = app.get('match_score')
            if match_score is not None:
                try:
                    match_score = float(match_score)
                except (ValueError, TypeError):
                    match_score = None
            matching_pct = app.get('matching_percentage')
            if matching_pct is None:
                matching_pct = 0
            else:
                try:
                    matching_pct = float(matching_pct)
                    if matching_pct < 0:
                        matching_pct = 0
                    elif matching_pct > 100:
                        matching_pct = 100
                except (ValueError, TypeError):
                    matching_pct = 0
            score_display = match_score if match_score is not None else matching_pct
            
            ats_analysis_raw = app.get('ats_analysis')
            ats_analysis = toon_loads_flex(ats_analysis_raw) if ats_analysis_raw else None
            formatted_apps.append({
                'id': app['id'],
                'candidateId': app['candidate_id'],
                'jobId': app['job_id'],
                'status': app['status'],
                'appliedAt': app['applied_at'],
                'matchScore': score_display,
                'score': score_display,
                'shortlisted': bool(app.get('shortlisted')),
                'atsReasoning': app.get('ats_reasoning'),
                'atsAnalysis': ats_analysis,
                'fullName': app.get('full_name') or app.get('candidate_name') or 'Unknown',
                'name': app.get('full_name') or app.get('candidate_name') or 'Unknown',
                'email': app.get('email'),
                'phone': app.get('phone'),
                'currentLocation': app.get('current_location'),
                'preferredLocation': app.get('preferred_location'),
                'experienceLevel': app.get('experience_level'),
                'servingNotice': app.get('serving_notice'),
                'noticePeriod': app.get('notice_period'),
                'lastWorkingDay': app.get('last_working_day'),
                'linkedinUrl': app.get('linkedin_url'),
                'portfolioUrl': app.get('portfolio_url'),
                'resumeFileName': 'resume.pdf' if app.get('has_resume') else None,
                'resumeUrl': f'/api/jobs/{job_id}/applications/{candidate_id}/resume' if app.get('has_resume') else None,
                'education': [
                    {
                        'degree': e.get('degree') or '',
                        'institution': e.get('institution') or '',
                        'cgpa': e.get('cgpa') or '',
                        'startMonth': e.get('start_date') or '',
                        'endMonth': e.get('end_date') or '',
                    }
                    for e in (education or [])
                ],
                'experiences': [
                    {
                        'company': e.get('company') or '',
                        'role': e.get('role') or '',
                        'startMonth': e.get('start_date') or '',
                        'endMonth': e.get('end_date') or '',
                        'isCurrent': (e.get('present') or '').lower() == 'yes',
                    }
                    for e in (experiences or [])
                ],
                'certifications': [
                    {
                        'certification': c.get('certification') or '',
                        'issuer': c.get('issuer') or '',
                        'endMonth': c.get('end_month') or '',
                    }
                    for c in (certifications or [])
                ],
            })
        
        return jsonify({'applications': formatted_apps})
    except Exception as e:
        print(f"Error in get_job_applications: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.get('/<string:job_id>/applications/<string:candidate_id>/resume')
@authenticate_token
@require_hr
def get_candidate_resume(job_id: str, candidate_id: str):
    """Download candidate resume for HR"""
    try:
        # Verify job belongs to HR user
        job = db_get('SELECT * FROM jobs WHERE jdid = ? AND posted_by = ?', (job_id, request.user.get('hrId')))
        if not job:
            return jsonify({'error': 'Job not found or access denied'}), 404
        
        # Verify candidate has applied to this job
        application = db_get('SELECT id FROM applications WHERE job_id = ? AND candidate_id = ?', (job_id, candidate_id))
        if not application:
            return jsonify({'error': 'Application not found'}), 404
        
        # Get resume
        profile = db_get(
            '''
            SELECT resume
            FROM candidate_profiles
            WHERE candidate_id = ?
            ''',
            (candidate_id,)
        )
        if not profile or not profile.get('resume'):
            return jsonify({'error': 'Resume not found'}), 404
        
        from flask import Response
        resume_data = _resume_bytes(profile.get('resume'))
        if resume_data:
            return Response(
                resume_data,
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'inline; filename=resume_{candidate_id}.pdf',
                    'Content-Type': 'application/pdf',
                    'X-Content-Type-Options': 'nosniff',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            )
        else:
            return jsonify({'error': 'Invalid resume data'}), 500
    except Exception as e:
        print(f"Error in get_candidate_resume: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.post('/<string:job_id>/applications/<string:candidate_id>/viewed')
@authenticate_token
@require_hr
def record_profile_viewed(job_id: str, candidate_id: str):
    """Record that HR viewed this candidate's profile for this job. Sends email and updates status."""
    try:
        job = db_get('SELECT * FROM jobs WHERE jdid = ? AND posted_by = ?', (job_id, request.user.get('hrId')))
        if not job:
            return jsonify({'error': 'Job not found or access denied'}), 404
        app = db_get('SELECT id FROM applications WHERE job_id = ? AND candidate_id = ?', (job_id, candidate_id))
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        profile = db_get('SELECT full_name, email FROM candidate_profiles WHERE candidate_id = ?', (candidate_id,))
        signup = db_get('SELECT email FROM candidate_signup WHERE cid = ?', (candidate_id,))
        app['full_name'] = (profile or {}).get('full_name') or ''
        app['email'] = (profile or {}).get('email') or (signup or {}).get('email') or ''
        ts = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        status_db = 'profile_viewed'
        if app['email']:
            out = send_and_get_output(
                hr_action='PROFILE_VIEWED',
                candidate_name=app.get('full_name') or '',
                candidate_email=app['email'],
                job_title=job.get('title') or '',
                company_name=job.get('company') or '',
                application_id=app['id'],
                timestamp=ts,
            )
            status_db = out['profile_update']['status_db']
        db_run(
            'UPDATE applications SET status = ? WHERE id = ?',
            (status_db, app['id'])
        )
        return jsonify({'status': 'ok', 'profile_update': {'application_id': str(app['id']), 'status': 'Profile Viewed', 'updated_at': ts}}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error in record_profile_viewed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.patch('/<string:job_id>/applications/<string:candidate_id>/status')
@authenticate_token
@require_hr
def update_application_status(job_id: str, candidate_id: str):
    """Shortlist or reject candidate. Body: { "action": "shortlist" | "reject" }."""
    try:
        data = request.get_json(force=True) or {}
        action = (data.get('action') or '').strip().lower()
        if action not in ('shortlist', 'reject'):
            return jsonify({'error': 'action must be "shortlist" or "reject"'}), 400
        job = db_get('SELECT * FROM jobs WHERE jdid = ? AND posted_by = ?', (job_id, request.user.get('hrId')))
        if not job:
            return jsonify({'error': 'Job not found or access denied'}), 404
        app = db_get('SELECT id FROM applications WHERE job_id = ? AND candidate_id = ?', (job_id, candidate_id))
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        profile = db_get('SELECT full_name, email FROM candidate_profiles WHERE candidate_id = ?', (candidate_id,))
        signup = db_get('SELECT email FROM candidate_signup WHERE cid = ?', (candidate_id,))
        app['full_name'] = (profile or {}).get('full_name') or ''
        app['email'] = (profile or {}).get('email') or (signup or {}).get('email') or ''
        if not app['email']:
            return jsonify({'error': 'Candidate email not found; cannot send notification'}), 400
        hr_action = 'SHORTLISTED' if action == 'shortlist' else 'NOT_SHORTLISTED'
        ts = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        out = send_and_get_output(
            hr_action=hr_action,
            candidate_name=app.get('full_name') or '',
            candidate_email=app.get('email') or '',
            job_title=job.get('title') or '',
            company_name=job.get('company') or '',
            application_id=app['id'],
            timestamp=ts,
        )
        _sl = action == 'shortlist'
        _sl_val = _sl if BACKEND == 'postgresql' else (1 if _sl else 0)
        db_run(
            'UPDATE applications SET status = ?, shortlisted = ? WHERE id = ?',
            (out['profile_update']['status_db'], _sl_val, app['id'])
        )
        return jsonify({'status': 'ok', 'profile_update': out['profile_update']}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error in update_application_status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.post('/')
@authenticate_token
@require_hr
def create_job():
    try:
        print("=" * 50)
        print("CREATE JOB ENDPOINT CALLED")
        print(f"Request method: {request.method}")
        print(f"Request URL: {request.url}")
        print(f"Headers: {dict(request.headers)}")
        data = request.get_json(force=True) or {}
        print(f"Received data: {data}")
        print(f"User from token: {request.user}")
        title = (data.get('title') or '').strip()
        company = (data.get('company') or '').strip()
        location = (data.get('location') or '').strip()
        salary = (data.get('salary') or '').strip() or None
        experience = data.get('experience') or None
        if experience:
            experience = str(experience).strip() or None
        
        # Support legacy format: if experienceFrom/experienceTo provided, combine them
        if not experience:
            experience_from = data.get('experienceFrom')
            experience_to = data.get('experienceTo')
            # Handle string values
            if isinstance(experience_from, str):
                try:
                    experience_from = int(experience_from) if experience_from.strip() else None
                except (ValueError, AttributeError):
                    experience_from = None
            if isinstance(experience_to, str):
                try:
                    experience_to = int(experience_to) if experience_to.strip() else None
                except (ValueError, AttributeError):
                    experience_to = None
            
            if experience_from is not None or experience_to is not None:
                if experience_from is not None and experience_to is not None:
                    experience = f"{experience_from}-{experience_to} years"
                elif experience_from is not None:
                    experience = f"{experience_from}+ years"
                elif experience_to is not None:
                    experience = f"Up to {experience_to} years"
        
        description = (data.get('description') or '').strip()
        
        # Get company from HR profile if not provided
        if not company and request.user.get('hrId'):
            hr_profile = db_get('SELECT company FROM hr_signup WHERE hrid = ?', (request.user.get('hrId'),))
            if hr_profile:
                company = hr_profile.get('company') or ''
        
        if not title or not company or not location or not description:
            missing_fields = []
            if not title: missing_fields.append('title')
            if not company: missing_fields.append('company')
            if not location: missing_fields.append('location')
            if not description: missing_fields.append('description')
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        # Ensure hrId exists
        hr_id = request.user.get('hrId')
        if not hr_id:
            return jsonify({'error': 'Invalid HR user. Please log in again.'}), 401
        
        # Generate jdid from job title
        jdid = generate_jdid_from_title(title)
        print(f"Generated jdid: {jdid} from title: {title}")
        
        print(f"Prepared job data: jdid={jdid}, title={title}, company={company}, location={location}, hr_id={hr_id}")
        print("Executing INSERT query...")
        
        _enabled_val = True if BACKEND == 'postgresql' else 1
        result = db_run(
            '''
            INSERT INTO jobs (jdid, title, company, location, salary, experience, description, posted_by, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (jdid, title, company, location, salary, experience, description, hr_id, _enabled_val)
        )
        print(f"INSERT result: {result}")
        
        print("Fetching created job...")
        job = db_get('SELECT * FROM jobs WHERE jdid = ?', (jdid,))
        print(f"Retrieved job: {job}")
        
        if not job:
            print("ERROR: Job created but could not be retrieved")
            return jsonify({'error': 'Job created but could not be retrieved'}), 500
        
        print("Job created successfully!")
        print("=" * 50)
        
        return jsonify({
            'id': job['jdid'],
            'title': job['title'],
            'company': job['company'],
            'location': job['location'],
            'salary': job['salary'],
            'experience': job.get('experience'),
            'description': job['description'],
            'enabled': bool(job['enabled']),
            'postedOn': job['posted_on'],
        }), 201
    except Exception as e:
        import traceback
        error_msg = str(e)
        print("=" * 50)
        print("ERROR IN CREATE JOB:")
        print(f"Error message: {error_msg}")
        traceback.print_exc()  # Print full traceback for debugging
        print("=" * 50)
        if 'FOREIGN KEY' in error_msg.upper():
            return jsonify({'error': 'Invalid HR user. Please log in again.'}), 400
        return jsonify({'error': f'Internal server error: {error_msg}'}), 500


@jobs_bp.put('/<string:job_id>')
@authenticate_token
@require_hr
def update_job(job_id: str):
    try:
        data = request.get_json(force=True)
        title = (data.get('title') or '').strip()
        location = (data.get('location') or '').strip()
        salary = (data.get('salary') or '').strip() or None
        experience = data.get('experience') or None
        if experience:
            experience = str(experience).strip() or None
        
        # Support legacy format: if experienceFrom/experienceTo provided, combine them
        if not experience:
            experience_from = data.get('experienceFrom')
            experience_to = data.get('experienceTo')
            # Handle string values
            if isinstance(experience_from, str):
                try:
                    experience_from = int(experience_from) if experience_from.strip() else None
                except (ValueError, AttributeError):
                    experience_from = None
            if isinstance(experience_to, str):
                try:
                    experience_to = int(experience_to) if experience_to.strip() else None
                except (ValueError, AttributeError):
                    experience_to = None
            
            if experience_from is not None or experience_to is not None:
                if experience_from is not None and experience_to is not None:
                    experience = f"{experience_from}-{experience_to} years"
                elif experience_from is not None:
                    experience = f"{experience_from}+ years"
                elif experience_to is not None:
                    experience = f"Up to {experience_to} years"
        description = (data.get('description') or '').strip()

        job = db_get('SELECT * FROM jobs WHERE jdid = ? AND posted_by = ?', (job_id, request.user.get('hrId')))
        if not job:
            return jsonify({'error': 'Job not found or access denied'}), 404

        # Determine if jdid needs to be regenerated
        # Regenerate if title, experience, or salary changed
        old_title = (job.get('title') or '').strip()
        old_experience = (job.get('experience') or '').strip()
        old_salary = (job.get('salary') or '').strip() or None
        new_title = title or old_title
        new_experience = experience or old_experience
        new_salary = salary if salary is not None else old_salary
        
        should_regenerate_jdid = (
            (title and title.strip() and title.strip().upper() != old_title.upper()) or
            (experience and experience.strip() != old_experience) or
            (salary is not None and salary != old_salary)
        )
        
        new_jdid = job_id  # Keep same jdid by default
        
        if should_regenerate_jdid:
            # Generate new jdid from title
            new_jdid = generate_jdid_from_title(new_title)
            print(f"Regenerating jdid: {job_id} -> {new_jdid} (title/experience/salary changed)")
            
            # If jdid changed, update foreign keys in other tables
            if new_jdid != job_id:
                # Update applications table
                db_run('UPDATE applications SET job_id = ? WHERE job_id = ?', (new_jdid, job_id))
                # saved_jobs table was removed in migrations; skip if present
                if BACKEND != "postgresql":
                    try:
                        db_run('UPDATE saved_jobs SET job_id = ? WHERE job_id = ?', (new_jdid, job_id))
                    except Exception:
                        pass

        # Update job with new jdid if it changed
        db_run(
            '''
            UPDATE jobs SET
              jdid = ?,
              title = COALESCE(?, title),
              location = COALESCE(?, location),
              salary = ?,
              experience = ?,
              description = COALESCE(?, description)
            WHERE jdid = ?
            ''',
            (new_jdid, title, location, salary, experience, description, job_id)
        )
        updated = db_get('SELECT * FROM jobs WHERE jdid = ?', (new_jdid,))
        return jsonify({
            'id': updated['jdid'],
            'title': updated['title'],
            'company': updated['company'],
            'location': updated['location'],
            'salary': updated['salary'],
            'experience': updated.get('experience'),
            'description': updated['description'],
            'enabled': bool(updated['enabled']),
            'postedOn': updated['posted_on'],
        })
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.patch('/<string:job_id>/enabled')
@authenticate_token
@require_hr
def toggle_job(job_id: str):
    try:
        data = request.get_json(force=True)
        enabled = bool(data.get('enabled'))
        job = db_get('SELECT * FROM jobs WHERE jdid = ? AND posted_by = ?', (job_id, request.user.get('hrId')))
        if not job:
            return jsonify({'error': 'Job not found or access denied'}), 404
        _enabled = (True, False) if BACKEND == 'postgresql' else (1, 0)
        db_run('UPDATE jobs SET enabled = ? WHERE jdid = ?', (_enabled[0] if enabled else _enabled[1], job_id))
        return jsonify({'message': 'Job status updated', 'enabled': enabled})
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.delete('/<string:job_id>')
@authenticate_token
@require_hr
def delete_job(job_id: str):
    try:
        job = db_get('SELECT * FROM jobs WHERE jdid = ? AND posted_by = ?', (job_id, request.user.get('hrId')))
        if not job:
            return jsonify({'error': 'Job not found or access denied'}), 404
        db_run('DELETE FROM jobs WHERE jdid = ?', (job_id,))
        return jsonify({'message': 'Job deleted successfully'})
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500
