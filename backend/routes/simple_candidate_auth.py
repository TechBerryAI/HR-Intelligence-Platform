"""
Simple candidate auth routes using only pyodbc (no SQLAlchemy conflicts)
This bypasses the SQLAlchemy session timeout issue
"""
import os
import bcrypt
import jwt
from flask import Blueprint, jsonify, request
from db import db_get, db_run

simple_candidate_auth_bp = Blueprint('simple_candidate_auth', __name__)

JWT_SECRET = os.getenv(
    'JWT_SECRET',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE',
)


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

