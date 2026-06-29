// API client with robust retry logic and error handling
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

// Retry configuration
const RETRY_CONFIG = {
  maxRetries: 2, // Reduced from 3 - fail faster for better UX
  initialDelayMs: 500, // Reduced from 1000 - faster initial retry
  maxDelayMs: 3000, // Reduced from 5000
  backoffMultiplier: 2,
};

// Log the configured BASE_URL in development
if (import.meta.env?.DEV) {
  console.log('API BASE_URL configured:', BASE_URL || 'NOT SET - requests will fail');
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
  if (!base) {
    console.warn('BASE_URL is not set! API requests will fail. Set VITE_API_URL in .env file.');
    return path;
  }
  if (/^https?:\/\//i.test(path)) return path;
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${base}${p}`;
}

function getErrorMessage(data, statusText) {
  return (data && (data.error || data.message)) || statusText || 'Request failed';
}

function isRefreshableAuthError(status, message) {
  if (status !== 401 && status !== 403) return false;
  const msg = (message || '').toLowerCase();
  if (msg.includes('access required')) return false;
  return (
    msg.includes('invalid or expired token') ||
    msg.includes('refresh token expired') ||
    msg.includes('invalid refresh token') ||
    status === 401
  );
}

function isRoleMismatchError(message) {
  return (message || '').toLowerCase().includes('access required');
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

async function tryRefresh() {
  const refreshToken = tokenService.getRefreshToken();
  if (!refreshToken) return false;
  const refreshUrl = joinUrl(BASE_URL, '/api/refresh');
  try {
    const res = await fetch(refreshUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ refresh_token: refreshToken }),
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

async function performRequest(url, method, body, token, headers, timeoutMs, alreadyTriedRefresh = false, skipAuthHandler = false) {
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;

  const finalHeaders = new Headers(headers);
  if (!isFormData) {
    if (!finalHeaders.has('Accept')) finalHeaders.set('Accept', 'application/json');
    if (body && !finalHeaders.has('Content-Type')) finalHeaders.set('Content-Type', 'application/json');
  } else {
    if (!finalHeaders.has('Accept')) finalHeaders.set('Accept', 'application/json');
  }

  const bearer = token || tokenService.getToken();
  const sentAuth = !!bearer;
  if (bearer) {
    finalHeaders.set('Authorization', `Bearer ${bearer}`);
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
    const authFailure = res.status === 401 || res.status === 403;
    const roleMismatch = authFailure && isRoleMismatchError(message);
    const refreshable = authFailure && !roleMismatch && isRefreshableAuthError(res.status, message);

    if (refreshable && sentAuth && !alreadyTriedRefresh) {
      const refreshed = await tryRefresh();
      if (refreshed) {
        return performRequest(url, method, body, tokenService.getToken(), headers, timeoutMs, true, skipAuthHandler);
      }
    }

    if (authFailure && sentAuth && !skipAuthHandler && !roleMismatch && typeof onUnauthorized === 'function') {
      try { onUnauthorized(); } catch {}
    }

    const error = new Error(message);
    error.status = res.status;
    error.data = data;
    throw error;
  }

  return data;
}
