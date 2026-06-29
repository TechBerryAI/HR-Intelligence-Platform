"""
Simple candidate auth routes using only pyodbc (no SQLAlchemy conflicts)
This bypasses the SQLAlchemy session timeout issue
"""
import os
import bcrypt
import jwt
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from db import db_get, db_run, db_all, BACKEND, NOW_SQL, TRUE_SQL
from helpers.otp_utils import (
    generate_otp,
    is_valid_email,
    send_email_otp,
    parse_otp_expiry,
    utc_now_aware,
    normalize_to_utc_aware,
)


def _otp_expiry_utc():
    """OTP valid for 5 minutes from now, as timezone-aware UTC (so PG stores correct instant)."""
    return utc_now_aware() + timedelta(minutes=5)
from utils import build_jwt_payload, validate_password_strength

simple_candidate_auth_bp = Blueprint('simple_candidate_auth', __name__)
# PostgreSQL requires quoted identifiers for mixed-case table names
CAUTH_T = '"CandidateAuth"' if BACKEND == 'postgresql' else 'CandidateAuth'

JWT_SECRET = os.getenv(
    'JWT_SECRET',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE',
)


@simple_candidate_auth_bp.post('/signup')
def candidate_signup():
    """Simple signup using only pyodbc - stores OTP for verification"""
    try:
        data = request.get_json(force=True) or {}
        name = (data.get('name') or '').strip()
        email_input = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        
        print(f"[SIGNUP] Attempting signup for: {email_input}")
        
        # Validation
        if not name:
            return jsonify({'error': 'Name is required.'}), 400
        if not email_input:
            return jsonify({'error': 'Email is required.'}), 400
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters.'}), 400
        
        # Validate email format
        if not is_valid_email(email_input):
            return jsonify({'error': 'Please provide a valid email address.'}), 400
        
        email = email_input
        
        # Generate OTP and expiry (use aware UTC so PostgreSQL stores correct instant)
        otp = generate_otp()
        expiry = _otp_expiry_utc()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        print(f"[CANDIDATE SIGNUP] Generated OTP for {email}: {otp}")
        
        # Check if candidate already exists in CandidateAuth table
        existing = db_get(
            'SELECT id, is_verified FROM ' + CAUTH_T + ' WHERE email = ?',
            (email,)
        )
        
        if existing:
            if existing.get('is_verified'):
                return jsonify({'error': 'Account already exists. Please login.'}), 400
            
            # Update existing unverified record with new OTP
            db_run(
                'UPDATE ' + CAUTH_T + ' SET name = ?, password_hash = ?, otp = ?, otp_expiry = ?, updated_at = ' + NOW_SQL + ' WHERE email = ?',
                (name, password_hash, otp, expiry, email)
            )
            print(f"[CANDIDATE SIGNUP] Updated existing unverified account for: {email} with OTP: {otp}")
        else:
            # Insert new candidate auth record (is_verified: boolean in PG, bit in MSSQL - use param)
            db_run(
                'INSERT INTO ' + CAUTH_T + ' (name, email, password_hash, otp, otp_expiry, is_verified, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ' + NOW_SQL + ', ' + NOW_SQL + ')',
                (name, email, password_hash, otp, expiry, False if BACKEND == 'postgresql' else 0)
            )
            print(f"[CANDIDATE SIGNUP] Created new candidate auth for: {email} with OTP: {otp}")
        
        # Verify what was actually stored in the database
        try:
            stored_candidate = db_get('SELECT otp FROM ' + CAUTH_T + ' WHERE email = ?', (email,))
            if stored_candidate:
                print(f"[CANDIDATE SIGNUP] OTP in database after save: {stored_candidate.get('otp')}")
            else:
                print(f"[CANDIDATE SIGNUP] WARNING: Could not find CandidateAuth record for {email}")
        except Exception as verify_error:
            print(f"[CANDIDATE SIGNUP] Error verifying stored OTP: {verify_error}")
        
        # Send OTP via email
        print(f"[CANDIDATE SIGNUP] About to send OTP via email: {otp}")
        otp_sent = send_email_otp(email, otp, user_type="Candidate")
        
        if not otp_sent:
            return jsonify({'error': 'Unable to send OTP. Please try again later.'}), 500
        
        print(f"[CANDIDATE SIGNUP] OTP sent successfully to: {email}")
        return jsonify({'message': 'OTP sent successfully. Please check your email.'}), 200
        
    except Exception as e:
        print(f"[SIGNUP ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Signup failed. Please try again.'}), 500


@simple_candidate_auth_bp.post('/verify-otp')
def verify_candidate_otp():
    """Verify OTP and create candidate_signup record"""
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        otp = (data.get('otp') or '').strip()
        
        print(f"[VERIFY-OTP] Attempting verification for: {email}")
        
        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400
        
        # Get candidate from CandidateAuth
        candidate = db_get(
            'SELECT id, name, email, password_hash, otp, otp_expiry, is_verified FROM ' + CAUTH_T + ' WHERE email = ?',
            (email,)
        )
        
        if not candidate:
            return jsonify({'error': 'No signup found. Please signup first.'}), 404
        
        if candidate.get('is_verified'):
            return jsonify({'error': 'Account already verified. Please login.'}), 400
        
        # Check OTP
        stored_otp = candidate.get('otp')
        input_otp = str(otp).strip()
        if not stored_otp or str(stored_otp).strip() != input_otp:
            return jsonify({'error': 'Invalid OTP. Please try again.'}), 400
        
        # Check expiry (PG returns timezone-aware timestamps; use aware UTC for comparison)
        otp_expiry = parse_otp_expiry(candidate.get('otp_expiry'))
        if not otp_expiry:
            return jsonify({'error': 'OTP expired. Please request a new one.'}), 400
        now_utc = utc_now_aware()
        otp_expiry_utc = normalize_to_utc_aware(otp_expiry)
        if now_utc > otp_expiry_utc:
            return jsonify({'error': 'OTP expired. Please request a new one.'}), 400
        
        # Mark as verified in CandidateAuth (is_verified: boolean in PG)
        db_run(
            'UPDATE ' + CAUTH_T + ' SET is_verified = ?, otp = NULL, otp_expiry = NULL, updated_at = ' + NOW_SQL + ' WHERE email = ?',
            (True if BACKEND == 'postgresql' else 1, email)
        )
        
        # Create or update candidate_signup record
        existing_signup = db_get(
            'SELECT cid FROM candidate_signup WHERE email = ?',
            (email,)
        )
        
        if existing_signup:
            # Update existing
            cid = existing_signup['cid']
            db_run(
                'UPDATE candidate_signup SET name = ?, password = ? WHERE cid = ?',
                (candidate['name'], candidate['password_hash'], cid)
            )
            print(f"[VERIFY-OTP] Updated existing candidate_signup for: {email}, cid: {cid}")
        else:
            # Insert new - let SQL Server generate CID automatically
            result = db_run(
                'INSERT INTO candidate_signup (name, email, password) VALUES (?, ?, ?)',
                (candidate['name'], email, candidate['password_hash'])
            )
            
            # Fetch the newly created cid
            if BACKEND == "postgresql":
                new_signup = db_get('SELECT cid FROM candidate_signup WHERE email = ? ORDER BY created_at DESC LIMIT 1', (email,))
            else:
                new_signup = db_get('SELECT TOP 1 cid FROM candidate_signup WHERE email = ? ORDER BY created_at DESC', (email,))
            
            if not new_signup:
                return jsonify({'error': 'Account creation failed. Please try again.'}), 500
            
            cid = new_signup['cid']
            print(f"[VERIFY-OTP] Created new candidate_signup for: {email}, cid: {cid}")
        
        print(f"[VERIFY-OTP] Verification successful for: {email}")
        return jsonify({
            'message': 'OTP verified successfully. Account created.',
            'cid': cid
        }), 200
        
    except Exception as e:
        print(f"[VERIFY-OTP ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Verification failed. Please try again.'}), 500


@simple_candidate_auth_bp.post('/resend-otp')
def resend_candidate_otp():
    """Resend OTP to candidate's email"""
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        
        print(f"[RESEND-OTP] Attempting to resend OTP for: {email}")
        
        if not email:
            return jsonify({'error': 'Email is required.'}), 400
        
        # Get candidate from CandidateAuth
        candidate = db_get(
            'SELECT id, email, is_verified FROM ' + CAUTH_T + ' WHERE email = ?',
            (email,)
        )
        
        if not candidate:
            return jsonify({'error': 'No signup found. Please signup first.'}), 404
        
        if candidate.get('is_verified'):
            return jsonify({'error': 'Account already verified. Please login.'}), 400
        
        # Generate new OTP (use aware UTC so PostgreSQL stores correct instant)
        otp = generate_otp()
        expiry = _otp_expiry_utc()
        
        # Update OTP in database
        db_run(
            'UPDATE ' + CAUTH_T + ' SET otp = ?, otp_expiry = ?, updated_at = ' + NOW_SQL + ' WHERE email = ?',
            (otp, expiry, email)
        )
        
        # Send OTP via email
        otp_sent = send_email_otp(email, otp, user_type="Candidate")
        
        if not otp_sent:
            return jsonify({'error': 'Unable to send OTP. Please try again later.'}), 500
        
        print(f"[RESEND-OTP] OTP resent successfully to: {email}")
        return jsonify({'message': 'OTP resent successfully. Please check your email.'}), 200
        
    except Exception as e:
        print(f"[RESEND-OTP ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to resend OTP. Please try again.'}), 500


@simple_candidate_auth_bp.post('/login')
def simple_candidate_login():
    """Simple login using only pyodbc - no SQLAlchemy session conflicts"""
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        
        print(f"[LOGIN] Attempting login for: {email}")
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Query using pyodbc directly - fast and reliable
        candidate = db_get(
            'SELECT cid, name, email, password FROM candidate_signup WHERE email = ?',
            (email,)
        )
        
        if not candidate:
            hr_account = db_get(
                'SELECT hrid FROM hr_signup WHERE LOWER(TRIM(email)) = ?',
                (email,)
            )
            if hr_account:
                print(f"[LOGIN] HR account used on candidate login: {email}")
                return jsonify({
                    'error': 'This email is registered as HR/Admin, not as a job applicant. Please sign in at HR / Admin Login.',
                    'code': 'hr_account',
                    'loginPath': '/login/admin',
                }), 401
            print(f"[LOGIN] No candidate found for: {email}")
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Verify password
        stored_hash = candidate['password'] or ''
        if not stored_hash:
            print(f"[LOGIN] No password hash for: {email}")
            return jsonify({'error': 'Invalid credentials'}), 401
            
        try:
            if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                print(f"[LOGIN] Invalid password for: {email}")
                return jsonify({'error': 'Invalid credentials'}), 401
        except Exception as e:
            print(f"[LOGIN] Password check error: {e}")
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Generate JWT access + refresh tokens
        identity = {'user_id': candidate['cid'], 'email': candidate['email'], 'role': 'CANDIDATE'}
        access_token = jwt.encode(
            build_jwt_payload(identity, refresh=False),
            JWT_SECRET,
            algorithm='HS256'
        )
        refresh_token = jwt.encode(
            build_jwt_payload(identity, refresh=True),
            JWT_SECRET,
            algorithm='HS256'
        )
        
        # Get profile if exists
        profile = db_get(
            'SELECT * FROM candidate_profiles WHERE candidate_id = ?',
            (candidate['cid'],)
        )
        
        user_data = {
            'id': candidate['cid'],
            'name': candidate['name'],
            'email': candidate['email'],
            'role': 'CANDIDATE'
        }
        
        if profile:
            user_data['profile'] = {
                'phone': profile.get('phone'),
                'location': profile.get('location'),
                'bio': profile.get('bio'),
            }
        
        print(f"[LOGIN] Success for: {email}")
        return jsonify({
            'token': access_token,
            'refresh_token': refresh_token,
            'user': user_data
        }), 200
        
    except Exception as e:
        print(f"[LOGIN ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'An unexpected error occurred during login. Please contact support if the issue persists.'}), 500


def _upsert_candidate_auth_otp(email, name, password_hash, otp, expiry):
    """Store password-reset OTP on CandidateAuth for an existing candidate."""
    existing = db_get('SELECT id FROM ' + CAUTH_T + ' WHERE email = ?', (email,))
    if existing:
        db_run(
            'UPDATE ' + CAUTH_T + ' SET name = ?, password_hash = ?, otp = ?, otp_expiry = ?, is_verified = ?, updated_at = ' + NOW_SQL + ' WHERE email = ?',
            (name, password_hash, otp, expiry, True if BACKEND == 'postgresql' else 1, email),
        )
    else:
        db_run(
            'INSERT INTO ' + CAUTH_T + ' (name, email, password_hash, otp, otp_expiry, is_verified, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ' + NOW_SQL + ', ' + NOW_SQL + ')',
            (name, email, password_hash, otp, expiry, True if BACKEND == 'postgresql' else 1),
        )


@simple_candidate_auth_bp.post('/forgot-password')
def candidate_forgot_password():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        if not email:
            return jsonify({'error': 'Email is required.'}), 400
        if not is_valid_email(email):
            return jsonify({'error': 'Please provide a valid email address.'}), 400

        candidate = db_get(
            'SELECT cid, name, email, password FROM candidate_signup WHERE LOWER(TRIM(email)) = ?',
            (email,),
        )
        if not candidate:
            return jsonify({'error': 'Account not found for this email.'}), 404

        otp = generate_otp()
        expiry = utc_now_aware() + timedelta(minutes=10)
        _upsert_candidate_auth_otp(
            email,
            candidate.get('name') or '',
            candidate.get('password') or '',
            otp,
            expiry,
        )
        if not send_email_otp(email, otp, user_type='Candidate'):
            return jsonify({'error': 'Failed to send OTP email. Please try again later.'}), 500
        return jsonify({'message': 'OTP sent successfully. Please check your email.'}), 200
    except Exception as e:
        print(f'[CANDIDATE FORGOT-PASSWORD ERROR] {type(e).__name__}: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@simple_candidate_auth_bp.post('/forgot-password/verify-otp')
def candidate_verify_reset_otp():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        otp = (data.get('otp') or '').strip()
        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400

        row = db_get(
            'SELECT otp, otp_expiry FROM ' + CAUTH_T + ' WHERE email = ?',
            (email,),
        )
        if not row or not row.get('otp'):
            return jsonify({'error': 'Please request a new OTP.'}), 400
        if str(row.get('otp')).strip() != str(otp).strip():
            return jsonify({'error': 'Invalid OTP.'}), 400

        otp_expiry = parse_otp_expiry(row.get('otp_expiry'))
        if not otp_expiry or utc_now_aware() > normalize_to_utc_aware(otp_expiry):
            return jsonify({'error': 'OTP expired. Please request a new one.'}), 400
        return jsonify({'message': 'OTP verified. You may set a new password.'}), 200
    except Exception as e:
        print(f'[CANDIDATE VERIFY RESET OTP ERROR] {type(e).__name__}: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@simple_candidate_auth_bp.post('/reset-password')
def candidate_reset_password():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        otp = (data.get('otp') or '').strip()
        new_password = data.get('newPassword') or data.get('password') or ''
        confirm_password = data.get('confirmPassword') or data.get('confirm_password') or ''

        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400
        ok, err = validate_password_strength(new_password)
        if not ok:
            return jsonify({'error': err}), 400
        if new_password != confirm_password:
            return jsonify({'error': 'Passwords do not match.'}), 400

        signup = db_get('SELECT cid, name FROM candidate_signup WHERE LOWER(TRIM(email)) = ?', (email,))
        if not signup:
            return jsonify({'error': 'Account not found for this email.'}), 404

        row = db_get(
            'SELECT otp, otp_expiry FROM ' + CAUTH_T + ' WHERE email = ?',
            (email,),
        )
        if not row or not row.get('otp'):
            return jsonify({'error': 'Please request a new OTP.'}), 400
        if str(row.get('otp')).strip() != str(otp).strip():
            return jsonify({'error': 'Invalid OTP.'}), 400
        otp_expiry = parse_otp_expiry(row.get('otp_expiry'))
        if not otp_expiry or utc_now_aware() > normalize_to_utc_aware(otp_expiry):
            return jsonify({'error': 'OTP expired. Please request a new one.'}), 400

        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db_run('UPDATE candidate_signup SET password = ? WHERE cid = ?', (password_hash, signup['cid']))
        db_run(
            'UPDATE ' + CAUTH_T + ' SET password_hash = ?, otp = NULL, otp_expiry = NULL, updated_at = ' + NOW_SQL + ' WHERE email = ?',
            (password_hash, email),
        )
        return jsonify({'message': 'Password updated successfully. You can now login.'}), 200
    except Exception as e:
        print(f'[CANDIDATE RESET PASSWORD ERROR] {type(e).__name__}: {e}')
        return jsonify({'error': 'Internal server error'}), 500
