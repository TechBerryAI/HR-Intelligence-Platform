// Health check utility to verify backend is running.
// During bulk parse the API can be busy; keep probes cheap and tolerate brief stalls.

// Keep BASE_URL local to avoid circular import with api.js (which calls markBackendSeen).
const BASE_URL = (import.meta.env?.VITE_API_URL ?? '').replace(/\/$/, '');

let backendHealthy = true; // Default to true for better UX
let lastCheckTime = 0;
let consecutiveFailures = 0;
const CHECK_INTERVAL = 30000; // Check every 30 seconds
const HEALTH_TIMEOUT_MS = 8000; // Allow queued responses while Flask is busy
const FAILURES_BEFORE_UNHEALTHY = 2; // Avoid banner flash on a single timeout
const listeners = new Set();

function notifyListeners() {
  for (const fn of listeners) {
    try {
      fn(backendHealthy);
    } catch {
      /* ignore */
    }
  }
}

/** Subscribe to health flag changes (used by AppContext / ConnectionStatus). */
export function onBackendHealthChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/**
 * Mark backend as reachable after any successful API call (e.g. bulk progress poll).
 * Prevents false "Connecting to server" banners while parsing is actively working.
 */
export function markBackendSeen() {
  const was = backendHealthy;
  backendHealthy = true;
  consecutiveFailures = 0;
  lastCheckTime = Date.now();
  if (!was) notifyListeners();
}

/**
 * Check if the backend server is healthy
 * @param {boolean} force - Force a new check even if recently checked
 * @returns {Promise<boolean>} - True if backend is healthy
 */
export async function checkBackendHealth(force = false) {
  const now = Date.now();

  // Return cached healthy result if recently confirmed
  if (!force && backendHealthy && (now - lastCheckTime) < CHECK_INTERVAL) {
    return true;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);

    // Fast liveness only — dependency probes live on /health?deps=1 and /ready
    const response = await fetch(`${BASE_URL}/health`, {
      method: 'GET',
      signal: controller.signal,
      cache: 'no-cache',
    });

    clearTimeout(timeoutId);

    if (response.ok) {
      markBackendSeen();
      return true;
    }

    consecutiveFailures += 1;
    lastCheckTime = now;
    const was = backendHealthy;
    if (consecutiveFailures >= FAILURES_BEFORE_UNHEALTHY) {
      backendHealthy = false;
    }
    if (was !== backendHealthy) notifyListeners();
    if (import.meta.env?.DEV) {
      console.warn(
        '[Health Check] Backend health check failed, status:',
        response.status,
        `failures=${consecutiveFailures}`,
      );
    }
    return backendHealthy;
  } catch (error) {
    consecutiveFailures += 1;
    lastCheckTime = now;
    const was = backendHealthy;
    if (consecutiveFailures >= FAILURES_BEFORE_UNHEALTHY) {
      backendHealthy = false;
    }
    if (was !== backendHealthy) notifyListeners();
    if (import.meta.env?.DEV) {
      console.warn(
        '[Health Check] Backend unavailable:',
        error.name,
        `failures=${consecutiveFailures}`,
      );
    }
    return backendHealthy;
  }
}

/**
 * Wait for backend to become healthy with retries
 * @param {number} maxAttempts - Maximum number of attempts
 * @param {number} delayMs - Delay between attempts in milliseconds
 * @returns {Promise<boolean>} - True if backend became healthy
 */
export async function waitForBackend(maxAttempts = 10, delayMs = 2000) {
  console.log('[Health Check] Waiting for backend to become available...');

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const isHealthy = await checkBackendHealth(true);

    if (isHealthy) {
      console.log('[Health Check] Backend is healthy!');
      return true;
    }

    if (attempt < maxAttempts) {
      console.log(
        `[Health Check] Backend not available, retrying in ${delayMs}ms... (${attempt}/${maxAttempts})`,
      );
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }

  console.error(
    '[Health Check] Backend failed to become available after',
    maxAttempts,
    'attempts',
  );
  return false;
}

/**
 * Get the current backend health status (from cache)
 * @returns {boolean} - True if backend was healthy in last check
 */
export function getBackendHealthStatus() {
  return backendHealthy;
}
