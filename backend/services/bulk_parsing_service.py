"""
Bulk Resume Parsing Service - calls Bulk-Resume-Parser API internally.
Admin-only; no duplicate parsing logic.
"""
import os
import requests

BULK_PARSER_URL = os.getenv('BULK_PARSER_URL', 'http://localhost:8001').rstrip('/')


def upload_files(files_list, output_filename=None, append=False):
    """
    Forward file upload to Bulk-Resume-Parser POST /api/upload.
    files_list: list of (filename, file_bytes) or requests-style file tuples.
    Returns (success, {job_id, total_files, ...} or error dict).
    """
    if not BULK_PARSER_URL:
        return False, {'error': 'BULK_PARSER_URL not configured'}

    try:
        files = [('files', (name, data)) for name, data in files_list]
        data = {}
        if output_filename:
            data['output_path'] = output_filename
        if append is not None:
            data['append'] = 'true' if append else 'false'

        resp = requests.post(
            f'{BULK_PARSER_URL}/api/upload',
            files=files,
            data=data,
            timeout=30,
        )
        resp.raise_for_status()
        return True, resp.json()
    except requests.exceptions.RequestException as e:
        err = str(e)
        if getattr(e, 'response', None) is not None:
            try:
                err = e.response.json().get('detail', err)
            except Exception:
                pass
        return False, {'error': err}


def get_progress(job_id):
    """Forward progress check to Bulk-Resume-Parser GET /api/progress/{job_id}."""
    if not BULK_PARSER_URL:
        return False, {'error': 'BULK_PARSER_URL not configured'}
    try:
        resp = requests.get(f'{BULK_PARSER_URL}/api/progress/{job_id}', timeout=10)
        resp.raise_for_status()
        return True, resp.json()
    except requests.exceptions.RequestException as e:
        err = str(e)
        if getattr(e, 'response', None) is not None and e.response.status_code == 404:
            return False, {'error': 'Job not found'}
        return False, {'error': err}


def get_download_url(job_id):
    """Return URL for client to download Excel from Bulk-Resume-Parser (same-origin proxy recommended)."""
    if not BULK_PARSER_URL:
        return None
    return f'{BULK_PARSER_URL}/api/download/{job_id}'


def stream_download(job_id):
    """
    Stream Excel file from Bulk-Resume-Parser to caller.
    Returns (success, (content_iterator, filename, content_type)) or (False, error_dict).
    """
    if not BULK_PARSER_URL:
        return False, {'error': 'BULK_PARSER_URL not configured'}
    try:
        resp = requests.get(
            f'{BULK_PARSER_URL}/api/download/{job_id}',
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()
        filename = resp.headers.get('Content-Disposition', '').split('filename=')[-1].strip('"\'') or 'Parsed_Resumes.xlsx'
        content_type = resp.headers.get('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        return True, (resp.iter_content(chunk_size=8192), filename, content_type)
    except requests.exceptions.RequestException as e:
        err = str(e)
        if getattr(e, 'response', None) is not None:
            if e.response.status_code == 404:
                err = 'Job not found or not completed'
            elif e.response.status_code == 400:
                err = 'Job not completed yet'
        return False, {'error': err}
