"""
AI interviewer: generate questions and evaluate candidate answers.
Uses the same X.AI key rotation as resume parsing; falls back to templates if LLM fails.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

from app.integrations.openai.llm_service import (
    LLM_REQUEST_TIMEOUT,
    XAI_MODEL,
    _get_session,
    parse_llm_response,
)

FALLBACK_QUESTIONS = [
    {
        'id': 'q1',
        'question': 'Walk me through your most relevant experience for this role.',
        'category': 'behavioral',
        'difficulty': 'easy',
    },
    {
        'id': 'q2',
        'question': 'Describe a challenging technical problem you solved recently and how you approached it.',
        'category': 'technical',
        'difficulty': 'medium',
    },
    {
        'id': 'q3',
        'question': 'How do you prioritize tasks when you have multiple urgent deadlines?',
        'category': 'situational',
        'difficulty': 'medium',
    },
    {
        'id': 'q4',
        'question': 'What interests you about this company and this specific role?',
        'category': 'culture',
        'difficulty': 'easy',
    },
    {
        'id': 'q5',
        'question': 'Tell me about a time you had to learn a new tool or technology quickly. What was the outcome?',
        'category': 'behavioral',
        'difficulty': 'medium',
    },
]


def _call_json_llm(system: str, user: str, service_id: str = 'interview') -> Dict[str, Any]:
    from app.integrations.openai.key_manager import get_key_for_service, report_result

    url = 'https://api.x.ai/v1/chat/completions'
    payload = {
        'model': XAI_MODEL,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'temperature': 0.3,
        'max_tokens': 2048,
    }
    keys_tried = 0
    last_error: Optional[str] = None
    try:
        mgr = __import__('llm_key_manager', fromlist=['KeyManager']).KeyManager.get_instance()
        key_count = mgr._registry.count
    except Exception:
        key_count = 0
    max_keys = key_count if key_count else 1
    timeout = max(15, min(120, LLM_REQUEST_TIMEOUT))

    while keys_tried < max_keys:
        key_slot = get_key_for_service(service_id)
        if not key_slot:
            raise ValueError('No LLM API key configured')
        slot_id, secret = key_slot
        keys_tried += 1
        headers = {'Authorization': f'Bearer {secret}', 'Content-Type': 'application/json'}
        t0 = time.perf_counter()
        try:
            response = _get_session().post(url, headers=headers, json=payload, timeout=timeout)
            latency_ms = (time.perf_counter() - t0) * 1000
            if response.ok:
                report_result(slot_id, True, response.status_code, latency_ms)
                content = response.json()['choices'][0]['message']['content']
                return parse_llm_response(content)
            report_result(slot_id, False, response.status_code, latency_ms)
            if 400 <= response.status_code < 500 and response.status_code != 429:
                raise ValueError(f'LLM API error ({response.status_code})')
            last_error = f'LLM API error ({response.status_code})'
        except requests.exceptions.RequestException:
            latency_ms = (time.perf_counter() - t0) * 1000
            report_result(slot_id, False, None, latency_ms)
            last_error = 'LLM network error'
    raise ValueError(last_error or 'LLM call failed')


def generate_interview_questions(
    job_title: str,
    company: str = '',
    job_context: str = '',
    candidate_summary: str = '',
    count: int = 5,
) -> List[Dict[str, Any]]:
    """Return a list of interview question objects."""
    system = (
        'You are an expert hiring interviewer. Return ONLY valid JSON with key "questions": '
        'an array of objects with fields question, category (technical|behavioral|situational|culture), '
        'difficulty (easy|medium|hard). No markdown.'
    )
    user = (
        f'Generate {count} interview questions for role "{job_title or "the open position"}" '
        f'at "{company or "the company"}".\n'
        f'Job context:\n{(job_context or "N/A")[:2500]}\n\n'
        f'Candidate summary:\n{(candidate_summary or "N/A")[:2000]}\n'
    )
    try:
        raw = _call_json_llm(system, user)
        questions = raw.get('questions') if isinstance(raw, dict) else None
        if not isinstance(questions, list) or not questions:
            return _with_ids(FALLBACK_QUESTIONS[:count])
        cleaned = []
        for i, q in enumerate(questions[:count]):
            if not isinstance(q, dict):
                continue
            text = str(q.get('question') or '').strip()
            if not text:
                continue
            cleaned.append({
                'id': f'q{i + 1}',
                'question': text,
                'category': str(q.get('category') or 'behavioral'),
                'difficulty': str(q.get('difficulty') or 'medium'),
                'rationale': str(q.get('rationale') or ''),
            })
        return cleaned or _with_ids(FALLBACK_QUESTIONS[:count])
    except Exception as e:
        print(f'[ai_interview] generate_questions fallback: {e}')
        return _with_ids(FALLBACK_QUESTIONS[:count])


def evaluate_answer(question: str, answer: str, job_title: str = '') -> Dict[str, Any]:
    """Score a single answer 0–100 with short feedback."""
    answer = (answer or '').strip()
    if len(answer) < 8:
        return {'score': 15, 'feedback': 'Answer was too short or incomplete.'}

    system = (
        'You are an AI interviewer evaluating a candidate answer. '
        'Return ONLY JSON: {"score": number 0-100, "feedback": "short constructive feedback"}.'
    )
    user = (
        f'Role: {job_title or "open role"}\n'
        f'Question: {question}\n'
        f'Candidate answer: {answer[:3000]}\n'
    )
    try:
        raw = _call_json_llm(system, user)
        score = float(raw.get('score', 50))
        score = max(0, min(100, score))
        feedback = str(raw.get('feedback') or 'No feedback provided.').strip()
        return {'score': round(score, 1), 'feedback': feedback}
    except Exception as e:
        print(f'[ai_interview] evaluate_answer fallback: {e}')
        # Heuristic fallback
        words = len(re.findall(r'\w+', answer))
        score = 40 + min(40, words // 5)
        return {
            'score': float(score),
            'feedback': 'Automated heuristic score (LLM unavailable). Consider detail and relevance.',
        }


def finalize_interview(answers: List[Dict[str, Any]], job_title: str = '') -> Dict[str, Any]:
    """Compute overall score and summary from evaluated answers."""
    if not answers:
        return {'overall_score': 0, 'score_summary': 'No answers submitted.', 'recommendation': 'incomplete'}

    scores = [float(a.get('score') or 0) for a in answers]
    overall = round(sum(scores) / len(scores), 1) if scores else 0

    if overall >= 75:
        recommendation = 'strong_hire'
        label = 'Strong hire signal'
    elif overall >= 60:
        recommendation = 'hire'
        label = 'Positive hire signal'
    elif overall >= 45:
        recommendation = 'maybe'
        label = 'Mixed results — human review recommended'
    else:
        recommendation = 'no_hire'
        label = 'Weak performance — review carefully'

    summary_bits = [f'Overall AI interview score: {overall}/100 ({label}).']
    for a in answers[:8]:
        q = str(a.get('question') or '')[:80]
        s = a.get('score')
        summary_bits.append(f'- [{s}] {q}')

    return {
        'overall_score': overall,
        'score_summary': '\n'.join(summary_bits),
        'recommendation': recommendation,
        'job_title': job_title,
    }


def _with_ids(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i, q in enumerate(questions):
        item = dict(q)
        item.setdefault('id', f'q{i + 1}')
        out.append(item)
    return out
