// API client with robust retry logic and error handling.
// Same-origin by default: leave VITE_API_URL empty so requests go to /api and /health
// on whatever host opened the UI. Vite proxies those paths in dev; production reverse
// proxy should do the same. Set an absolute VITE_API_URL only for rare split-origin setups.
// Auth is httpOnly-cookie based on the web (see core/auth/tokenService.js); `credentials:
// 'include'` below is what makes that cookie actually go out on same-origin requests.
import { tokenService } from '@/core/auth/tokenService.js';
import { markBackendSeen } from '@/core/api/healthCheck.js';

// Empty string = same-origin relative URLs (recommended)
export const BASE_URL = (import.meta.env?.VITE_API_URL ?? '').replace(/\/$/, '');

// Retry configuration
const RETRY_CONFIG = {
  maxRetries: 2, // Reduced from 3 - fail faster for better UX
  initialDelayMs: 500, // Reduced from 1000 - faster initial retry
  maxDelayMs: 3000, // Reduced from 5000
  backoffMultiplier: 2,
};

// Log the configured BASE_URL in development
if (import.meta.env?.DEV) {
  console.log('API BASE_URL configured:', BASE_URL || '(same-origin)');
}

// Helper to wait with exponential backoff
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Check if error is retryable
function isRetryableError(error) {
  // Retry on network errors, timeouts, and 5xx server errors
  if (error.name === 'AbortError') return false; // Don't retry aborted requests
  if (error.message === 'Network error') return true;
  if (error.status >= 500 && error.status < 600) return true;
  if (error.cause?.code === 'ECONNREFUSED') return true;
  if (error.cause?.code === 'ETIMEDOUT') return true;
  if (error.cause?.code === 'ENOTFOUND') return true;
  return false;
}

let onUnauthorized = null;
let onTokensRefreshed = null;

export function setUnauthorizedHandler(fn) {
  onUnauthorized = typeof fn === 'function' ? fn : null;
}

export function setOnTokensRefreshed(fn) {
  onTokensRefreshed = typeof fn === 'function' ? fn : null;
}

function joinUrl(base, path) {
  if (/^https?:\/\//i.test(path)) return path;
  const p = path.startsWith('/') ? path : `/${path}`;
  // Empty base = same-origin relative path (intentional)
  if (!base) return p;
  return `${base}${p}`;
}

function getErrorMessage(data, statusText) {
  return (data && (data.error || data.message)) || statusText || 'Request failed';
}

// 401s that are ordinary request failures, not a dead session (wrong password
// on login / change-password, webhook secrets). They must never log anyone out.
const NON_SESSION_401_PATTERNS = [
  'invalid email or password',
  'current password',
  'callback secret',
  'x-platform-key',
];

// 403s that DO mean the session is gone. Every other 403 is a permission
// answer for this one request ("Access denied", "you do not have permission
// to update this job", "Read-only access", ...) and must only surface as an
// error — treating those as auth failures is what used to log recruiters out
// whenever they toggled or deleted a job they didn't post.
const SESSION_403_PATTERNS = [
  'invalid or expired token',
  'refresh token',
  'account inactive',
];

/** True only when the response means "this login is no longer valid". */
export function isSessionAuthError(status, message) {
  const msg = (message || '').toLowerCase();
  if (status === 401) {
    return !NON_SESSION_401_PATTERNS.some((p) => msg.includes(p));
  }
  if (status === 403) {
    return SESSION_403_PATTERNS.some((p) => msg.includes(p));
  }
  return false;
}

// A CSRF failure means this one request's double-submit header didn't match
// the cookie — it says nothing about whether the session itself is still
// valid, so it must never be treated the same as a real 401/expired-token
// auth failure (that would force a full logout over what's usually a
// transient, retryable mismatch).
function isCsrfError(status, message) {
  return status === 403 && (message || '').toLowerCase().includes('csrf');
}

function readCsrfCookie() {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Double-submit header for state-changing requests. Any raw fetch() that
 * POSTs to an authenticated route (e.g. the SSE parse streams) must spread
 * this into its headers — the browser auto-attaches the access cookie, so the
 * backend CSRF-checks the request and rejects it with 403 without this.
 */
export function csrfHeaders() {
  const value = readCsrfCookie();
  return value ? { 'X-CSRF-Token': value } : {};
}

/** Decode JWT payload without verifying signature (client-side expiry check only). */
function decodeJwtPayload(token) {
  if (!token || typeof token !== 'string') return null;
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
    const json = typeof atob === 'function' ? atob(padded) : Buffer.from(padded, 'base64').toString('utf8');
    return JSON.parse(json);
  } catch {
    return null;
  }
}

const PROACTIVE_REFRESH_WINDOW_SEC = 120; // refresh when access JWT expires within 2 minutes
let refreshInFlight = null;

async function tryRefreshOnce() {
  // No early-return-if-empty here: a web client after a page reload has no
  // in-memory refresh token (it was never in localStorage to begin with),
  // but the httpOnly refresh cookie the backend set still carries one, so
  // this call must still fire — the cookie goes along via credentials:
  // 'include'. Electron has no cookie in production, so it sends its
  // in-memory token in the body instead.
  const refreshToken = tokenService.getRefreshToken();
  const refreshUrl = joinUrl(BASE_URL, '/api/refresh');
  try {
    const res = await fetch(refreshUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      credentials: 'include',
      body: refreshToken ? JSON.stringify({ refresh_token: refreshToken }) : undefined,
    });
    if (!res.ok) return false;
    const json = await res.json().catch(() => ({}));
    if (!json.token || !json.refresh_token) return false;
    tokenService.setToken(json.token);
    tokenService.setRefreshToken(json.refresh_token);
    if (typeof onTokensRefreshed === 'function') {
      try { onTokensRefreshed(json.token, json.refresh_token); } catch {}
    }
    return true;
  } catch {
    return false;
  }
}

