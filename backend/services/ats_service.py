"""
ATS Matching Service - calls HR-ATS-API internally.
Do not duplicate matching logic; this module is the single integration point.
"""
import os
import json
import requests

ATS_API_URL = os.getenv('ATS_API_URL', 'http://localhost:8000').rstrip('/')
ATS_API_KEY = os.getenv('ATS_API_KEY', '')
ATS_THRESHOLD = int(os.getenv('ATS_THRESHOLD', '60'))


def match_candidate_to_job(candidate_id: str, job_id: str, parsed_resume: dict, parsed_jd: dict, apply_id: str = None):
    """
    Call HR-ATS-API /api/match with parsed resume and JD (TOON format).
    Returns (success, result_or_error).
    result: dict with final_score, decision ('shortlist'|'reject'), json_output, deterministic_scores, etc.
    """
    if not ATS_API_URL:
        return False, {'error': 'ATS_API_URL not configured'}
    if not ATS_API_KEY:
        return False, {'error': 'ATS_API_KEY not configured'}

    # ATS API expects parsed_resume and parsed_jd as strings (TOON text or JSON string)
    parsed_resume_str = json.dumps(parsed_resume) if isinstance(parsed_resume, dict) else str(parsed_resume)
    parsed_jd_str = json.dumps(parsed_jd) if isinstance(parsed_jd, dict) else str(parsed_jd)

    payload = {
        'candidate_id': candidate_id,
        'job_id': job_id,
        'parsed_resume': parsed_resume_str,
        'parsed_jd': parsed_jd_str,
        'threshold': ATS_THRESHOLD,
    }
    if apply_id:
        payload['apply_id'] = apply_id

    headers = {
        'Content-Type': 'application/json',
        'x-api-key': ATS_API_KEY,
    }

    try:
        resp = requests.post(
            f'{ATS_API_URL}/api/match',
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        # HR-ATS-API match_router returns MatchResponse (correlation_id, toon_output, json_output, deterministic_scores, ...)
        return True, data
    except requests.exceptions.Timeout:
        return False, {'error': 'ATS request timed out'}
    except requests.exceptions.RequestException as e:
        err_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                body = e.response.json()
                err_msg = body.get('detail', body.get('error', err_msg))
            except Exception:
                pass
        return False, {'error': err_msg}
