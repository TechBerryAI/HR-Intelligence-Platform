/**
 * Document Intelligence Engine — client API.
 *
 * React MUST consume Form DTOs only (`result.form`).
 * Raw TOON / AI output is never mapped on the frontend.
 */
import { BASE_URL as API_URL } from './api';

function validationHeaders() {
  // Never embed validation bypass tokens in production bundles.
  if (import.meta.env.PROD) return {};
  const token = import.meta.env.VITE_VALIDATION_TOKEN;
  if (!token) return {};
  return { 'X-Validation-Token': String(token) };
}

/**
 * Prefer server-provided parse failure detail over a generic label.
 */
export function extractParseErrorMessage(payload, fallback = 'Unable to parse this document') {
  if (!payload) return fallback;
  if (typeof payload === 'string') {
    const s = payload.trim();
    return s || fallback;
  }
  const candidates = [
    payload.error,
    payload.message,
    payload.detail,
    payload.reason,
  ];
  for (const c of candidates) {
    if (typeof c === 'string' && c.trim()) return c.trim();
    if (c && typeof c === 'object') {
      const nested = c.message || c.error || c.detail;
      if (typeof nested === 'string' && nested.trim()) return nested.trim();
    }
  }
  if (Array.isArray(payload.errors) && payload.errors.length) {
    return payload.errors
      .map((e) => (typeof e === 'string' ? e : e?.message || e?.error || ''))
      .filter(Boolean)
      .join('; ') || fallback;
  }
  return fallback;
}

/**
 * Upload and parse resume file (authenticated).
 * @returns {Promise<Object>} Parse result with `form` Form DTO
 */
export async function uploadAndParseResume(file, candidateId = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (candidateId) {
    formData.append('candidate_id', candidateId);
  }

  const token = localStorage.getItem('jwtToken');

  const response = await fetch(`${API_URL}/api/parse/resume`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractParseErrorMessage(error, 'Failed to parse resume'));
  }

  return await response.json();
}

/**
 * Public resume parse for apply-form autofill (no auth).
 */
