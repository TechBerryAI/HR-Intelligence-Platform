// API client
// Backend CORS requirements for local dev:
//   app.use(cors({
//     origin: 'http://localhost:5173',
//     credentials: true,
//   }))
// If you migrate auth to HttpOnly cookies, ensure the backend sets them and
// keep `credentials: 'include'` (already set below). You may then stop
// attaching Authorization headers and persisting tokens.
import { tokenService } from './tokenService';

// Default to localhost:3000 if VITE_API_URL is not set (for development)
export const BASE_URL = (import.meta.env?.VITE_API_URL || 'http://localhost:3000').replace(/\/$/, '');

// Log the configured BASE_URL in development
if (import.meta.env?.DEV) {
  console.log('API BASE_URL configured:', BASE_URL || 'NOT SET - requests will fail');
}

let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = typeof fn === 'function' ? fn : null;
}

function joinUrl(base, path) {
  if (!base) {
    console.warn('BASE_URL is not set! API requests will fail. Set VITE_API_URL in .env file.');
    return path;
  }
  if (/^https?:\/\//i.test(path)) return path;
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${base}${p}`;
}

export async function apiRequest(
  path,
  { method = 'GET', body, token, headers = {}, timeoutMs } = {}
) {
  if (import.meta.env?.PROD && BASE_URL && BASE_URL.startsWith('http://')) {
    // eslint-disable-next-line no-console
    console.warn('Insecure API base URL over http in production');
  }

  const url = joinUrl(BASE_URL, path);
  // Log all API requests in development for debugging
  if (import.meta.env?.DEV) {
    console.log(`[API] ${method} ${url}`, body ? { body } : '');
  }
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;

  const finalHeaders = new Headers(headers);
  if (!isFormData) {
    if (!finalHeaders.has('Accept')) finalHeaders.set('Accept', 'application/json');
    if (body && !finalHeaders.has('Content-Type')) finalHeaders.set('Content-Type', 'application/json');
  } else {
    if (!finalHeaders.has('Accept')) finalHeaders.set('Accept', 'application/json');
  }

  const bearer = token || tokenService.getToken();
  if (bearer) {
    finalHeaders.set('Authorization', `Bearer ${bearer}`);
  }

  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const defaultTimeout = Number(import.meta.env?.VITE_API_TIMEOUT_MS) || 15000;
  const ms = typeof timeoutMs === 'number' ? timeoutMs : defaultTimeout;
  let timeoutId;
  if (controller && ms > 0) {
    timeoutId = setTimeout(() => controller.abort(), ms);
  }

  const options = {
    method,
    headers: finalHeaders,
    // Send cookies when backend uses HttpOnly session/JWT cookies. Safe to leave enabled.
    credentials: 'include',
    signal: controller ? controller.signal : undefined,
  };

  if (body !== undefined) {
    options.body = isFormData ? body : JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(url, options);
  } catch (networkErr) {
    if (!import.meta.env?.PROD) {
      // eslint-disable-next-line no-console
      console.error('Network error calling API', { url, method, networkErr });
    }
    const error = new Error('Network error');
    error.cause = networkErr;
    throw error;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }

  const contentType = res.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const data = isJson ? await res.json().catch(() => ({})) : await res.text();

  if (!res.ok) {
    if (res.status === 401 && typeof onUnauthorized === 'function') {
      try { onUnauthorized(); } catch {}
    }
    const message = (isJson && data && (data.error || data.message)) || res.statusText || 'Request failed';
    const error = new Error(message);
    error.status = res.status;
    error.data = data;
    throw error;
  }

  return data;
}
