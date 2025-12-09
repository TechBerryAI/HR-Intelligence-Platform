"""
Simple candidate auth routes using only pyodbc (no SQLAlchemy conflicts)
This bypasses the SQLAlchemy session timeout issue
"""
import os
import bcrypt
import jwt
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from db import db_get, db_run, db_all
from helpers.otp_utils import (
    generate_otp,
    is_valid_email,
    send_email_otp,
    parse_otp_expiry
)

simple_candidate_auth_bp = Blueprint('simple_candidate_auth', __name__)

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
        
        # Generate OTP and expiry
        otp = generate_otp()
        expiry = datetime.utcnow() + timedelta(minutes=5)
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        print(f"[CANDIDATE SIGNUP] Generated OTP for {email}: {otp}")
        
        # Check if candidate already exists in CandidateAuth table
        existing = db_get(
            'SELECT id, is_verified FROM CandidateAuth WHERE email = ?',
            (email,)
        )
        
        if existing:
            if existing.get('is_verified'):
                return jsonify({'error': 'Account already exists. Please login.'}), 400
            
            # Update existing unverified record with new OTP
            db_run(
                '''UPDATE CandidateAuth 
                   SET name = ?, password_hash = ?, otp = ?, otp_expiry = ?, updated_at = SYSUTCDATETIME()
                   WHERE email = ?''',
                (name, password_hash, otp, expiry, email)
            )
            print(f"[CANDIDATE SIGNUP] Updated existing unverified account for: {email} with OTP: {otp}")
        else:
            # Insert new candidate auth record
            db_run(
                '''INSERT INTO CandidateAuth (name, email, password_hash, otp, otp_expiry, is_verified, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 0, SYSUTCDATETIME(), SYSUTCDATETIME())''',
                (name, email, password_hash, otp, expiry)
            )
            print(f"[CANDIDATE SIGNUP] Created new candidate auth for: {email} with OTP: {otp}")
        
        # Verify what was actually stored in the database
        try:
            stored_candidate = db_get('SELECT otp FROM CandidateAuth WHERE email = ?', (email,))
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
            'SELECT id, name, email, password_hash, otp, otp_expiry, is_verified FROM CandidateAuth WHERE email = ?',
            (email,)
        )
        
        if not candidate:
            return jsonify({'error': 'No signup found. Please signup first.'}), 404
        
        if candidate.get('is_verified'):
            return jsonify({'error': 'Account already verified. Please login.'}), 400
        
        # Check OTP
        stored_otp = candidate.get('otp')
        if not stored_otp or stored_otp != otp:
            return jsonify({'error': 'Invalid OTP. Please try again.'}), 400
        
        # Check expiry
        otp_expiry = parse_otp_expiry(candidate.get('otp_expiry'))
        if not otp_expiry or datetime.utcnow() > otp_expiry:
            return jsonify({'error': 'OTP expired. Please request a new one.'}), 400
        
        # Mark as verified in CandidateAuth
        db_run(
            'UPDATE CandidateAuth SET is_verified = 1, otp = NULL, otp_expiry = NULL, updated_at = SYSUTCDATETIME() WHERE email = ?',
            (email,)
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
            new_signup = db_get(
                'SELECT TOP 1 cid FROM candidate_signup WHERE email = ? ORDER BY created_at DESC',
                (email,)
            )
            
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
            'SELECT id, email, is_verified FROM CandidateAuth WHERE email = ?',
            (email,)
        )
        
        if not candidate:
            return jsonify({'error': 'No signup found. Please signup first.'}), 404
        
        if candidate.get('is_verified'):
            return jsonify({'error': 'Account already verified. Please login.'}), 400
        
        # Generate new OTP
        otp = generate_otp()
        expiry = datetime.utcnow() + timedelta(minutes=5)
        
        # Update OTP in database
        db_run(
            'UPDATE CandidateAuth SET otp = ?, otp_expiry = ?, updated_at = SYSUTCDATETIME() WHERE email = ?',
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
        
        # Generate JWT token
        token = jwt.encode(
            {
                'id': candidate['cid'],
                'email': candidate['email'],
                'role': 'candidate'
            },
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
            'role': 'candidate'
        }
        
        if profile:
            user_data['profile'] = {
                'phone': profile.get('phone'),
                'location': profile.get('location'),
                'bio': profile.get('bio'),
            }
        
        print(f"[LOGIN] Success for: {email}")
        return jsonify({
            'token': token,
            'user': user_data
        }), 200
        
    except Exception as e:
        print(f"[LOGIN ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Login failed. Please try again.'}), 500


@simple_candidate_auth_bp.get('/profile')
def get_candidate_profile():
    """Get candidate profile - simple version"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            cid = payload.get('id')
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        # Get candidate info
        candidate = db_get(
            'SELECT cid, name, email FROM candidate_signup WHERE cid = ?',
            (cid,)
        )
        
        if not candidate:
            return jsonify({'error': 'Candidate not found'}), 404
        
        # Get profile
        profile = db_get(
            'SELECT * FROM candidate_profiles WHERE candidate_id = ?',
            (cid,)
        )
        
        result = {
            'id': candidate['cid'],
            'name': candidate['name'],
            'email': candidate['email'],
            'role': 'candidate'
        }
        
        if profile:
            result['profile'] = {
                'phone': profile.get('phone'),
                'location': profile.get('location'),
                'bio': profile.get('bio'),
                'skills': profile.get('skills'),
                'experience_years': profile.get('experience_years'),
            }
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"[PROFILE ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to get profile'}), 500

