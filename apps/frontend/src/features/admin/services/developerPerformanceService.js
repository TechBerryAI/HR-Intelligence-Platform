/**
 * Admin Developer Mode — performance timing APIs.
 * HEAD_HR only; backend returns 404 when DEVELOPER_MODE is off.
 */
import { apiRequest, BASE_URL } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'

export async function fetchDeveloperStatus() {
  try {
    const data = await apiRequest('/api/admin/developer/status', { skipRetry: true })
    return {
      enabled: Boolean(data?.enabled),
      developerMode: Boolean(data?.developer_mode),
    }
  } catch {
    return { enabled: false, developerMode: false }
  }
}

export async function fetchPerformanceRecent(params = {}) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && String(v).trim() !== '') qs.set(k, String(v).trim())
  })
  const suffix = qs.toString() ? `?${qs}` : ''
  return apiRequest(`/api/admin/developer/performance/recent${suffix}`)
}

export async function fetchPerformanceRequest(requestId) {
  return apiRequest(`/api/admin/developer/performance/request/${encodeURIComponent(requestId)}`)
}

export async function fetchPerformanceStats(hours = 24) {
  return apiRequest(`/api/admin/developer/performance/stats?hours=${hours}`)
}

export function buildExportUrl(params = {}) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && String(v).trim() !== '') qs.set(k, String(v).trim())
  })
  const suffix = qs.toString() ? `?${qs}` : ''
  return `${BASE_URL}/api/admin/developer/performance/export${suffix}`
}

export async function downloadPerformanceCsv(params = {}) {
  const token = tokenService.getToken()
  const url = buildExportUrl(params)
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: 'include',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `Export failed (${res.status})`)
  }
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'performance-timings.csv'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(a.href)
}