export async function uploadAndParseResumePublic(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_URL}/api/parse/resume/public`, {
    method: 'POST',
    headers: {
      ...validationHeaders(),
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractParseErrorMessage(error, 'Failed to parse resume'));
  }

  return await response.json();
}

function applySseChunk(chunk, { onStage, sink }) {
  const lines = String(chunk || '').split('\n');
  let eventName = 'message';
  const dataLines = [];
  for (const line of lines) {
    const trimmed = line.replace(/\r$/, '');
    if (trimmed.startsWith('event:')) eventName = trimmed.slice(6).trim();
    else if (trimmed.startsWith('data:')) dataLines.push(trimmed.slice(5).trimStart());
  }
  if (!dataLines.length) return;
  let data;
  try {
    data = JSON.parse(dataLines.join('\n'));
  } catch {
    return;
  }
  if (eventName === 'stage' && onStage) onStage(data);
  if (eventName === 'result') sink.result = data;
  if (eventName === 'error') sink.errorPayload = data;
}

/**
 * Parse SSE stream from Document Intelligence Engine.
 */
async function consumeParseSSE(response, { onStage } = {}) {
  const contentType = response.headers.get('content-type') || '';
  if (!response.ok) {
    if (contentType.includes('application/json')) {
      const error = await response.json().catch(() => ({}));
      throw new Error(extractParseErrorMessage(error, 'Failed to parse document'));
    }
    const text = await response.text().catch(() => '');
    throw new Error(extractParseErrorMessage(text, `Failed to parse document (HTTP ${response.status})`));
  }
  if (!response.body) {
    throw new Error('Failed to parse document: empty response stream');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const sink = { result: null, errorPayload: null };

  const drainBuffer = (flush) => {
    buffer = buffer.replace(/\r\n/g, '\n');
    const chunks = buffer.split('\n\n');
    if (!flush) {
      buffer = chunks.pop() || '';
    } else {
      buffer = '';
    }
    for (const chunk of chunks) {
      applySseChunk(chunk, { onStage, sink });
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      drainBuffer(true);
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    drainBuffer(false);
  }
  if (sink.errorPayload) {
    throw new Error(extractParseErrorMessage(sink.errorPayload, 'Parse failed'));
  }
  if (!sink.result) {
    throw new Error('Parse stream ended without result');
  }
  return sink.result;
}

const SSE_HEADERS = {
  Accept: 'text/event-stream',
  'Cache-Control': 'no-cache',
};

/**
 * Public resume parse with live stage events (SSE).
 * Falls back to sync only for transport/stream issues — never hides a real parse error.
 */
export async function uploadAndParseResumePublicStream(file, { onStage } = {}) {
  const formData = new FormData();
  formData.append('file', file);
  let response;
  try {
    response = await fetch(`${API_URL}/api/parse/resume/public/stream`, {
      method: 'POST',
      headers: {
        ...SSE_HEADERS,
        ...validationHeaders(),
      },
      body: formData,
    });
  } catch {
    return uploadAndParseResumePublic(file);
  }

  // Do not fall back to the blocking /public parse after the stream started.
  // A second OCR pass freezes the overlay on the last SSE stage ("Extracting text").
  return await consumeParseSSE(response, { onStage });
}

/**
 * Authenticated resume parse with live stage events (SSE).
 * Falls back to sync only for transport/stream issues.
 */
export async function uploadAndParseResumeStream(file, candidateId = null, { onStage } = {}) {
  const formData = new FormData();
  formData.append('file', file);
  if (candidateId) formData.append('candidate_id', candidateId);
  const token = localStorage.getItem('jwtToken');
  let response;
  try {
    response = await fetch(`${API_URL}/api/parse/resume/stream`, {
      method: 'POST',
      headers: { ...SSE_HEADERS, Authorization: `Bearer ${token}` },
      body: formData,
    });
  } catch {
    return uploadAndParseResume(file, candidateId);
  }

  return await consumeParseSSE(response, { onStage });
}

/**
 * JD parse with live stage events (SSE).
 */
export async function uploadAndParseJDStream(file, jobId = null, { onStage } = {}) {
  const formData = new FormData();
  formData.append('file', file);
  if (jobId) formData.append('job_id', jobId);
  const token = localStorage.getItem('jwtToken');
  let response;
  try {
    response = await fetch(`${API_URL}/api/parse/jd/stream`, {
      method: 'POST',
      headers: { ...SSE_HEADERS, Authorization: `Bearer ${token}` },
      body: formData,
    });
  } catch {
    return uploadAndParseJD(file, jobId);
  }

  return await consumeParseSSE(response, { onStage });
}

/**
 * Upload and parse job description file.
 */
export async function uploadAndParseJD(file, jobId = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (jobId) {
    formData.append('job_id', jobId);
  }

  const token = localStorage.getItem('jwtToken');

  const response = await fetch(`${API_URL}/api/parse/jd`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(extractParseErrorMessage(error, 'Failed to parse job description'));
  }

  return await response.json();
}

/**
 * Extract Application Form DTO from Document Intelligence response.
 * No mapping — backend already produced the Form DTO.
 * @param {Object} result - API response
 * @returns {Object} Form autofill fields
 */
export function takeResumeFormDTO(result) {
  if (!result || result.status !== 'ok' || !result.form) {
    throw new Error('Invalid parse response: Form DTO missing');
  }
  return result.form;
}

/**
 * Extract Job Create Form DTO from Document Intelligence response.
 */
export function takeJDFormDTO(result) {
  if (!result || result.status !== 'ok' || !result.form) {
    throw new Error('Invalid parse response: Form DTO missing');
  }
  const form = result.form;
  // Normalize keywords for the job form (string field)
  if (!form.keywords) {
    const list = Array.isArray(form._keywords) ? form._keywords : [];
    form.keywords = list.filter(Boolean).join(', ');
  }
  return form;
}

/**
 * Validate file before upload.
 */
export function validateFileForParsing(file) {
  const allowedExtensions = ['pdf', 'docx', 'png', 'jpg', 'jpeg', 'webp'];
  const maxSize = 10 * 1024 * 1024; // 10MB

  const extension = file.name.split('.').pop().toLowerCase();

  if (extension === 'doc') {
    return {
      valid: false,
      error: 'Legacy .doc format is not supported. Please use DOCX or PDF.',
    };
  }

  if (!allowedExtensions.includes(extension)) {
    return {
      valid: false,
      error: 'Invalid file type. Please upload PDF, DOCX, PNG, JPG, or WEBP files only.',
    };
  }

  if (file.size > maxSize) {
    return {
      valid: false,
      error: 'File too large. Maximum size is 10MB.',
    };
  }

  return { valid: true, error: null };
}
