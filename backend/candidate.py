import os
import bcrypt
from flask import Blueprint, request, jsonify, Response
from db import db_get, db_run, db_all, BACKEND, NOW_SQL
from utils import authenticate_token, require_candidate, require_hr, validate_password_strength
from matching import calculate_matching_percentage

candidate_bp = Blueprint('candidate', __name__)
# Column name for cgpa/percentage: PostgreSQL uses double-quoted identifier
CGPA_COL = '"cgpa/percentage"' if BACKEND == "postgresql" else "[cgpa/percentage]"

@candidate_bp.post('/logout')
def candidate_logout():
    from sessions_service import deactivate_session
    try:
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.split(' ')[1] if auth_header.startswith('Bearer ') else None
        if token:
            deactivate_session(token)
        return jsonify({'message': 'Logged out successfully'})
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@candidate_bp.post('/change-password')
@authenticate_token
@require_candidate
def candidate_change_password():
    """Change password for logged-in candidate. Requires current password and new password."""
    try:
        data = request.get_json(force=True) or {}
        current_password = (data.get('currentPassword') or data.get('current_password') or '').strip()
        new_password = (data.get('newPassword') or data.get('new_password') or '').strip()
        if not current_password:
            return jsonify({'error': 'Current password is required'}), 400
        ok, err = validate_password_strength(new_password)
        if not ok:
            return jsonify({'error': err}), 400
        candidate_id = request.user['id']
        row = db_get('SELECT cid, email, password FROM candidate_signup WHERE cid = ?', (candidate_id,))
        if not row:
            return jsonify({'error': 'Account not found'}), 404
        stored_hash = row.get('password') or ''
        if not stored_hash:
            return jsonify({'error': 'Invalid current password'}), 401
        stored_b = stored_hash.encode('utf-8') if isinstance(stored_hash, str) else stored_hash
        if not bcrypt.checkpw(current_password.encode('utf-8'), stored_b):
            return jsonify({'error': 'Current password is incorrect'}), 401
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db_run('UPDATE candidate_signup SET password = ? WHERE cid = ?', (password_hash, candidate_id))
        return jsonify({'message': 'Password updated successfully'}), 200
    except Exception as e:
        print(f"Error in candidate_change_password: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@candidate_bp.get('/profile')
@authenticate_token
@require_candidate
def get_profile():
    try:
        user_id = request.user['id']
        # Exclude resume binary data from profile query (it's large and not needed here)
        profile = db_get('''
            SELECT candidate_id, full_name, email, phone,
                   experience_level, serving_notice, notice_period, last_working_day,
                   linkedin_url, portfolio_url, current_location, preferred_location,
                   completed, updated_at,
                   CASE WHEN resume IS NOT NULL THEN 1 ELSE 0 END as has_resume
            FROM candidate_profiles WHERE candidate_id = ?
        ''', (user_id,))
        if not profile:
            return jsonify({
                'experienceLevel': '',
                'servingNotice': '',
                'fullName': '',
                'email': request.user.get('email', ''),
                'phone': '',
                'noticePeriod': '',
                'lastWorkingDay': '',
                'linkedinUrl': '',
                'portfolioUrl': '',
                'currentLocation': '',
                'preferredLocation': '',
                'resumeFileName': '',
                'education': [],
                'certifications': [],
                'experiences': [],
                'completed': False
            })
        return jsonify(parse_profile(profile))
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@candidate_bp.post('/profile')
@authenticate_token
@require_candidate
def save_profile():
    try:
        # Handle both JSON and multipart/form-data
        is_multipart = request.content_type and 'multipart/form-data' in request.content_type
        
        if is_multipart:
            data = request.form.to_dict()
            # Parse JSON fields if they're sent as strings
            if 'education' in data and isinstance(data['education'], str):
                import json
                data['education'] = json.loads(data['education'])
            if 'certifications' in data and isinstance(data['certifications'], str):
                import json
                data['certifications'] = json.loads(data['certifications'])
            if 'experiences' in data and isinstance(data['experiences'], str):
                import json
                data['experiences'] = json.loads(data['experiences'])
        else:
            data = request.get_json(force=True) if request.is_json else {}
        
        candidate_id = request.user['id']
        existing = db_get('SELECT candidate_id FROM candidate_profiles WHERE candidate_id = ?', (candidate_id,))
        
        # Handle resume file upload - check both request.files and request.form
        resume_binary = None
        print(f"DEBUG: Content-Type: {request.content_type}")
        print(f"DEBUG: is_multipart: {is_multipart}")
        print(f"DEBUG: request.files: {request.files}")
        print(f"DEBUG: request.form keys: {list(request.form.keys()) if hasattr(request, 'form') else 'N/A'}")
        
        if is_multipart and request.files:
            # Debug: log available files
            print(f"DEBUG: Available files: {list(request.files.keys())}")
            # Check for resume in files
            if 'resume' in request.files:
                resume_file = request.files['resume']
                print(f"DEBUG: Resume file found: {resume_file.filename if resume_file else 'None'}")
                print(f"DEBUG: Resume file type: {type(resume_file)}")
                if resume_file and resume_file.filename:
                    # Reset file pointer to beginning (in case it was read before)
                    resume_file.seek(0)
                    # Read the file as binary
                    resume_binary = resume_file.read()
                    # Reset again for potential future reads
                    resume_file.seek(0)
                    print(f"DEBUG: Resume binary type: {type(resume_binary)}")
                    print(f"DEBUG: Resume binary size: {len(resume_binary) if resume_binary else 0} bytes")
                    if resume_binary and len(resume_binary) > 0:
                        # Ensure it's bytes
                        if not isinstance(resume_binary, bytes):
                            resume_binary = bytes(resume_binary)
                        print(f"DEBUG: Resume binary is bytes: {isinstance(resume_binary, bytes)}")
                        print(f"DEBUG: First 20 bytes (hex): {resume_binary[:20].hex() if len(resume_binary) >= 20 else resume_binary.hex()}")
                    else:
                        print(f"DEBUG: Resume binary is empty or None")
                        resume_binary = None
            else:
                print(f"DEBUG: 'resume' not found in request.files. Available keys: {list(request.files.keys())}")
        elif not is_multipart:
            # If JSON request, check if resume data is sent as base64 (for backward compatibility)
            resume_data = data.get('resume')
            if resume_data and isinstance(resume_data, str):
                import base64
                try:
                    resume_binary = base64.b64decode(resume_data)
                except:
                    resume_binary = None
        
        education_entries = data.get('education') or []
        certification_entries = data.get('certifications') or []
        experience_entries = data.get('experiences') or []
        
        if existing:
            # Only update resume if a new file is provided
            if resume_binary is not None and len(resume_binary) > 0:
                print(f"DEBUG: Updating profile with resume binary ({len(resume_binary)} bytes)")
                try:
                    resume_param = resume_binary if BACKEND == "postgresql" else (__import__("pyodbc").Binary(resume_binary) if resume_binary else None)
                    result = db_run(
                        '''
                        UPDATE candidate_profiles SET
                          full_name = ?, email = ?, phone = ?,
                          experience_level = ?, serving_notice = ?, notice_period = ?, last_working_day = ?,
                          linkedin_url = ?, portfolio_url = ?,
                          current_location = ?, preferred_location = ?,
                          resume = ?,
                          completed = ?,
                          updated_at = ''' + NOW_SQL + '''
                        WHERE candidate_id = ?
                        ''',
                        (
                            data.get('fullName'), data.get('email') or request.user.get('email'), data.get('phone'),
                            data.get('experienceLevel'), data.get('servingNotice'), data.get('noticePeriod'), data.get('lastWorkingDay'),
                            data.get('linkedinUrl'), data.get('portfolioUrl'),
                            data.get('currentLocation'), data.get('preferredLocation'),
                            resume_param,
                            (True if data.get('completed') else False) if BACKEND == 'postgresql' else (1 if data.get('completed') else 0),
                            candidate_id
                        )
                    )
                    print(f"DEBUG: Resume updated successfully. Rows affected: {result.get('changes', 0)}")
                    # Verify the update
                    verify = db_get('SELECT ' + ('LENGTH(resume)' if BACKEND == 'postgresql' else 'LEN(resume)') + ' as resume_size FROM candidate_profiles WHERE candidate_id = ?', (candidate_id,))
                    if verify:
                        print(f"DEBUG: Verification - Resume size in DB: {verify.get('resume_size', 'NULL')}")
                except Exception as e:
                    print(f"DEBUG: Error updating resume: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    raise
            else:
                print(f"DEBUG: No resume file provided, updating other fields only")
                # Update other fields but keep existing resume
                db_run(
                    '''
                    UPDATE candidate_profiles SET
                      full_name = ?, email = ?, phone = ?,
                      experience_level = ?, serving_notice = ?, notice_period = ?, last_working_day = ?,
                      linkedin_url = ?, portfolio_url = ?,
                      current_location = ?, preferred_location = ?,
                      completed = ?,
                      updated_at = ''' + NOW_SQL + '''
                    WHERE candidate_id = ?
                    ''',
                    (
                        data.get('fullName'), data.get('email') or request.user.get('email'), data.get('phone'),
                        data.get('experienceLevel'), data.get('servingNotice'), data.get('noticePeriod'), data.get('lastWorkingDay'),
                        data.get('linkedinUrl'), data.get('portfolioUrl'),
                        data.get('currentLocation'), data.get('preferredLocation'),
                        (True if data.get('completed') else False) if BACKEND == 'postgresql' else (1 if data.get('completed') else 0),
                        candidate_id
                    )
                )
        else:
            print(f"DEBUG: Creating new profile with resume binary ({len(resume_binary) if resume_binary else 0} bytes)")
            try:
                resume_param = resume_binary if BACKEND == "postgresql" else (__import__("pyodbc").Binary(resume_binary) if resume_binary else None)
                result = db_run(
                    '''
                    INSERT INTO candidate_profiles (
                      candidate_id, full_name, email, phone,
                      experience_level, serving_notice, notice_period, last_working_day,
                      linkedin_url, portfolio_url,
                      current_location, preferred_location,
                      resume,
                      completed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        candidate_id,
                        data.get('fullName'), data.get('email') or request.user.get('email'), data.get('phone'),
                        data.get('experienceLevel'), data.get('servingNotice'), data.get('noticePeriod'), data.get('lastWorkingDay'),
                        data.get('linkedinUrl'), data.get('portfolioUrl'),
                        data.get('currentLocation'), data.get('preferredLocation'),
                        resume_param,
                        (True if data.get('completed') else False) if BACKEND == 'postgresql' else (1 if data.get('completed') else 0)
                    )
                )
                print(f"DEBUG: Profile created successfully. Rows affected: {result.get('changes', 0)}")
                # Verify the insert
                verify = db_get('SELECT ' + ('LENGTH(resume)' if BACKEND == 'postgresql' else 'LEN(resume)') + ' as resume_size FROM candidate_profiles WHERE candidate_id = ?', (candidate_id,))
                if verify:
                    print(f"DEBUG: Verification - Resume size in DB: {verify.get('resume_size', 'NULL')}")
            except Exception as e:
                print(f"DEBUG: Error creating profile: {str(e)}")
                import traceback
                traceback.print_exc()
                raise
        # Refresh education records
        db_run('DELETE FROM candidate_education WHERE candidate_id = ?', (candidate_id,))
        for entry in education_entries:
            if not isinstance(entry, dict):
                continue
            degree = entry.get('degree')
            institution = entry.get('institution')
            cgpa = entry.get('cgpa') or entry.get('cgpaPercentage')
            start_date = entry.get('startMonth') or entry.get('start_date')
            end_date = entry.get('endMonth') or entry.get('end_date')
            if not degree and not institution and not cgpa and not start_date and not end_date:
                continue
            db_run(
                'INSERT INTO candidate_education (candidate_id, degree, institution, ' + CGPA_COL + ', start_date, end_date) VALUES (?, ?, ?, ?, ?, ?)',
                (candidate_id, degree, institution, cgpa, start_date, end_date)
            )
        # Refresh certification records
        db_run('DELETE FROM candidate_certifications WHERE candidate_id = ?', (candidate_id,))
        for entry in certification_entries:
            if not isinstance(entry, dict):
                continue
            certification = entry.get('certification') or entry.get('name')
            issuer = entry.get('issuer') or entry.get('authority')
            end_month = entry.get('endMonth') or entry.get('end_month')
            if not certification and not issuer and not end_month:
                continue
            db_run(
                '''
                INSERT INTO candidate_certifications (candidate_id, certification, issuer, end_month)
                VALUES (?, ?, ?, ?)
                ''',
                (candidate_id, certification, issuer, end_month)
            )
        # Refresh experience records
        db_run('DELETE FROM candidate_experiences WHERE candidate_id = ?', (candidate_id,))
        for entry in experience_entries:
            if not isinstance(entry, dict):
                continue
            company = entry.get('company')
            role = entry.get('role')
            start_date = entry.get('startMonth') or entry.get('start_date')
            end_date = entry.get('endMonth') or entry.get('end_date')
            is_current = entry.get('isCurrent', False)
            # If isCurrent is true, set present to 'yes' and clear end_date
            # If end_date is provided, set present to 'no'
            if is_current:
                present = 'yes'
                end_date = None
            elif end_date:
                present = 'no'
            else:
                present = 'no'  # Default to 'no' if neither is set
            if not company and not role and not start_date:
                continue
            db_run(
                '''
                INSERT INTO candidate_experiences (candidate_id, company, role, start_date, end_date, present)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (candidate_id, company, role, start_date, end_date, present)
            )
        
        # Recalculate matching percentage for all existing applications
        # This ensures that when a candidate updates their profile/resume, 
        # the matching scores are updated based on the latest profile data
        try:
            existing_applications = db_all(
                'SELECT DISTINCT job_id FROM applications WHERE candidate_id = ?',
                (candidate_id,)
            )
            for app in existing_applications:
                job_id = app.get('job_id')
                if job_id:
                    new_matching_percentage = calculate_matching_percentage(candidate_id, job_id)
                    db_run(
                        'UPDATE applications SET matching_percentage = ? WHERE candidate_id = ? AND job_id = ?',
                        (new_matching_percentage, candidate_id, job_id)
                    )
            print(f"DEBUG: Recalculated matching percentage for {len(existing_applications)} applications")
        except Exception as e:
            # Don't fail the profile save if recalculation fails
            print(f"WARNING: Failed to recalculate matching percentages: {e}")
            import traceback
            traceback.print_exc()
        
        return jsonify({'message': 'Profile saved successfully'})
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


def _read_resume_from_storage_url(storage_url: str) -> bytes | None:
    """Read file bytes from a file:// storage URL (local path)."""
    if not storage_url or not str(storage_url).strip().startswith('file://'):
        return None
    path = str(storage_url).replace('file://', '').lstrip('/')
    if os.name == 'nt' and path.startswith('/'):
        path = path[1:]
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'rb') as f:
            return f.read()
    except Exception:
        return None


@candidate_bp.get('/resume')
@authenticate_token
@require_candidate
def get_resume():
    """Download the candidate's resume (from profile or latest upload before save)."""
    try:
        candidate_id = request.user['id']
        profile = db_get(
            '''
            SELECT resume
            FROM candidate_profiles
            WHERE candidate_id = ?
            ''',
            (candidate_id,)
        )
        resume_data = None
        filename = 'resume.pdf'
        if profile and profile.get('resume'):
            resume_data = _resume_bytes(profile.get('resume'))
        if not resume_data:
            # Fallback: serve latest uploaded resume from parse flow (raw_files) so "View" works before profile save
            raw = db_get(
                '''
                SELECT storage_url, original_filename
                FROM raw_files
                WHERE uploader_id = ? AND uploader_role = 'candidate'
                ORDER BY created_at DESC
                LIMIT 1
                ''',
                (candidate_id,)
            )
            if raw and raw.get('storage_url'):
                resume_data = _read_resume_from_storage_url(raw.get('storage_url'))
                if raw.get('original_filename'):
                    filename = raw.get('original_filename') or filename
        if not resume_data:
            return jsonify({'error': 'Resume not found'}), 404
        return Response(
            resume_data,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': 'application/pdf'
            }
        )
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


