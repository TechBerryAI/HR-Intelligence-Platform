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
  return apiRequest('/api/integrations/calendar/google/connect', {
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
