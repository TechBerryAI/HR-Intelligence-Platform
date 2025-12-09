import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from candidate import parse_profile
from db import db_get, db_run
from helpers.email_utils import send_notification_email
from helpers.otp_utils import (
    generate_otp,
    is_valid_email,
    is_valid_indian_phone,
    normalize_phone,
    parse_otp_expiry,
    send_email_otp,
    send_sms_otp,
)
from models import get_session
from models.candidate_auth import CandidateAuth
from sessions_service import get_recent_failed_attempts, record_login_attempt

candidate_auth_bp = Blueprint('candidate_auth', __name__)

JWT_SECRET = os.getenv(
    'JWT_SECRET',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE',
)


def _find_candidate(session, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[CandidateAuth]:
    filters = []
    if email:
        filters.append(CandidateAuth.email == email)
    if phone:
        filters.append(CandidateAuth.phone == phone)
    if not filters:
        return None
    return session.query(CandidateAuth).filter(or_(*filters)).first()


def _resolve_signup_email(email: Optional[str], phone: Optional[str]) -> Optional[str]:
    if email:
        return email
    if phone:
        return f"phone_{phone}@jobportal.local"
    return None


def _ensure_candidate_signup(name: str, email: Optional[str], phone: Optional[str], password_hash: str) -> Optional[str]:
    try:
        target_email = _resolve_signup_email(email, phone)
        if not target_email:
            print(f"Error: Could not resolve signup email for email={email}, phone={phone}")
            return None
        
        # Check if candidate already exists
        existing = db_get('SELECT cid FROM candidate_signup WHERE email = ?', (target_email,))
        if existing:
            # Update existing candidate
            try:
                db_run(
                    'UPDATE candidate_signup SET name = ?, password = ? WHERE cid = ?',
                    (name, password_hash, existing['cid']),
                )
                return existing['cid']
            except Exception as e:
                print(f"Error updating existing candidate: {e}")
                # If update fails, try to return existing cid anyway
                return existing['cid']
        
        # Insert new candidate - handle potential unique constraint violation
        try:
            db_run(
                'INSERT INTO candidate_signup (name, email, password) VALUES (?, ?, ?)',
                (name, target_email, password_hash),
            )
        except Exception as insert_error:
            # If insert fails (e.g., unique constraint), check if record was created
            print(f"Insert failed, checking if record exists: {insert_error}")
            existing_after = db_get('SELECT cid FROM candidate_signup WHERE email = ?', (target_email,))
            if existing_after:
                # Record exists, update it
                try:
                    db_run(
                        'UPDATE candidate_signup SET name = ?, password = ? WHERE cid = ?',
                        (name, password_hash, existing_after['cid']),
                    )
                    return existing_after['cid']
                except Exception as update_error:
                    print(f"Update failed after insert error: {update_error}")
                    return existing_after['cid']  # Return cid anyway
            else:
                raise  # Re-raise if it's a different error
        
        # Fetch the newly created cid
        row = db_get('SELECT TOP 1 cid FROM candidate_signup WHERE email = ?', (target_email,))
        if not row:
            print(f"Error: Failed to retrieve cid after insert for email={target_email}")
            return None
        
        return row['cid']
    except Exception as e:
        print(f"Error in _ensure_candidate_signup: {e}")
        import traceback
        traceback.print_exc()
        return None


def _bootstrap_legacy_candidate(session, email: str) -> Optional[CandidateAuth]:
    legacy = db_get(
        'SELECT TOP 1 name, email, password FROM candidate_signup WHERE email = ?',
        (email,),
    )
    if not legacy:
        return None
    candidate = CandidateAuth(
        name=legacy['name'],
        email=legacy['email'],
        phone=None,
        password_hash=legacy['password'],
        otp=None,
        otp_expiry=None,
        is_verified=True,
    )
    session.add(candidate)
    session.flush()
    session.refresh(candidate)
    return candidate


@candidate_auth_bp.post('/signup')
def candidate_signup():
    data = request.get_json(force=True) or {}
    name = (data.get('name') or '').strip()
    email_input = (data.get('email') or '').strip().lower()
    phone_raw = data.get('phone')
    phone = normalize_phone(phone_raw)
    password = data.get('password') or ''

    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    if not email_input and not phone:
        return jsonify({'error': 'Email or phone is required.'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters.'}), 400

    email_valid = is_valid_email(email_input) if email_input else False
    email = email_input or None
    phone_valid = is_valid_indian_phone(phone)
    if not (email_valid or phone_valid):
        return jsonify({'error': 'Provide a valid email address or 10-digit Indian phone number.'}), 400

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=5)

    with get_session() as session:
        existing_email = session.query(CandidateAuth).filter(CandidateAuth.email == email).first() if email else None
        existing_phone = session.query(CandidateAuth).filter(CandidateAuth.phone == phone).first() if phone else None

        if existing_email and existing_phone and existing_email.id != existing_phone.id:
            return jsonify({'error': 'Email and phone belong to different accounts.'}), 400

        candidate = existing_email or existing_phone
        if candidate and candidate.is_verified:
            return jsonify({'error': 'Account already exists. Please login.'}), 400

        if not candidate:
            candidate = CandidateAuth(
                name=name,
                email=email,
                phone=phone,
                password_hash=password_hash,
                otp=otp,
                otp_expiry=expiry,
                is_verified=False,
            )
            session.add(candidate)
        else:
            candidate.name = name
            candidate.email = email or candidate.email
            candidate.phone = phone or candidate.phone
            candidate.password_hash = password_hash
            candidate.otp = otp
            candidate.otp_expiry = expiry
            candidate.is_verified = False

    otp_sent = False
    if email_valid and email:
        otp_sent = send_email_otp(email, otp, user_type="Candidate")
        if not otp_sent and phone_valid:
            otp_sent = send_sms_otp(phone, otp)
    elif phone_valid:
        otp_sent = send_sms_otp(phone, otp)

    if not otp_sent:
        return jsonify({'error': 'Unable to send OTP. Please try again later.'}), 500

    return jsonify({'message': 'OTP sent successfully.'}), 200


@candidate_auth_bp.post('/verify-otp')
def verify_candidate_otp():
    try:
        data = request.get_json(force=True) or {}
        email_input = (data.get('email') or '').strip().lower()
        phone = normalize_phone(data.get('phone'))
        otp = (data.get('otp') or '').strip()

        if not otp:
            return jsonify({'error': 'OTP is required.'}), 400
        
        if not email_input and not phone:
            return jsonify({'error': 'Email or phone is required.'}), 400

        # Verify OTP in CandidateAuth table
        candidate_data = None
        try:
            print(f"Starting OTP verification for email={email_input}, otp={otp}")
            with get_session() as session:
                print(f"Session created, searching for candidate...")
                candidate = _find_candidate(session, email=email_input or None, phone=phone or None)
                if not candidate:
                    print(f"Candidate not found for email={email_input}, phone={phone}")
                    return jsonify({'error': 'Candidate not found. Please signup again.'}), 404
                
                print(f"Found candidate: name={candidate.name}, email={candidate.email}, otp={candidate.otp}, otp_type={type(candidate.otp)}")
                
                # Convert both OTPs to strings for comparison (handles int/string mismatch)
                stored_otp = str(candidate.otp).strip() if candidate.otp else None
                input_otp = str(otp).strip()
                
                if not stored_otp or stored_otp != input_otp:
                    print(f"Invalid OTP for candidate. Expected={stored_otp}, Got={input_otp}")
                    return jsonify({'error': 'Invalid OTP. Please check and try again.'}), 400
                
                # Check OTP expiry - ensure it's a datetime object before comparison
                current_time = datetime.utcnow()
                otp_expiry_raw = candidate.otp_expiry
                
                print(f"OTP expiry raw type: {type(otp_expiry_raw)}, value: {otp_expiry_raw}")
                
                # Convert otp_expiry to datetime object if needed
                otp_expiry = None
                if otp_expiry_raw:
                    if isinstance(otp_expiry_raw, datetime):
                        # Already a datetime object
                        otp_expiry = otp_expiry_raw
                    elif isinstance(otp_expiry_raw, str):
                        # Convert string to datetime
                        try:
                            # Handle format: "2025-11-21 12:17:54.6400000" (with microseconds)
                            otp_expiry_str = otp_expiry_raw.strip()
                            
                            # Try ISO format first
                            if 'T' in otp_expiry_str:
                                # Remove timezone and microseconds for parsing
                                otp_expiry_str = otp_expiry_str.replace('Z', '').split('.')[0]
                                otp_expiry = datetime.fromisoformat(otp_expiry_str)
                            else:
                                # Handle SQL Server datetime format: "YYYY-MM-DD HH:MM:SS.microseconds"
                                # Remove microseconds if present
                                if '.' in otp_expiry_str:
                                    # Split by dot and take only the date-time part before microseconds
                                    base_part = otp_expiry_str.split('.')[0]
                                    try:
                                        otp_expiry = datetime.strptime(base_part, '%Y-%m-%d %H:%M:%S')
                                    except ValueError:
                                        # Try with dateutil parser as fallback
                                        from dateutil import parser
                                        otp_expiry = parser.parse(otp_expiry_str)
                                else:
                                    # No microseconds, parse directly
                                    try:
                                        otp_expiry = datetime.strptime(otp_expiry_str, '%Y-%m-%d %H:%M:%S')
                                    except ValueError:
                                        # Try dateutil parser
                                        from dateutil import parser
                                        otp_expiry = parser.parse(otp_expiry_str)
                        except (ValueError, AttributeError, TypeError) as parse_error:
                            print(f"Error parsing otp_expiry string '{otp_expiry_raw}': {parse_error}")
                            otp_expiry = None
                    else:
                        # Try to convert other types
                        try:
                            # If it has datetime attributes, use them
                            if hasattr(otp_expiry_raw, 'year'):
                                otp_expiry = datetime(
                                    otp_expiry_raw.year, otp_expiry_raw.month, otp_expiry_raw.day,
                                    otp_expiry_raw.hour, otp_expiry_raw.minute, otp_expiry_raw.second
                                )
                            else:
                                # Convert to string then parse
                                otp_expiry = datetime.fromisoformat(str(otp_expiry_raw))
                        except (ValueError, AttributeError, TypeError):
                            print(f"Could not convert otp_expiry to datetime: {type(otp_expiry_raw)}")
                            otp_expiry = None
                
                if not otp_expiry or not isinstance(otp_expiry, datetime):
                    print(f"OTP expiry is None or not a datetime object: {otp_expiry}, type: {type(otp_expiry)}")
                    return jsonify({'error': 'Invalid OTP expiry. Please request a new OTP.'}), 400
                
                # Now safely compare datetime objects
                try:
                    if otp_expiry < current_time:
                        print(f"OTP expired for candidate. Expiry={otp_expiry}, Now={current_time}")
                        return jsonify({'error': 'OTP expired. Please request a new OTP.'}), 400
                except TypeError as compare_error:
                    print(f"Error comparing datetimes: {compare_error}, otp_expiry type: {type(otp_expiry)}, current_time type: {type(current_time)}")
                    return jsonify({'error': 'Invalid OTP expiry format. Please request a new OTP.'}), 400

                print(f"OTP verified, marking candidate as verified...")
                # Mark as verified
                candidate.mark_verified()
                session.add(candidate)
                
                # Store candidate data before closing session
                candidate_data = {
                    'name': candidate.name,
                    'email': candidate.email,
                    'phone': candidate.phone,
                    'password_hash': candidate.password_hash,
                }
                print(f"Candidate data extracted: name={candidate_data['name']}, email={candidate_data['email']}")
        except Exception as session_error:
            print(f"Error in session operations: {type(session_error).__name__}: {session_error}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Database error during verification: {str(session_error)}'}), 500
        
        if not candidate_data:
            print(f"Error: candidate_data is None after session operations")
            return jsonify({'error': 'Failed to retrieve candidate data. Please try again.'}), 500

        # Create account in candidate_signup table
        print(f"Creating candidate signup for email={candidate_data['email']}, name={candidate_data['name']}")
        
        try:
            cid = _ensure_candidate_signup(
                candidate_data['name'],
                candidate_data['email'],
                candidate_data['phone'],
                candidate_data['password_hash'],
            )
        except Exception as signup_error:
            print(f"Exception in _ensure_candidate_signup: {signup_error}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'error': 'Failed to create account. Please contact support or try again.'
            }), 500
        
        if not cid:
            print(f"Failed to create candidate signup for email={candidate_data['email']} - _ensure_candidate_signup returned None")
            return jsonify({
                'error': 'Verification succeeded but account creation failed. Please contact support or try again.'
            }), 500

        print(f"Successfully created candidate with cid={cid}")

        if candidate_data.get('email'):
            send_notification_email(
                candidate_data['email'],
                "Welcome to Job Portal",
                (
                    f"Hi {candidate_data['name']},\n\n"
                    "Your applicant account has been verified successfully. You can now sign in and start applying for jobs.\n\n"
                    "If you did not sign up, please reset your password or contact support immediately."
                )
            )

        return jsonify({
            'message': 'OTP verified successfully. Account created.',
            'cid': cid
        }), 200
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print(f"Error in verify_candidate_otp: {error_type}: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Return a more user-friendly error message based on error type
        error_msg_upper = error_msg.upper()
        
        # Handle specific error types
        if 'UNIQUE' in error_msg_upper or 'CONSTRAINT' in error_msg_upper or 'DUPLICATE' in error_msg_upper:
            return jsonify({'error': 'This email is already registered. Please login instead.'}), 400
        elif 'OPERATIONALERROR' in error_type or 'CONNECTION' in error_msg_upper or 'TIMEOUT' in error_msg_upper:
            return jsonify({'error': 'Database connection error. Please try again later.'}), 500
        elif 'INTEGRITYERROR' in error_type or 'FOREIGN KEY' in error_msg_upper:
            return jsonify({'error': 'Database integrity error. Please contact support.'}), 500
        elif 'PROGRAMMINGERROR' in error_type or 'SYNTAX' in error_msg_upper:
            return jsonify({'error': 'Database query error. Please contact support.'}), 500
        else:
            # Return generic error for security (actual error logged in console)
            # In debug mode, you might want to return the actual error message
            debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
            if debug_mode:
                return jsonify({'error': f'An error occurred: {error_msg}'}), 500
            return jsonify({'error': 'An error occurred during verification. Please try again.'}), 500


@candidate_auth_bp.post('/resend-otp')
def resend_candidate_otp():
    """Resend OTP to candidate's email or phone"""
    try:
        data = request.get_json()
        email_input = data.get('email', '').strip().lower() if data.get('email') else None
        phone = data.get('phone', '').strip() if data.get('phone') else None

        if not email_input and not phone:
            return jsonify({'error': 'Email or phone is required.'}), 400

        email_valid = is_valid_email(email_input) if email_input else False
        phone_valid = is_valid_indian_phone(phone) if phone else False
        if not (email_valid or phone_valid):
            return jsonify({'error': 'Provide a valid email address or 10-digit Indian phone number.'}), 400

        email = email_input or None

        with get_session() as session:
            existing_email = session.query(CandidateAuth).filter(CandidateAuth.email == email).first() if email else None
            existing_phone = session.query(CandidateAuth).filter(CandidateAuth.phone == phone).first() if phone else None

            candidate = existing_email or existing_phone
            if not candidate:
                return jsonify({'error': 'No signup found. Please signup first.'}), 404

            if candidate.is_verified:
                return jsonify({'error': 'Account already verified. Please login.'}), 400

            # Generate new OTP
            otp = generate_otp()
            expiry = datetime.utcnow() + timedelta(minutes=5)

            candidate.otp = otp
            candidate.otp_expiry = expiry
            session.add(candidate)

        # Send OTP via email
        target_email = email or _resolve_signup_email(None, phone)
        if target_email:
            otp_sent = send_email_otp(target_email, otp, user_type="Candidate")
            if not otp_sent:
                return jsonify({'error': 'Unable to send OTP. Please try again later.'}), 500

        return jsonify({'message': 'OTP resent successfully. Please check your email.'}), 200

    except Exception as e:
        print(f"Error in resend_candidate_otp: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@candidate_auth_bp.post('/login')
def candidate_login():
    data = request.get_json(force=True) or {}
    email_input = (data.get('email') or '').strip().lower()
    phone = normalize_phone(data.get('phone'))
    password = data.get('password') or ''
    identifier = email_input or phone
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')

    if not identifier or not password:
        return jsonify({'error': 'Email/phone and password are required.'}), 400

    failed_attempts = get_recent_failed_attempts(identifier, 'candidate', 15)
    if failed_attempts >= 5:
        record_login_attempt(identifier, 'candidate', 'failed', ip_address, user_agent,
                             'Too many failed attempts')
        return jsonify({'error': 'Too many failed login attempts. Please try again later.'}), 429

    with get_session() as session:
        candidate = _find_candidate(session, email=email_input or None, phone=phone or None)
        if not candidate and email_input:
            candidate = _bootstrap_legacy_candidate(session, email_input)
        if not candidate:
            record_login_attempt(identifier, 'candidate', 'failed', ip_address, user_agent,
                                 'User not found')
            return jsonify({'error': 'Invalid credentials'}), 401

        if not candidate.is_verified:
            record_login_attempt(identifier, 'candidate', 'failed', ip_address, user_agent,
                                 'OTP not verified')
            return jsonify({'error': 'Please verify your OTP to login.'}), 403

        stored_hash = candidate.password_hash or ''
        if not stored_hash or not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            record_login_attempt(identifier, 'candidate', 'failed', ip_address, user_agent,
                                 'Invalid password')
            return jsonify({'error': 'Invalid credentials'}), 401

        cid = _ensure_candidate_signup(candidate.name, candidate.email, candidate.phone, stored_hash)
        if not cid:
            return jsonify({'error': 'Candidate profile mapping failed.'}), 500

        token = jwt.encode(
            {'id': cid, 'email': candidate.email, 'role': 'candidate'},
            JWT_SECRET,
            algorithm='HS256',
        )

    login_email = candidate.email or _resolve_signup_email(candidate.email, candidate.phone)
    db_run(
        'INSERT INTO candidate_login (cid, email, password) VALUES (?, ?, ?)',
        (cid, login_email, stored_hash),
    )
    record_login_attempt(identifier, 'candidate', 'success', ip_address, user_agent)

    if candidate.email:
        send_notification_email(
            candidate.email,
            "New login to your Job Portal account",
            (
                f"Hi {candidate.name},\n\n"
                f"We noticed a login to your Job Portal account on {datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC.\n"
                f"IP Address: {ip_address or 'Unavailable'}\n"
                f"Device: {user_agent or 'Unavailable'}\n\n"
                "If this was you, no action is needed. If you did not sign in, please reset your password immediately."
            )
        )

    profile = db_get('SELECT * FROM candidate_profiles WHERE candidate_id = ?', (cid,))
    user_data = {
        'id': cid,
        'email': candidate.email or '',
        'phone': candidate.phone or '',
        'name': candidate.name,
        'role': 'candidate',
    }
    if profile:
        user_data['profile'] = parse_profile(profile)

    return jsonify({'token': token, 'user': user_data}), 200


@candidate_auth_bp.post('/forgot-password')
def candidate_forgot_password():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()

        if not email:
            return jsonify({'error': 'Email is required.'}), 400
        if not is_valid_email(email):
            return jsonify({'error': 'Please provide a valid email address.'}), 400

        with get_session() as session:
            candidate = _find_candidate(session, email=email)
            if not candidate:
                candidate = _bootstrap_legacy_candidate(session, email)
            if not candidate:
                return jsonify({'error': 'Account not found for this email.'}), 404
            if not candidate.is_verified:
                return jsonify({'error': 'Please verify your account before resetting the password.'}), 400

            otp = generate_otp()
            candidate.otp = otp
            candidate.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
            session.add(candidate)

        if not send_email_otp(email, otp, user_type="Candidate"):
            return jsonify({'error': 'Failed to send OTP email. Please try again later.'}), 500

        return jsonify({'message': 'OTP sent successfully. Please check your email.'}), 200
    except Exception as e:
        print(f"Error in candidate_forgot_password: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@candidate_auth_bp.post('/forgot-password/verify-otp')
def candidate_verify_reset_otp():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        otp = (data.get('otp') or '').strip()

        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400
        if not is_valid_email(email):
            return jsonify({'error': 'Please provide a valid email address.'}), 400

        with get_session() as session:
            candidate = _find_candidate(session, email=email)
            if not candidate:
                candidate = _bootstrap_legacy_candidate(session, email)
            if not candidate or not candidate.otp:
                return jsonify({'error': 'Please request a new OTP.'}), 400

            stored_otp = str(candidate.otp).strip()
            if stored_otp != otp:
                return jsonify({'error': 'Invalid OTP.'}), 400

            expiry = parse_otp_expiry(candidate.otp_expiry)
            if not expiry or expiry < datetime.utcnow():
                return jsonify({'error': 'OTP expired. Please request a new one.'}), 400

        return jsonify({'message': 'OTP verified. You may set a new password.'}), 200
    except Exception as e:
        print(f"Error in candidate_verify_reset_otp: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@candidate_auth_bp.post('/reset-password')
def candidate_reset_password():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        otp = (data.get('otp') or '').strip()
        new_password = data.get('newPassword') or data.get('password') or ''
        confirm_password = data.get('confirmPassword') or data.get('confirm_password') or ''

        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400
        if len(new_password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters.'}), 400
        if new_password != confirm_password:
            return jsonify({'error': 'Passwords do not match.'}), 400

        candidate_snapshot = None
        with get_session() as session:
            candidate = _find_candidate(session, email=email)
            if not candidate:
                candidate = _bootstrap_legacy_candidate(session, email)
            if not candidate or not candidate.otp:
                return jsonify({'error': 'Please request a new OTP.'}), 400

            stored_otp = str(candidate.otp).strip()
            if stored_otp != otp:
                return jsonify({'error': 'Invalid OTP.'}), 400

            expiry = parse_otp_expiry(candidate.otp_expiry)
            if not expiry or expiry < datetime.utcnow():
                return jsonify({'error': 'OTP expired. Please request a new one.'}), 400

            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            candidate.password_hash = password_hash
            candidate.otp = None
            candidate.otp_expiry = None
            session.add(candidate)
            candidate_snapshot = {
                'name': candidate.name,
                'email': candidate.email,
                'phone': candidate.phone,
            }

        cid = _ensure_candidate_signup(
            candidate_snapshot['name'],
            candidate_snapshot['email'],
            candidate_snapshot['phone'],
            password_hash,
        )
        if not cid:
            try:
                db_run('UPDATE candidate_signup SET password = ? WHERE email = ?', (password_hash, email))
            except Exception:
                pass

        if candidate_snapshot and candidate_snapshot.get('email'):
            send_notification_email(
                candidate_snapshot['email'],
                "Your Job Portal password was changed",
                (
                    f"Hi {candidate_snapshot['name']},\n\n"
                    "This is a confirmation that the password on your Job Portal account was just changed.\n"
                    "If this wasn't you, please reset your password immediately or contact support."
                )
            )

        return jsonify({'message': 'Password updated successfully. You can now login.'}), 200
    except Exception as e:
        print(f"Error in candidate_reset_password: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

