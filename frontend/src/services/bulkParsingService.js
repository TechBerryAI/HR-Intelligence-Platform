/**
 * Bulk Resume Parsing API - calls backend /api/admin/bulk-parse (proxy to Bulk-Resume-Parser).
 * Admin only; requires HR token.
 */
import { apiRequest } from '../utils/api.js'
import { tokenService } from '../utils/tokenService.js'

export async function uploadBulkResumes(files, append = false) {
  const form = new FormData()
  files.forEach((file) => form.append('files', file))
  if (append) form.append('append', 'true')
  return apiRequest('/api/admin/bulk-parse/upload', {
    method: 'POST',
    body: form,
    timeoutMs: 60000,
    skipRetry: true, // Do not retry on 502/503 — parsing service down
  })
}

export async function getBulkProgress(jobId) {
  return apiRequest(`/api/admin/bulk-parse/progress/${jobId}`)
}

/**
 * Returns URL for downloading Excel (same-origin; backend streams from Bulk-Resume-Parser).
 */
export function getBulkDownloadUrl(jobId) {
  const base = (import.meta.env?.VITE_API_URL || 'http://localhost:3000').replace(/\/$/, '')
  return `${base}/api/admin/bulk-parse/download/${jobId}`
}

/**
 * Download Excel file (requires token via apiRequest). Fetches blob and triggers download.
 */
export async function downloadBulkResult(jobId, filename = 'Parsed_Resumes.xlsx') {
  const base = (import.meta.env?.VITE_API_URL || 'http://localhost:3000').replace(/\/$/, '')
  const url = `${base}/api/admin/bulk-parse/download/${jobId}`
  const token = tokenService.getToken()
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: 'include',
  })
  if (!res.ok) throw new Error(res.statusText || 'Download failed')
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition')
  const match = disposition && disposition.match(/filename="?([^"]+)"?/)
  const name = match ? match[1] : filename
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
}
