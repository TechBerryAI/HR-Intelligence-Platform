"""
LLM Service for Resume and JD Parsing. Output format is TOON (Token-Oriented Object Notation).
Supports X.AI Grok (multi-key rotation), OpenAI, and Anthropic
"""
import os
import time
import requests
from typing import Dict, Any, Literal, Optional

from toon import toon_loads_flex

# Reuse a session for connection keep-alive (faster repeated calls)
_session: Optional[requests.Session] = None

def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session

# Load configuration
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'xai')  # xai, openai, anthropic
XAI_MODEL = os.getenv('XAI_MODEL', 'grok-4-fast-reasoning')  # Fast model for parsing
LLM_REQUEST_TIMEOUT = int(os.getenv('LLM_REQUEST_TIMEOUT', '45'))  # Lower = faster fail; 45s suits grok-4-fast
LLM_MAX_INPUT_CHARS = int(os.getenv('LLM_MAX_INPUT_CHARS', '0'))  # 0 = no trim; set e.g. 18000 to speed very long docs
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')


def call_llm(prompt: str, doc_type: Literal['resume', 'jd']) -> Dict[str, Any]:
    """
    Call LLM to parse document
    
    Args:
        prompt: The prompt containing document text
        doc_type: Type of document ('resume' or 'jd')
    
    Returns:
        Parsed TOON format as dict
    """
    if LLM_MAX_INPUT_CHARS and len(prompt) > LLM_MAX_INPUT_CHARS:
        prompt = prompt[:LLM_MAX_INPUT_CHARS] + "\n\n[Document truncated for length. Extract from above.]"
    if LLM_PROVIDER == 'xai':
        return call_xai_grok(prompt, doc_type)
    elif LLM_PROVIDER == 'openai':
        return call_openai(prompt, doc_type)
    elif LLM_PROVIDER == 'anthropic':
        return call_anthropic(prompt, doc_type)
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")


