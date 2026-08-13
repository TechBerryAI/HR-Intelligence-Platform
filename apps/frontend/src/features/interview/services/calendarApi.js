import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'

function token() {
  return tokenService.getToken()
}

export async function fetchGoogleCalendarStatus() {
  return apiRequest('/api/integrations/calendar/google/status', {
    method: 'GET',
    token: token(),
  })
}

export async function startGoogleCalendarConnect() {
  // Return to the same origin+path the user started from so OAuth does not bounce
  // them onto a different host (e.g. FRONTEND_URL LAN IP vs localhost) and drop session.
  const returnTo =
    typeof window !== 'undefined'
      ? `${window.location.origin}${window.location.pathname}`
      : ''
  const qs = returnTo ? `?returnTo=${encodeURIComponent(returnTo)}` : ''
  return apiRequest(`/api/integrations/calendar/google/connect${qs}`, {
    method: 'GET',
    token: token(),
  })
}

export async function disconnectGoogleCalendar() {
  return apiRequest('/api/integrations/calendar/google/disconnect', {
    method: 'DELETE',
    token: token(),
  })
}
