"""Platform operator endpoints — provision companies (env-keyed)."""
from __future__ import annotations

import os
import secrets

import bcrypt
from flask import Blueprint, jsonify, request

from app.database.connection.db import db_get, db_run
from app.domains.identity.services.organizations import (
    ensure_organization,
    force_organization_id,
    get_organization,
)

platform_bp = Blueprint('platform', __name__)

PLATFORM_PROVISION_KEY = (os.getenv('PLATFORM_PROVISION_KEY') or '').strip()


def _require_platform_key():
    expected = PLATFORM_PROVISION_KEY
    if not expected:
        return jsonify({
            'error': 'Platform provisioning is not configured (PLATFORM_PROVISION_KEY)',
        }), 503
    provided = (request.headers.get('X-Platform-Key') or '').strip()
    if not provided or not secrets.compare_digest(provided, expected):
        return jsonify({'error': 'Invalid or missing X-Platform-Key'}), 401
    return None


def _next_hrid() -> str:
    row = db_get(
        "SELECT COALESCE(MAX(CAST(SUBSTRING(hrid FROM 5) AS INT)), 0) AS maxn "
        "FROM hr_signup WHERE hrid ~ ?",
        ('^HRID[0-9]+$',),
    )
    next_num = int(row['maxn']) + 1 if row and row.get('maxn') is not None else 1
    return f'HRID{next_num:03d}'


def _create_staff(*, email: str, full_name: str, password: str, role: str, company: str, org_id: str):
    email_clean = email.strip().lower()
    existing = db_get('SELECT hrid FROM hr_signup WHERE LOWER(TRIM(email)) = ?', (email_clean,))
    if existing:
        raise ValueError(f'Email already registered: {email_clean}')
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    hrid = _next_hrid()
    db_run(
        """
        INSERT INTO hr_signup (
            hrid, full_name, email, company, password, role,
            account_status, organization_id
        ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
        """,
        (hrid, full_name.strip(), email_clean, company, password_hash, role, org_id),
    )
    force_organization_id('hr_signup', 'hrid', hrid, org_id)
    return {
        'hrid': hrid,
        'email': email_clean,
        'fullName': full_name.strip(),
        'role': role,
        'company': company,
        'organizationId': org_id,
    }


@platform_bp.post('/companies')
def provision_company():
    """
    Create a company (organization) and initial HEAD_HR (optional CEO).

    Header: X-Platform-Key: <PLATFORM_PROVISION_KEY>
    Body: {
      "name": "Acme Corp",
      "headHr": { "email", "fullName", "password" },
      "ceo": { "email", "fullName", "password" }  // optional
    }
    """
    auth_err = _require_platform_key()
    if auth_err:
        return auth_err

    data = request.get_json(force=True) or {}
    name = (data.get('name') or data.get('company') or '').strip()
    head = data.get('headHr') or data.get('head_hr') or {}
    ceo = data.get('ceo') or None

    if not name:
        return jsonify({'error': 'name is required'}), 400
    if not isinstance(head, dict):
        return jsonify({'error': 'headHr object is required'}), 400

    head_email = (head.get('email') or '').strip().lower()
    head_name = (head.get('fullName') or head.get('full_name') or '').strip()
    head_password = (head.get('password') or '').strip()
    if not head_email or not head_name or not head_password:
        return jsonify({'error': 'headHr.email, headHr.fullName, and headHr.password are required'}), 400
    if len(head_password) < 6:
        return jsonify({'error': 'headHr.password must be at least 6 characters'}), 400

    if ceo is not None:
        if not isinstance(ceo, dict):
            return jsonify({'error': 'ceo must be an object when provided'}), 400
        ceo_email = (ceo.get('email') or '').strip().lower()
        ceo_name = (ceo.get('fullName') or ceo.get('full_name') or '').strip()
        ceo_password = (ceo.get('password') or '').strip()
        if not ceo_email or not ceo_name or not ceo_password:
            return jsonify({'error': 'ceo.email, ceo.fullName, and ceo.password are required'}), 400
        if len(ceo_password) < 6:
            return jsonify({'error': 'ceo.password must be at least 6 characters'}), 400

    try:
        org_id = ensure_organization(name)
        if not org_id:
            return jsonify({'error': 'Failed to create company'}), 500
        org = get_organization(org_id)
        company_name = (org or {}).get('name') or name

        head_account = _create_staff(
            email=head_email,
            full_name=head_name,
            password=head_password,
            role='HEAD_HR',
            company=company_name,
            org_id=org_id,
        )
        ceo_account = None
        if ceo is not None:
            ceo_account = _create_staff(
                email=(ceo.get('email') or '').strip().lower(),
                full_name=(ceo.get('fullName') or ceo.get('full_name') or '').strip(),
                password=(ceo.get('password') or '').strip(),
                role='CEO',
                company=company_name,
                org_id=org_id,
            )

        return jsonify({
            'message': 'Company provisioned',
            'company': {
                'id': org_id,
                'name': company_name,
                'slug': (org or {}).get('slug'),
            },
            'headHr': head_account,
            'ceo': ceo_account,
        }), 201
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        print(f'[PLATFORM] provision error: {e}')
        return jsonify({'error': 'Failed to provision company'}), 500