def call_xai_grok(prompt: str, doc_type: str, service_id: str = "parsing") -> Dict[str, Any]:
    """Call X.AI Grok API with multi-key rotation and cooldown on failure. Optimized for grok-4-fast-reasoning."""
    from llm_key_manager import get_key_for_service, report_result

    url = "https://api.x.ai/v1/chat/completions"
    payload = {
        "model": XAI_MODEL,
        "messages": [
            {"role": "system", "content": get_system_prompt(doc_type)},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    keys_tried = 0
    last_error: Optional[str] = None
    key_count = 0
    try:
        mgr = __import__("llm_key_manager", fromlist=["KeyManager"]).KeyManager.get_instance()
        key_count = mgr._registry.count
    except Exception:
        key_count = 0
    max_keys_to_try = key_count if key_count else 1
    timeout = max(15, min(120, LLM_REQUEST_TIMEOUT))

    while keys_tried < max_keys_to_try:
        key_slot = get_key_for_service(service_id)
        if not key_slot:
            raise ValueError("No LLM API key configured (set HRMS_API_KEY_1..N or XAI_API_KEY)")
        slot_id, secret = key_slot
        keys_tried += 1
        headers = {
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        }
        t0 = time.perf_counter()
        try:
            session = _get_session()
            response = session.post(url, headers=headers, json=payload, timeout=timeout)
            latency_ms = (time.perf_counter() - t0) * 1000
            if response.ok:
                report_result(slot_id, True, response.status_code, latency_ms)
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return parse_llm_response(content)
            status = response.status_code
            report_result(slot_id, False, status, latency_ms)
            if 400 <= status < 500 and status != 429:
                raise ValueError(f"X.AI API error ({status})")
            last_error = f"X.AI API error ({status})"
            continue
        except requests.exceptions.Timeout:
            latency_ms = (time.perf_counter() - t0) * 1000
            report_result(slot_id, False, None, latency_ms)
            last_error = "X.AI API timeout"
            continue
        except requests.exceptions.RequestException as e:
            latency_ms = (time.perf_counter() - t0) * 1000
            report_result(slot_id, False, getattr(e, "response", None) and getattr(e.response, "status_code"), latency_ms)
            if hasattr(e, "response") and e.response is not None and 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                raise ValueError("X.AI API request failed")
            last_error = "X.AI API network error"
            continue
    raise ValueError(last_error or "X.AI API call failed after all keys tried")


def call_openai(prompt: str, doc_type: str) -> Dict[str, Any]:
    """Call OpenAI API"""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured")
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4-turbo-preview",
        "messages": [
            {
                "role": "system",
                "content": get_system_prompt(doc_type)
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"}
    }
    
    # Retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            return parse_llm_response(content)
            
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            if attempt < max_retries - 1:
                import time
                wait_time = (attempt + 1) * 2
                print(f"[LLM RETRY] OpenAI error, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            raise ValueError(f"OpenAI API error: {str(e)}")
    
    raise ValueError("OpenAI API call failed after all retries")


def call_anthropic(prompt: str, doc_type: str) -> Dict[str, Any]:
    """Call Anthropic Claude API"""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not configured")
    
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 2000,
        "temperature": 0.3,
        "system": get_system_prompt(doc_type),
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    # Retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            
            result = response.json()
            content = result['content'][0]['text']
            
            return parse_llm_response(content)
            
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            if attempt < max_retries - 1:
                import time
                wait_time = (attempt + 1) * 2
                print(f"[LLM RETRY] Anthropic error, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            raise ValueError(f"Anthropic API error: {str(e)}")
    
    raise ValueError("Anthropic API call failed after all retries")


def get_system_prompt(doc_type: str) -> str:
    """Get system prompt for LLM. Required output format is TOON (Token-Oriented Object Notation)."""
    if doc_type == 'resume':
        return """You are an expert resume parser. Extract ALL information from the resume including EVERY URL. Return ONLY valid TOON (Token-Oriented Object Notation): one key-value per line, key: value, nested keys with dots, scalar lists with pipe. Example:

type: resume
person.name: Full Name
person.email: email@example.com
person.phone: +1234567890
person.location: City, State/Country
person.linkedin: https://linkedin.com/in/username
person.github: 
person.portfolio: 
person.website: 
person.twitter: 
person.otherUrls[0]:
summary: Professional summary
skills: skill1|skill2
experience.0.title: Job Title
experience.0.company: Company Name
experience.0.from: 2020-01
experience.0.to: 2023-12
experience.0.years: 3.9
education.0.degree: Bachelor of Science
education.0.field: Computer Science
education.0.institution: University Name
education.0.year: 2020
certifications: cert1|cert2
total_experience_years: 3.9

CRITICAL: Extract EVERY URL (LinkedIn, GitHub, portfolio, website, Twitter) into the person fields; use empty string if not found. Extract location/city/address (e.g. Mumbai, Bangalore, Delhi NCR, City - Country) into person.location. Use pipe (|) for lists of strings. Return ONLY the TOON block, no markdown, no explanations. You may also return valid JSON and it will be accepted."""
    
    else:  # jd
        return """You are an expert job description parser. Extract information and return ONLY valid TOON (Token-Oriented Object Notation): one key-value per line, key: value, lists with pipe. Example:

type: job_description
title: Job Title
company: Company Name
location: City, Country
salary_range: 50000-80000
min_experience_years: 2
max_experience_years: 5
skills: skill1|skill2
responsibilities: resp1|resp2
qualifications: qual1|qual2
keywords: keyword1|keyword2

CRITICAL: Extract the COMPANY NAME. Return ONLY the TOON block, no markdown. You may also return valid JSON and it will be accepted."""


def parse_llm_response(content: str) -> Dict[str, Any]:
    """Parse LLM response as TOON or legacy JSON into a dict."""
    parsed = toon_loads_flex(content)
    if not parsed:
        raise ValueError("Failed to parse LLM response as TOON or JSON")
    return parsed


def classify_document(text: str) -> Literal['resume', 'jd', 'unknown']:
    """
    Classify document type using simple heuristics
    
    Args:
        text: Document text
    
    Returns:
        Document type: 'resume', 'jd', or 'unknown'
    """
    text_lower = text.lower()
    
    # Resume indicators
    resume_keywords = ['resume', 'cv', 'curriculum vitae', 'experience', 'education', 'skills', 'objective']
    resume_score = sum(1 for kw in resume_keywords if kw in text_lower)
    
    # JD indicators
    jd_keywords = ['job description', 'responsibilities', 'requirements', 'qualifications', 'we are looking for', 'position']
    jd_score = sum(1 for kw in jd_keywords if kw in text_lower)
    
    if resume_score > jd_score and resume_score >= 2:
        return 'resume'
    elif jd_score > resume_score and jd_score >= 2:
        return 'jd'
    else:
        return 'unknown'