/** Single-flight refresh — concurrent callers share one in-flight promise. */
export async function tryRefresh() {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = tryRefreshOnce().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

/** If access token expires soon, refresh before the request. */
export async function ensureFreshAccessToken() {
  const access = tokenService.getToken();
  if (!access) return;
  const payload = decodeJwtPayload(access);
  const exp = payload?.exp;
  if (typeof exp !== 'number') return;
  const nowSec = Math.floor(Date.now() / 1000);
  if (exp - nowSec <= PROACTIVE_REFRESH_WINDOW_SEC) {
    await tryRefresh();
  }
}

export async function apiRequest(
  path,
  { method = 'GET', body, token, headers = {}, timeoutMs, skipRetry = false, skipAuthHandler = false } = {}
) {
  if (import.meta.env?.PROD && BASE_URL && BASE_URL.startsWith('http://')) {
    // eslint-disable-next-line no-console
    console.warn('Insecure API base URL over http in production');
  }

  const url = joinUrl(BASE_URL, path);
  
  // Attempt the request with retry logic
  let lastError;
  const maxAttempts = skipRetry ? 1 : RETRY_CONFIG.maxRetries;
  
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    // Log API requests in development (only first attempt to reduce noise)
    if (import.meta.env?.DEV && attempt === 0) {
      console.log(`[API] ${method} ${url}`);
    }
    
    try {
      const result = await performRequest(url, method, body, token, headers, timeoutMs, false, skipAuthHandler);
      
      // Success - log retry success if applicable
      if (attempt > 0 && import.meta.env?.DEV) {
        console.log(`[API] ✓ Request succeeded after ${attempt} ${attempt === 1 ? 'retry' : 'retries'}`);
      }
      // Any successful API traffic (incl. bulk progress) proves the backend is up
      try { markBackendSeen(); } catch { /* ignore */ }
      return result;
      
    } catch (error) {
      lastError = error;
      
      // Don't retry on 4xx errors (client errors) or non-retryable errors
      if (!isRetryableError(error)) {
        throw error;
      }
      
      // Don't retry if this is the last attempt
      if (attempt === maxAttempts - 1) {
        break;
      }
      
      // Calculate delay with exponential backoff
      const delayMs = Math.min(
        RETRY_CONFIG.initialDelayMs * Math.pow(RETRY_CONFIG.backoffMultiplier, attempt),
        RETRY_CONFIG.maxDelayMs
      );
      
      if (import.meta.env?.DEV) {
        console.warn(`[API] ⟲ Retrying in ${delayMs}ms (${attempt + 1}/${maxAttempts})...`);
      }
      
      await delay(delayMs);
    }
  }
  
  // All retries exhausted
  if (import.meta.env?.DEV) {
    console.error(`[API] Request failed after ${maxAttempts} attempts`, lastError);
  }
  
  // Enhance error message to be more user-friendly
  if (lastError.message === 'Network error') {
    lastError.message = 'Connection failed. Please check your internet connection and try again.';
  } else if (lastError.status === 500) {
    lastError.message = 'Server error. Please try again in a moment.';
  } else if (lastError.status === 503) {
    lastError.message = 'Service temporarily unavailable. Please try again shortly.';
  } else if (lastError.cause?.code === 'ECONNREFUSED') {
    lastError.message = 'Unable to reach server. The service may be starting up.';
  }
  
  throw lastError;
}