def parse_profile(profile: dict) -> dict:
    education_rows = db_all(
        'SELECT degree, institution, ' + CGPA_COL + ' as cgpa, start_date, end_date FROM candidate_education WHERE candidate_id = ? ORDER BY degree',
        (profile.get('candidate_id'),)
    ) if profile.get('candidate_id') else []
    formatted_education = [
        {
            'degree': row.get('degree') or '',
            'institution': row.get('institution') or '',
            'cgpa': row.get('cgpa') or '',
            'startMonth': row.get('start_date') or '',
            'endMonth': row.get('end_date') or '',
        }
        for row in (education_rows or [])
    ]
    certification_rows = db_all(
        '''
        SELECT certification, issuer, end_month
        FROM candidate_certifications
        WHERE candidate_id = ?
        ORDER BY certification
        ''',
        (profile.get('candidate_id'),)
    ) if profile.get('candidate_id') else []
    formatted_certifications = [
        {
            'certification': row.get('certification') or '',
            'issuer': row.get('issuer') or '',
            'endMonth': row.get('end_month') or '',
        }
        for row in (certification_rows or [])
    ]
    experience_rows = db_all(
        '''
        SELECT company, role, start_date, end_date, present
        FROM candidate_experiences
        WHERE candidate_id = ?
        ORDER BY company
        ''',
        (profile.get('candidate_id'),)
    ) if profile.get('candidate_id') else []
    formatted_experiences = [
        {
            'company': row.get('company') or '',
            'role': row.get('role') or '',
            'startMonth': row.get('start_date') or '',
            'endMonth': row.get('end_date') or '',
            'isCurrent': (row.get('present') or '').lower() == 'yes',
        }
        for row in (experience_rows or [])
    ]
    return {
        'experienceLevel': profile.get('experience_level') or '',
        'servingNotice': profile.get('serving_notice') or '',
        'fullName': profile.get('full_name') or '',
        'email': profile.get('email') or '',
        'phone': profile.get('phone') or '',
        'noticePeriod': profile.get('notice_period') or '',
        'lastWorkingDay': profile.get('last_working_day') or '',
        'linkedinUrl': profile.get('linkedin_url') or '',
        'portfolioUrl': profile.get('portfolio_url') or '',
        'currentLocation': profile.get('current_location') or '',
        'preferredLocation': profile.get('preferred_location') or '',
        'resumeFileName': _resume_filename(profile),
        'education': formatted_education,
        'certifications': formatted_certifications,
        'experiences': formatted_experiences,
        'completed': bool(profile.get('completed')),
    }


@candidate_bp.get('/profile/<string:candidate_id>')
@authenticate_token
@require_hr
def get_profile_admin(candidate_id: str):
    """Allow HR/admins to view any candidate profile with full details."""
    try:
        profile = db_get(
            '''
            SELECT candidate_id, full_name, email, phone,
                   experience_level, serving_notice, notice_period, last_working_day,
                   linkedin_url, portfolio_url, current_location, preferred_location,
                   completed, updated_at,
                   CASE WHEN resume IS NOT NULL THEN 1 ELSE 0 END as has_resume
            FROM candidate_profiles
            WHERE candidate_id = ?
            ''',
            (candidate_id,)
        )
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404

        return jsonify(parse_profile(profile))
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


def _resume_filename(profile: dict) -> str:
    """Return resume file name if profile has a resume stored (handles different DB column types)."""
    if not profile:
        return ''
    has_resume = profile.get('has_resume')
    if has_resume is not None and has_resume != '' and has_resume != 0:
        return 'resume.pdf'
    if profile.get('resume') is not None:
        return 'resume.pdf'
    return ''


def _resume_bytes(data):
    """Convert resume blobs (bytes, bytearray, memoryview, etc.) into raw bytes."""
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
