"""
LLM Service for Resume and JD Parsing
Supports X.AI Grok, OpenAI, and Anthropic
"""
import os
import json
import requests
from typing import Dict, Any, Literal

# Load configuration
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'xai')  # xai, openai, anthropic
XAI_API_KEY = os.getenv('XAI_API_KEY', '')
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


def call_xai_grok(prompt: str, doc_type: str) -> Dict[str, Any]:
    """Call X.AI Grok API"""
    if not XAI_API_KEY:
        raise ValueError("XAI_API_KEY not configured")
    
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": XAI_MODEL,
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
        "max_tokens": 2000
    }
    
    print(f"[LLM] Calling X.AI Grok with model: {XAI_MODEL}")
    print(f"[LLM] API URL: {url}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"[LLM ERROR] HTTP {e.response.status_code}: {e.response.text}")
        raise ValueError(f"X.AI API error ({e.response.status_code}): {e.response.text}")
    
    result = response.json()
    content = result['choices'][0]['message']['content']
    
    # Parse JSON from response
    return parse_llm_response(content)


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
    
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    
    result = response.json()
    content = result['choices'][0]['message']['content']
    
    return parse_llm_response(content)


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
    
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    
    result = response.json()
    content = result['content'][0]['text']
    
    return parse_llm_response(content)


def get_system_prompt(doc_type: str) -> str:
    """Get system prompt for LLM based on document type"""
    if doc_type == 'resume':
        return """You are an expert resume parser. Extract ALL information from the resume and return ONLY a valid JSON object in this exact format. Be thorough and extract dates, years, and all details:

{
  "type": "resume",
  "person": {
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "+1234567890"
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

