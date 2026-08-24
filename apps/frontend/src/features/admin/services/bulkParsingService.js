/**
 * Bulk Resume Parsing API - chunked folder uploads + ZIP + progress/download.
 * Admin / Head HR; requires HR token.
 */
import { apiRequest, BASE_URL, tryRefresh } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'

export const BULK_UPLOAD_CHUNK_SIZE = 40
export const BULK_CHUNK_TIMEOUT_MS = 180000
export const BULK_POLL_INTERVAL_MS = 2000
export const BULK_JOB_STORAGE_KEY = 'bulkParseActiveJob'

export function saveBulkJobSession(jobId) {
  if (!jobId || typeof sessionStorage === 'undefined') return
  try {
    sessionStorage.setItem(
      BULK_JOB_STORAGE_KEY,
      JSON.stringify({ jobId, startedAt: Date.now() })
    )
  } catch {
    // ignore quota / private mode
  }
}

export function loadBulkJobSession() {
  if (typeof sessionStorage === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(BULK_JOB_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.jobId) return null
    return parsed
  } catch {
    return null
  }
}

export function clearBulkJobSession() {
  if (typeof sessionStorage === 'undefined') return
  try {
    sessionStorage.removeItem(BULK_JOB_STORAGE_KEY)
  } catch {
    // ignore
  }
}

export async function createBulkJob(append = false) {
  return apiRequest('/api/admin/bulk-parse/jobs', {
    method: 'POST',
    body: { append: !!append },
    skipRetry: true,
  })
}

/**
 * Upload one chunk of resume files to an existing job.
 * @param {string} jobId
 * @param {File[]} files
 * @param {{ append?: boolean, finalize?: boolean }} opts
 */
export async function uploadBulkChunk(jobId, files, opts = {}) {
  const form = new FormData()
  form.append('job_id', jobId)
  if (opts.append) form.append('append', 'true')
  if (opts.finalize) form.append('finalize', 'true')
  files.forEach((file) => form.append('files', file))
  return apiRequest('/api/admin/bulk-parse/upload', {
    method: 'POST',
    body: form,
    timeoutMs: BULK_CHUNK_TIMEOUT_MS,
    skipRetry: true,
  })
}

/**
 * Upload a ZIP archive to an existing job (server extracts PDF/DOC/DOCX).
 */
export async function uploadBulkZip(jobId, zipFile, opts = {}) {
  const form = new FormData()
  form.append('job_id', jobId)
  form.append('zip', zipFile, zipFile.name || 'resumes.zip')
  if (opts.append) form.append('append', 'true')
  if (opts.finalize) form.append('finalize', 'true')
  return apiRequest('/api/admin/bulk-parse/upload', {
    method: 'POST',
    body: form,
    timeoutMs: BULK_CHUNK_TIMEOUT_MS,
    skipRetry: true,
  })
}

export async function startBulkJob(jobId, append = false) {
  return apiRequest(`/api/admin/bulk-parse/start/${jobId}`, {
    method: 'POST',
    body: { append: !!append },
    skipRetry: true,
  })
}

/**
 * Create job, upload all files in chunks (or ZIP-only), then start parsing.
 * Prefer individual resumes when present — a ZIP sitting inside a browsed folder
 * must not replace thousands of PDF/DOC/DOCX files.
 * @param {File[]} files - resume files and/or zip archives
 * @param {boolean} append
 * @param {{ onProgress?: (msg: string) => void }} callbacks
 */
export async function uploadBulkResumes(files, append = false, callbacks = {}) {
  const onProgress = callbacks.onProgress || (() => {})
  const zipFiles = files.filter((f) => /\.zip$/i.test(f.name))
  const resumeFiles = files.filter((f) => /\.(pdf|docx?)$/i.test(f.name))

  if (!zipFiles.length && !resumeFiles.length) {
    const err = new Error('No valid resume files (PDF, DOC, DOCX) or ZIP')
    err.status = 400
    throw err
  }

  onProgress('Creating job…')
  const created = await createBulkJob(append)
  const jobId = created.job_id
  if (!jobId) {
    const err = new Error('Failed to create bulk parse job')
    err.status = 502
    throw err
  }

  try {
    if (resumeFiles.length > 0) {
      // Folder / multi-file selection: upload every resume in batches
      const totalChunks = Math.ceil(resumeFiles.length / BULK_UPLOAD_CHUNK_SIZE) || 1
      for (let i = 0; i < resumeFiles.length; i += BULK_UPLOAD_CHUNK_SIZE) {
        const chunk = resumeFiles.slice(i, i + BULK_UPLOAD_CHUNK_SIZE)
        const batchNum = Math.floor(i / BULK_UPLOAD_CHUNK_SIZE) + 1
        onProgress(`Uploading batch ${batchNum}/${totalChunks} (${chunk.length} files)…`)
        await uploadBulkChunk(jobId, chunk, { append, finalize: false })
      }
      if (zipFiles.length) {
        onProgress(
          `Skipped ${zipFiles.length} ZIP in the folder selection — resumes are uploaded directly. Use “Upload ZIP” for archive-only jobs.`
        )
      }
    } else {
      // ZIP-only selection (explicit Upload ZIP)
      for (let i = 0; i < zipFiles.length; i++) {
        const zip = zipFiles[i]
        onProgress(`Uploading ZIP ${i + 1}/${zipFiles.length}: ${zip.name}…`)
        await uploadBulkZip(jobId, zip, { append, finalize: false })
      }
    }

    onProgress('Starting parse…')
    const started = await startBulkJob(jobId, append)
    return {
      ...started,
      job_id: started.job_id || jobId,
    }
  } catch (e) {
    // Attach job_id so UI can still show partial state / clearer errors
    if (e && typeof e === 'object') e.jobId = jobId
    throw e
  }
}

/**
 * Progress poll — never triggers logout (skipAuthHandler).
 * Callers should handle 401/403 with tryRefresh + session banner.
 */
export async function getBulkProgress(jobId) {
  return apiRequest(`/api/admin/bulk-parse/progress/${jobId}`, {
    skipAuthHandler: true,
    skipRetry: true,
  })
}

/** Pause a running bulk job (finishes in-flight files, then stops). */
export async function pauseBulkJob(jobId) {
  return apiRequest(`/api/admin/bulk-parse/pause/${jobId}`, {
    method: 'POST',
  })
}

/** Resume a paused bulk job. */
export async function resumeBulkJob(jobId) {
  return apiRequest(`/api/admin/bulk-parse/resume/${jobId}`, {
    method: 'POST',
  })
}

/** Attempt one coordinated refresh after an auth-looking progress failure. */
export async function refreshForBulkPoll() {
  return tryRefresh()
}

/**
 * Returns URL for downloading Excel (same-origin; backend streams).
 */
export function getBulkDownloadUrl(jobId) {
  return `${BASE_URL}/api/admin/bulk-parse/download/${jobId}`
}

/**
 * Download Excel file (requires token via fetch). Fetches blob and triggers download.
 */
export async function downloadBulkResult(jobId, filename = 'Parsed_Resumes.xlsx') {
  const url = `${BASE_URL}/api/admin/bulk-parse/download/${jobId}`
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
