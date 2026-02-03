"""
LLM Service for Resume and JD Parsing
Supports X.AI Grok (multi-key rotation), OpenAI, and Anthropic
"""
import os
import json
import time
import requests
from typing import Dict, Any, Literal, Optional

# Load configuration
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'xai')  # xai, openai, anthropic
XAI_MODEL = os.getenv('XAI_MODEL', 'grok-4-fast-reasoning')  # Default to fast reasoning model
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
    if LLM_PROVIDER == 'xai':
        return call_xai_grok(prompt, doc_type)
    elif LLM_PROVIDER == 'openai':
        return call_openai(prompt, doc_type)
    elif LLM_PROVIDER == 'anthropic':
        return call_anthropic(prompt, doc_type)
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")


def call_xai_grok(prompt: str, doc_type: str, service_id: str = "parsing") -> Dict[str, Any]:
    """Call X.AI Grok API with multi-key rotation and cooldown on failure."""
    from llm_key_manager import get_key_for_service, report_result

    url = "https://api.x.ai/v1/chat/completions"
    payload = {
        "model": XAI_MODEL,
        "messages": [
            {"role": "system", "content": get_system_prompt(doc_type)},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }
    # Try up to N distinct keys (one attempt per key)
    keys_tried = 0
    last_error: Optional[str] = None
    key_count = 0
    try:
        mgr = __import__("llm_key_manager", fromlist=["KeyManager"]).KeyManager.get_instance()
        key_count = mgr._registry.count
    except Exception:
        key_count = 0
    max_keys_to_try = key_count if key_count else 1

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
            response = requests.post(url, headers=headers, json=payload, timeout=90)
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
    """Get system prompt for LLM based on document type"""
    if doc_type == 'resume':
        return """You are an expert resume parser. Extract ALL information from the resume including EVERY URL you find. Look carefully for LinkedIn, GitHub, portfolio, personal website, Twitter, and any other URLs. Return ONLY a valid JSON object in this exact format:

{
  "type": "resume",
  "person": {
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "+1234567890",
    "linkedin": "https://linkedin.com/in/username or empty string if not found",
    "github": "https://github.com/username or empty string if not found",
    "portfolio": "https://portfolio.example.com or empty string if not found",
    "website": "https://personal-website.com or empty string if not found",
    "twitter": "https://twitter.com/username or empty string if not found",
    "otherUrls": ["https://other-url.com"] or empty array if none found
  },
  "summary": "Professional summary",
  "skills": ["skill1", "skill2"],
  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "from": "2020-01",
      "to": "2023-12",
      "years": 3.9
    }
  ],
  "education": [
    {
      "degree": "Bachelor of Science",
      "field": "Computer Science",
      "institution": "University Name",
      "start": "2016",
      "year": "2020"
    }
  ],
  "certifications": ["cert1", "cert2"],
  "total_experience_years": 3.9
}

CRITICAL INSTRUCTIONS FOR URL EXTRACTION:
- Search the ENTIRE resume text for ANY URLs (http://, https://, www., linkedin.com, github.com, etc.)
- Extract LinkedIn URLs into "linkedin" field (even if format is linkedin.com/in/username without https://)
- Extract GitHub URLs into "github" field
- Extract portfolio/personal website URLs into "portfolio" or "website" fields
- Extract Twitter URLs into "twitter" field
- Put any other URLs found into "otherUrls" array
- If a URL doesn't have http:// or https://, add https:// prefix
- DO NOT skip URLs - extract EVERY URL you find in the resume
- If no URLs are found, use empty strings and empty arrays

Return ONLY the JSON object, no markdown, no explanations."""
    
    else:  # jd
        return """You are an expert job description parser. Extract information from the job description and return ONLY a valid JSON object in this exact format:

{
  "type": "job_description",
  "title": "Job Title",
  "company": "Company Name",
  "location": "City, Country",
  "salary_range": "50000-80000",
  "min_experience_years": 2,
  "max_experience_years": 5,
  "skills": ["skill1", "skill2"],
  "responsibilities": ["resp1", "resp2"],
  "qualifications": ["qual1", "qual2"],
  "keywords": ["keyword1", "keyword2"]
}

CRITICAL: Extract the COMPANY NAME from the job description. Look for:
- Company name in header/footer
- Phrases like "Company:", "About [Company]", "We are [Company]", "Join [Company]"
- Company name mentioned in the job description text
- If company name is not found, use empty string

Return ONLY the JSON object, no markdown, no explanations."""


def parse_llm_response(content: str) -> Dict[str, Any]:
    """Parse LLM response and extract JSON"""
    # Remove markdown code blocks if present
    content = content.strip()
    if content.startswith('```json'):
        content = content[7:]
    elif content.startswith('```'):
        content = content[3:]
    if content.endswith('```'):
        content = content[:-3]
    
    content = content.strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nContent: {content[:200]}")


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

