// Health check utility to verify backend is running
import { BASE_URL } from './api';

let backendHealthy = true; // Default to true for better UX
let lastCheckTime = 0;
const CHECK_INTERVAL = 30000; // Check every 30 seconds

/**
 * Check if the backend server is healthy
 * @param {boolean} force - Force a new check even if recently checked
 * @returns {Promise<boolean>} - True if backend is healthy
 */
export async function checkBackendHealth(force = false) {
  const now = Date.now();
  
  // Return cached result if recently checked (within CHECK_INTERVAL)
  if (!force && backendHealthy && (now - lastCheckTime) < CHECK_INTERVAL) {
    return true;
  }
  
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000); // 3 second timeout
    
    const response = await fetch(`${BASE_URL}/health`, {
      method: 'GET',
      signal: controller.signal,
      cache: 'no-cache',
    });
    
    clearTimeout(timeoutId);
    
    backendHealthy = response.ok;
    lastCheckTime = now;
    
    // Only log failures, not successes (reduce console noise)
    if (!backendHealthy && import.meta.env?.DEV) {
      console.warn('[Health Check] Backend health check failed, status:', response.status);
    }
    
    return backendHealthy;
  } catch (error) {
    // Only log in development
    if (import.meta.env?.DEV) {
      console.warn('[Health Check] Backend unavailable:', error.name);
    }
    backendHealthy = false;
    lastCheckTime = now;
    return false;
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
      console.log(`[Health Check] Backend not available, retrying in ${delayMs}ms... (${attempt}/${maxAttempts})`);
      await new Promise(resolve => setTimeout(resolve, delayMs));
    }
  }
  
  console.error('[Health Check] Backend failed to become available after', maxAttempts, 'attempts');
  return false;
}

/**
 * Get the current backend health status (from cache)
 * @returns {boolean} - True if backend was healthy in last check
 */
export function getBackendHealthStatus() {
  return backendHealthy;
}