async function performRequest(url, method, body, token, headers, timeoutMs, alreadyTriedRefresh = false, skipAuthHandler = false) {
  if (!alreadyTriedRefresh) {
    try {
      await ensureFreshAccessToken();
    } catch {
      // ignore proactive refresh errors; request may still succeed or reactive path will run
    }
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
  // Web sessions authenticate via an httpOnly cookie the browser attaches
  // automatically — there's no bearer token to read here even when a request
  // is genuinely authenticated, so `bearer` alone can't be used below to tell
  // "this request tried to authenticate" from "this request didn't." CSRF
  // protection for state-changing requests instead: echo the (non-HttpOnly)
  // csrf cookie back as a header so the backend can double-submit-check it.
  if (!/^(GET|HEAD)$/i.test(method)) {
    const csrf = readCsrfCookie();
    if (csrf) {
      finalHeaders.set('X-CSRF-Token', csrf);
    }
  }

  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const defaultTimeout = Number(import.meta.env?.VITE_API_TIMEOUT_MS) || 30000; // Increased to 30s
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
      console.error('Network error calling API', { url, method, error: networkErr.message });
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
    const message = isJson ? getErrorMessage(data, res.statusText) : (res.statusText || 'Request failed');
    const csrfFailure = isCsrfError(res.status, message);
    const sessionFailure = !csrfFailure && isSessionAuthError(res.status, message);

    // A stale/missing CSRF header is retried once as-is (not via tryRefresh —
    // the session itself is fine, only this request's header was wrong or
    // absent) rather than treated as an auth failure. If the csrf cookie is
    // gone entirely (cleared, or expired while the access cookie survived),
    // a plain retry would fail identically — /api/refresh re-issues it.
    if (csrfFailure && !alreadyTriedRefresh) {
      if (!readCsrfCookie()) {
        await tryRefresh();
      }
      return performRequest(url, method, body, tokenService.getToken() || token, headers, timeoutMs, true, skipAuthHandler);
    }

    if (sessionFailure && !alreadyTriedRefresh) {
      // Retry once even when the refresh itself failed: refresh tokens rotate,
      // so if another tab refreshed a moment earlier our refresh loses the race
      // ("already rotated") — but the browser's cookie jar now already holds
      // that tab's fresh access cookie, and the retry goes out with it.
      await tryRefresh();
      return performRequest(url, method, body, tokenService.getToken() || token, headers, timeoutMs, true, skipAuthHandler);
    }

    // Only logout if this request's bearer is still the active session token.
    // Stale in-flight 401/403s from a previous session must not wipe a fresh login
    // (common right after reconnecting Google Calendar or re-logging in).
    const tokenStillCurrent = !bearer || bearer === tokenService.getToken();
    if (
      sessionFailure &&
      tokenStillCurrent &&
      !skipAuthHandler &&
      typeof onUnauthorized === 'function'
    ) {
      try { onUnauthorized(); } catch {}
    }

    const error = new Error(message);
    error.status = res.status;
    error.data = data;
    throw error;
  }

  return data;
}
