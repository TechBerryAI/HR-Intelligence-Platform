import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import Blueprint, request, jsonify

from db import db_get, db_run, BACKEND
from helpers.email_utils import send_notification_email
from helpers.otp_utils import generate_otp, is_valid_email, parse_otp_expiry, send_email_otp, utc_now_aware, normalize_to_utc_aware
from models import get_session
from models.hr_auth import HRAuth
from sessions_service import record_login_attempt
from utils import build_jwt_payload, authenticate_token

auth_bp = Blueprint('auth', __name__)
HRAUTH_T = '"HRAuth"' if BACKEND == 'postgresql' else 'HRAuth'

JWT_SECRET = os.getenv('JWT_SECRET', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE')


@auth_bp.post('/signup')
def hr_signup():
    try:
        data = request.get_json(force=True)
        full_name = (data.get('fullName') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        company = (data.get('company') or '').strip()

        if not full_name or not email or not password or not company:
            return jsonify({"error": "All fields are required"}), 400
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400

        # Validate email format (must contain @ and be valid email)
        if not is_valid_email(email):
            return jsonify({"error": "Please provide a valid email address"}), 400

        # Check if email already exists in hr_signup (verified account)
        existing_signup = db_get('SELECT hrid FROM hr_signup WHERE email = ?', (email,))
        if existing_signup:
            return jsonify({"error": "Email already registered"}), 400

        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        otp = generate_otp()
        # Use timezone-aware UTC so PostgreSQL TIMESTAMPTZ stores/compares correctly
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        print(f"[HR SIGNUP] Generated OTP for {email}: {otp}")

        # Store in HRAuth temporarily until OTP verification
        try:
            with get_session() as session:
                existing_hr_auth = session.query(HRAuth).filter(HRAuth.email == email).first()
                
                if existing_hr_auth and existing_hr_auth.is_verified:
                    return jsonify({"error": "Email already registered"}), 400
                
                if not existing_hr_auth:
                    hr_auth = HRAuth(
                        full_name=full_name,
                        email=email,
                        company=company,
                        password_hash=password_hash,
                        otp=otp,
                        otp_expiry=expiry,
                        is_verified=False,
                    )
                    session.add(hr_auth)
                    print(f"[HR SIGNUP] Created new HRAuth record with OTP: {otp}")
                else:
                    # Update existing unverified record
                    existing_hr_auth.full_name = full_name
                    existing_hr_auth.company = company
                    existing_hr_auth.password_hash = password_hash
                    existing_hr_auth.otp = otp
                    existing_hr_auth.otp_expiry = expiry
                    existing_hr_auth.is_verified = False
                    print(f"[HR SIGNUP] Updated existing HRAuth record with OTP: {otp}")
                
                # Explicitly flush to ensure data is saved before sending email
                session.flush()
                print(f"[HR SIGNUP] Flushed session - OTP should be saved: {otp}")
        except Exception as db_error:
            print(f"Database error in hr_signup: {type(db_error).__name__}: {db_error}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"Database error: {str(db_error)}"}), 500

        # Verify what was actually stored in the database
        try:
            stored_hr = db_get('SELECT otp FROM ' + HRAUTH_T + ' WHERE email = ?', (email,))
            if stored_hr:
                print(f"[HR SIGNUP] OTP in database after save: {stored_hr.get('otp')}")
            else:
                print(f"[HR SIGNUP] WARNING: Could not find HRAuth record for {email}")
        except Exception as verify_error:
            print(f"[HR SIGNUP] Error verifying stored OTP: {verify_error}")

        # Send OTP via email
        try:
            print(f"[HR SIGNUP] About to send OTP via email: {otp}")
            otp_sent = send_email_otp(email, otp, user_type="HR")
            if not otp_sent:
                return jsonify({'error': 'Unable to send OTP. Please try again later.'}), 500
            print(f"[HR SIGNUP] OTP sent successfully to {email}")
        except Exception as email_error:
            print(f"Email error in hr_signup: {type(email_error).__name__}: {email_error}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': 'Failed to send OTP email. Please try again later.'}), 500

        return jsonify({'message': 'OTP sent successfully. Please check your email.'}), 200
    except Exception as e:
        print(f"Error in hr_signup: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@auth_bp.post('/verify-otp')
def verify_hr_otp():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        otp = (data.get('otp') or '').strip()

        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400

        with get_session() as session:
            hr_auth = session.query(HRAuth).filter(HRAuth.email == email).first()
            if not hr_auth:
                return jsonify({'error': 'HR not found. Please signup again.'}), 404
            
            # Convert both OTPs to strings for comparison (handles int/string mismatch)
            stored_otp = str(hr_auth.otp).strip() if hr_auth.otp else None
            input_otp = str(otp).strip()
            
            if not stored_otp or stored_otp != input_otp:
                print(f"Invalid OTP for HR. Expected={stored_otp}, Got={input_otp}")
                return jsonify({'error': 'Invalid OTP.'}), 400
            
            # Check OTP expiry (PG returns timezone-aware; use aware UTC for comparison)
            current_time = utc_now_aware()
            otp_expiry_raw = hr_auth.otp_expiry
            
            # Convert otp_expiry to datetime object if needed
            otp_expiry = None
            if otp_expiry_raw:
                if isinstance(otp_expiry_raw, datetime):
                    otp_expiry = otp_expiry_raw
                elif isinstance(otp_expiry_raw, str):
                    try:
                        # Handle format: "2025-11-21 12:17:54.6400000" (with microseconds)
                        otp_expiry_str = otp_expiry_raw.strip()
                        
                        # Try ISO format first
                        if 'T' in otp_expiry_str:
                            otp_expiry_str = otp_expiry_str.replace('Z', '').split('.')[0]
                            otp_expiry = datetime.fromisoformat(otp_expiry_str)
                        else:
                            # Handle SQL Server datetime format: "YYYY-MM-DD HH:MM:SS.microseconds"
                            if '.' in otp_expiry_str:
                                base_part = otp_expiry_str.split('.')[0]
                                try:
                                    otp_expiry = datetime.strptime(base_part, '%Y-%m-%d %H:%M:%S')
                                except ValueError:
                                    try:
                                        from dateutil import parser
                                        otp_expiry = parser.parse(otp_expiry_str)
                                    except Exception:
                                        otp_expiry = None
                            else:
                                try:
                                    otp_expiry = datetime.strptime(otp_expiry_str, '%Y-%m-%d %H:%M:%S')
                                except ValueError:
                                    try:
                                        from dateutil import parser
                                        otp_expiry = parser.parse(otp_expiry_str)
                                    except Exception:
                                        otp_expiry = None
                    except (ValueError, AttributeError, TypeError) as parse_error:
                        print(f"Error parsing HR otp_expiry string '{otp_expiry_raw}': {parse_error}")
                        otp_expiry = None
                else:
                    try:
                        if hasattr(otp_expiry_raw, 'year'):
                            otp_expiry = datetime(
                                otp_expiry_raw.year, otp_expiry_raw.month, otp_expiry_raw.day,
                                otp_expiry_raw.hour, otp_expiry_raw.minute, otp_expiry_raw.second
                            )
                        else:
                            otp_expiry = datetime.fromisoformat(str(otp_expiry_raw))
                    except (ValueError, AttributeError, TypeError):
                        otp_expiry = None
            
            if not otp_expiry or not isinstance(otp_expiry, datetime):
                print(f"Invalid OTP expiry for HR. Raw value: {otp_expiry_raw}, Type: {type(otp_expiry_raw)}")
                return jsonify({'error': 'Invalid OTP expiry. Please request a new OTP.'}), 400
            otp_expiry_utc = normalize_to_utc_aware(otp_expiry)
            # 30s grace after nominal expiry to avoid clock skew
            grace = timedelta(seconds=30)
            if otp_expiry_utc and current_time > (otp_expiry_utc + grace):
                print(f"[VERIFY OTP] Expired: now_utc={current_time}, expiry_utc={otp_expiry_utc}")
                return jsonify({'error': 'OTP expired. Please request a new OTP.'}), 400

            # Mark as verified
            hr_auth.mark_verified()
            session.add(hr_auth)
            
            # Store HR data before session closes
            hr_data = {
                'full_name': hr_auth.full_name,
                'email': hr_auth.email,
                'company': hr_auth.company,
                'password_hash': hr_auth.password_hash,
            }
            
            # Explicitly flush to ensure verification is saved
            session.flush()

        # Check if account already exists in hr_signup
        existing = db_get('SELECT hrid FROM hr_signup WHERE email = ?', (hr_data['email'],))
        if existing:
            return jsonify({"error": "Account already verified and registered"}), 400

        # Generate next HRID like HRID001 based on max existing
        try:
            row = db_get("SELECT MAX(CAST(SUBSTRING(hrid,5,10) AS INT)) AS maxn FROM hr_signup", ())
            next_num = int(row['maxn']) + 1 if row and row.get('maxn') is not None else 1
        except (ValueError, TypeError, KeyError) as e:
            print(f"Error generating HRID: {e}")
            # Fallback: count existing records
            count_row = db_get("SELECT COUNT(*) AS cnt FROM hr_signup", ())
            next_num = (count_row['cnt'] if count_row else 0) + 1
        hrid = f"HRID{next_num:03d}"

        # Insert verified signup into hr_signup table
        try:
            db_run(
                'INSERT INTO hr_signup (hrid, full_name, email, company, password) VALUES (?, ?, ?, ?, ?)',
                (hrid, hr_data['full_name'], hr_data['email'], hr_data['company'], hr_data['password_hash'])
            )
        except Exception as db_error:
            print(f"Error inserting into hr_signup: {db_error}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": "Failed to create account. Please try again."}), 500

        identity = {"hrId": hrid, "email": hr_data['email'], "role": "HR"}
        access_token = jwt.encode(build_jwt_payload(identity, refresh=False), JWT_SECRET, algorithm='HS256')
        refresh_token = jwt.encode(build_jwt_payload(identity, refresh=True), JWT_SECRET, algorithm='HS256')

        # Record the signup/login in login_history so subsequent logins from same IP/device are recognized
        # This prevents sending unnecessary emails for logins from the same device used during signup
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')
        record_login_attempt(hr_data['email'], 'HR', 'success', ip_address, user_agent)

        send_notification_email(
            hr_data['email'],
            "Welcome to Job Portal",
            (
                f"Hi {hr_data['full_name']},\n\n"
                "Your HR account has been verified and is ready to use. You can now log in to manage jobs and applicants.\n\n"
                "If you did not initiate this signup, please contact support immediately."
            )
        )

        return jsonify({
            "message": "Account verified and created successfully",
            "token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "hrId": hrid,
                "email": hr_data['email'],
                "fullName": hr_data['full_name'],
                "company": hr_data['company'],
                "role": "HR"
            }
        }), 200
    except Exception as e:
        print(f"Error in verify_hr_otp: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.post('/resend-otp')
def resend_hr_otp():
    """Resend OTP to HR's email"""
    try:
        data = request.get_json(force=True)
        email = (data.get('email') or '').strip().lower()

        if not email:
            return jsonify({'error': 'Email is required.'}), 400

        if not is_valid_email(email):
            return jsonify({"error": "Please provide a valid email address"}), 400

        # Check if email already exists in hr_signup (verified account)
        existing_signup = db_get('SELECT hrid FROM hr_signup WHERE email = ?', (email,))
        if existing_signup:
            return jsonify({"error": "Email already registered. Please login."}), 400

        with get_session() as session:
            hr_auth = session.query(HRAuth).filter(HRAuth.email == email).first()
            
            if not hr_auth:
                return jsonify({'error': 'No signup found. Please signup first.'}), 404

            if hr_auth.is_verified:
                return jsonify({'error': 'Account already verified. Please login.'}), 400

            # Generate new OTP (timezone-aware UTC for TIMESTAMPTZ)
            otp = generate_otp()
            expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

            hr_auth.otp = otp
            hr_auth.otp_expiry = expiry
            session.add(hr_auth)

        # Send OTP via email
        otp_sent = send_email_otp(email, otp, user_type="HR")
        if not otp_sent:
            return jsonify({'error': 'Unable to send OTP. Please try again later.'}), 500

        return jsonify({'message': 'OTP resent successfully. Please check your email.'}), 200

    except Exception as e:
        print(f"Error in resend_hr_otp: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.post('/forgot-password')
def hr_forgot_password():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()

        if not email:
            return jsonify({'error': 'Email is required.'}), 400
        if not is_valid_email(email):
            return jsonify({'error': 'Please provide a valid email address.'}), 400

        hr_signup = db_get('SELECT full_name, email, company, password FROM hr_signup WHERE email = ?', (email,))
        if not hr_signup:
            return jsonify({'error': 'Account not found for this email.'}), 404

        otp = generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)

        with get_session() as session:
            hr_auth = session.query(HRAuth).filter(HRAuth.email == email).first()
            if not hr_auth:
                hr_auth = HRAuth(
                    full_name=hr_signup['full_name'],
                    email=email,
                    company=hr_signup['company'],
                    password_hash=hr_signup['password'],
                    is_verified=True,
                )
                session.add(hr_auth)
                session.flush()
            hr_auth.otp = otp
            hr_auth.otp_expiry = expiry
            session.add(hr_auth)

        if not send_email_otp(email, otp, user_type="HR"):
            return jsonify({'error': 'Failed to send OTP email. Please try again later.'}), 500

        return jsonify({'message': 'OTP sent successfully. Please check your email.'}), 200
    except Exception as e:
        print(f"Error in hr_forgot_password: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.post('/forgot-password/verify-otp')
def hr_verify_reset_otp():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        otp = (data.get('otp') or '').strip()

        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400
        if not is_valid_email(email):
            return jsonify({'error': 'Please provide a valid email address.'}), 400

        with get_session() as session:
            hr_auth = session.query(HRAuth).filter(HRAuth.email == email).first()
            if not hr_auth or not hr_auth.otp:
                return jsonify({'error': 'Please request a new OTP.'}), 400

            stored_otp = str(hr_auth.otp).strip()
            if stored_otp != otp:
                return jsonify({'error': 'Invalid OTP.'}), 400

            expiry = parse_otp_expiry(hr_auth.otp_expiry)
            if not expiry:
                return jsonify({'error': 'OTP expired. Please request a new one.'}), 400
            expiry_utc = normalize_to_utc_aware(expiry)
            now = utc_now_aware()
            if expiry_utc and now > (expiry_utc + timedelta(seconds=30)):
                return jsonify({'error': 'OTP expired. Please request a new one.'}), 400

        return jsonify({'message': 'OTP verified. You may set a new password.'}), 200
    except Exception as e:
        print(f"Error in hr_verify_reset_otp: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.post('/reset-password')
def hr_reset_password():
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

        signup_row = db_get('SELECT hrid, full_name FROM hr_signup WHERE email = ?', (email,))
        if not signup_row:
            return jsonify({'error': 'Account not found for this email.'}), 404
        hr_name = signup_row.get('full_name') if signup_row else None

        with get_session() as session:
            hr_auth = session.query(HRAuth).filter(HRAuth.email == email).first()
            if not hr_auth or not hr_auth.otp:
                return jsonify({'error': 'Please request a new OTP.'}), 400

            stored_otp = str(hr_auth.otp).strip()
            if stored_otp != otp:
                return jsonify({'error': 'Invalid OTP.'}), 400

            expiry = parse_otp_expiry(hr_auth.otp_expiry)
            if not expiry:
                return jsonify({'error': 'OTP expired. Please request a new one.'}), 400
            expiry_utc = normalize_to_utc_aware(expiry)
            if expiry_utc and utc_now_aware() > expiry_utc:
                return jsonify({'error': 'OTP expired. Please request a new one.'}), 400

            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            hr_auth.password_hash = password_hash
            hr_auth.otp = None
            hr_auth.otp_expiry = None
            session.add(hr_auth)

        try:
            db_run('UPDATE hr_signup SET password = ? WHERE email = ?', (password_hash, email))
        except Exception as db_error:
            print(f"Error updating hr_signup password: {db_error}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': 'Failed to update password. Please try again.'}), 500

        send_notification_email(
            email,
            "Your Job Portal password was changed",
            (
                f"Hi {hr_name or 'there'},\n\n"
                "This is a confirmation that the password for your Job Portal HR account was just changed.\n"
                "If this wasn't you, please reset your password immediately or contact support."
            )
        )

        return jsonify({'message': 'Password updated successfully. You can now login.'}), 200
    except Exception as e:
        print(f"Error in hr_reset_password: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.post('/login')
def hr_login():
    try:
        data = request.get_json(force=True)
        email = data.get('email')
        password = data.get('password')
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        email_clean = email.strip().lower()
        signup_data = db_get(
            'SELECT hrid, email, password, full_name, company, is_head_hr FROM hr_signup WHERE LOWER(TRIM(email)) = ?',
            (email_clean,)
        )
        if not signup_data:
            record_login_attempt(email, 'HR', 'failed', ip_address, user_agent, 'User not found')
            return jsonify({"error": "Invalid email or password"}), 401

        stored = signup_data.get('password') or ''
        if not stored:
            record_login_attempt(email, 'HR', 'failed', ip_address, user_agent, 'Invalid password')
            return jsonify({"error": "Invalid email or password"}), 401
        stored_b = stored.encode('utf-8') if isinstance(stored, str) else stored
        if not bcrypt.checkpw(password.encode('utf-8'), stored_b):
            record_login_attempt(email, 'HR', 'failed', ip_address, user_agent, 'Invalid password')
            return jsonify({"error": "Invalid email or password"}), 401

        user_id = signup_data['hrid']
        role = 'head_hr' if signup_data.get('is_head_hr') else 'HR'
        identity = {"hrId": user_id, "email": signup_data['email'], "role": role}
        access_token = jwt.encode(build_jwt_payload(identity, refresh=False), JWT_SECRET, algorithm='HS256')
        refresh_token = jwt.encode(build_jwt_payload(identity, refresh=True), JWT_SECRET, algorithm='HS256')

        # Check if this is a new IP/device combination BEFORE recording the login
        # This way we don't count the current login in our check
        from sessions_service import has_previous_login_from_same_device
        is_new_device = not has_previous_login_from_same_device(email, 'HR', ip_address, user_agent)
        
        db_run('INSERT INTO hr_login (hrid, email, password) VALUES (?, ?, ?)', (user_id, signup_data['email'], signup_data['password']))
        record_login_attempt(email, 'HR', 'success', ip_address, user_agent)

        # Only send login notification email if this is a new IP/device combination
        # Skip email if user has logged in from this IP/device before (including signup)
        if is_new_device:
            # This is a new device/IP - send notification
            send_notification_email(
                signup_data['email'],
                "New login to your Job Portal HR account",
                (
                    f"Hi {signup_data['full_name'] or 'there'},\n\n"
                    f"We noticed a login to your Job Portal HR account on {datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC.\n"
                    f"IP Address: {ip_address or 'Unavailable'}\n"
                    f"Device: {user_agent or 'Unavailable'}\n\n"
                    "If this was you, no action is needed. If you did not sign in, please reset your password immediately."
                )
            )

        return jsonify({
            "token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "hrId": user_id,
                "email": signup_data['email'],
                "fullName": signup_data['full_name'],
                "company": signup_data['company'],
                "role": role
            }
        })
    except Exception:
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.post('/change-password')
@authenticate_token
def hr_change_password():
    """Change password for logged-in HR or Super Admin. Requires current password and new password."""
    try:
        user = getattr(request, 'user', None)
        if not user or not user.get('hrId'):
            return jsonify({'error': 'Access denied'}), 403
        data = request.get_json(force=True) or {}
        current_password = (data.get('currentPassword') or data.get('current_password') or '').strip()
        new_password = (data.get('newPassword') or data.get('new_password') or '').strip()
        if not current_password:
            return jsonify({'error': 'Current password is required'}), 400
        if len(new_password) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400
        hrid = user['hrId']
        signup_data = db_get(
            'SELECT hrid, email, password, full_name FROM hr_signup WHERE hrid = ?',
            (hrid,)
        )
        if not signup_data:
            return jsonify({'error': 'Account not found'}), 404
        stored = signup_data.get('password') or ''
        if not stored:
            return jsonify({'error': 'Invalid current password'}), 401
        stored_b = stored.encode('utf-8') if isinstance(stored, str) else stored
        if not bcrypt.checkpw(current_password.encode('utf-8'), stored_b):
            return jsonify({'error': 'Current password is incorrect'}), 401
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        email = signup_data['email']
        try:
            db_run('UPDATE hr_signup SET password = ? WHERE hrid = ?', (password_hash, hrid))
        except Exception as db_err:
            print(f"Error updating hr_signup password: {db_err}")
            return jsonify({'error': 'Failed to update password'}), 500
        with get_session() as session:
            hr_auth = session.query(HRAuth).filter(HRAuth.email == email).first()
            if hr_auth:
                hr_auth.password_hash = password_hash
                session.add(hr_auth)
        hr_name = signup_data.get('full_name') or 'there'
        try:
            send_notification_email(
                email,
                "Your Job Portal password was changed",
                (
                    f"Hi {hr_name},\n\n"
                    "This is a confirmation that the password for your Job Portal account was changed.\n"
                    "If this wasn't you, please reset your password immediately or contact support."
                ),
            )
        except Exception:
            pass
        return jsonify({'message': 'Password updated successfully'}), 200
    except Exception as e:
        print(f"Error in hr_change_password: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@auth_bp.post('/refresh')
def refresh_tokens():
    """Exchange a valid refresh token for new access and refresh tokens. No auth header required."""
    try:
        data = request.get_json(silent=True) or {}
        refresh_token = (data.get('refresh_token') or '').strip()
        if not refresh_token:
            return jsonify({"error": "refresh_token required"}), 400
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=["HS256"])
        if payload.get('type') != 'refresh':
            return jsonify({"error": "Invalid refresh token"}), 403
        identity = {k: payload[k] for k in ('hrId', 'id', 'email', 'role') if k in payload}
        if not identity:
            return jsonify({"error": "Invalid refresh token"}), 403
        new_access = jwt.encode(build_jwt_payload(identity, refresh=False), JWT_SECRET, algorithm='HS256')
        new_refresh = jwt.encode(build_jwt_payload(identity, refresh=True), JWT_SECRET, algorithm='HS256')
        return jsonify({"token": new_access, "refresh_token": new_refresh})
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Refresh token expired"}), 403
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid refresh token"}), 403
    except Exception as e:
        print(f"[REFRESH] Error: {e}")
        return jsonify({"error": "Invalid refresh token"}), 403


@auth_bp.post('/logout')
def hr_logout():
    from sessions_service import deactivate_session
    try:
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.split(' ')[1] if auth_header.startswith('Bearer ') else None
        if token:
            deactivate_session(token)
        return jsonify({"message": "Logged out successfully"})
    except Exception:
        return jsonify({"error": "Internal server error"}), 500
