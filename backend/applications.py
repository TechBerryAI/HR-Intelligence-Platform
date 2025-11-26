from flask import Blueprint, request, jsonify
from db import db_get, db_run, db_all
from utils import authenticate_token, require_candidate
from matching import calculate_matching_percentage

applications_bp = Blueprint('applications', __name__)


@applications_bp.post('/')
@authenticate_token
@require_candidate
def apply_job():
    try:
        data = request.get_json(force=True)
        job_id = data.get('jobId')
        candidate_id = request.user['id']
        if not job_id:
            return jsonify({'error': 'Job ID is required'}), 400
        job = db_get('SELECT * FROM jobs WHERE jdid = ? AND enabled = 1', (job_id,))
        if not job:
            return jsonify({'error': 'Job not found or not available'}), 404
        existing = db_get('SELECT id FROM applications WHERE candidate_id = ? AND job_id = ?', (candidate_id, job_id))
        if existing:
            return jsonify({'error': 'Already applied to this job'}), 400
        profile = db_get('SELECT * FROM candidate_profiles WHERE candidate_id = ? AND completed = 1', (candidate_id,))
        if not profile:
            return jsonify({'error': 'Please complete your profile before applying'}), 400
        
        # Calculate matching percentage
        matching_percentage = calculate_matching_percentage(candidate_id, job_id)
        
        # Insert application with matching percentage
        db_run(
            'INSERT INTO applications (candidate_id, job_id, status, matching_percentage) VALUES (?, ?, ?, ?)',
            (candidate_id, job_id, 'pending', matching_percentage)
        )
        return jsonify({'message': 'Application submitted successfully'}), 201
    except Exception as e:
        print(f"Error in apply_job: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@applications_bp.get('/')
@authenticate_token
@require_candidate
def get_my_applications():
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
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


