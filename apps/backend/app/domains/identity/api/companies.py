"""Public companies (organizations) listing for job board picker."""
from flask import Blueprint, jsonify

from app.domains.identity.services.organizations import list_companies_with_enabled_jobs

companies_bp = Blueprint('companies', __name__)


@companies_bp.get('/')
def list_companies():
    """Orgs that currently have at least one enabled public job."""
    try:
        return jsonify({'companies': list_companies_with_enabled_jobs()})
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500
