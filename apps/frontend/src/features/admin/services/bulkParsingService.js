/**
 * Bulk Resume Parsing API - chunked folder uploads + ZIP + progress/download.
 * Admin / Head HR; requires HR token.
 */
import { apiRequest, BASE_URL, tryRefresh, isSessionAuthError } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'

export const BULK_UPLOAD_CHUNK_SIZE = 40
export const BULK_CHUNK_TIMEOUT_MS = 180000
export const BULK_POLL_INTERVAL_MS = 2000
export const BULK_JOB_STORAGE_KEY = 'bulkParseActiveJob'

/**
 * Remember the active job for this tab so a reload / re-login can resume
 * watching it. `owner` (user id or email) scopes it: sessionStorage survives
 * logout + login as someone else, and that account would get 403 "Access
 * denied" polling a job it didn't start.
 */
export function saveBulkJobSession(jobId, owner = '') {
  if (!jobId || typeof sessionStorage === 'undefined') return
  try {
    sessionStorage.setItem(
      BULK_JOB_STORAGE_KEY,
      JSON.stringify({ jobId, owner: String(owner || ''), startedAt: Date.now() })
    )
  } catch {
    // ignore quota / private mode
  }
}

export function loadBulkJobSession(owner = '') {
  if (typeof sessionStorage === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(BULK_JOB_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.jobId) return null
    if (owner && parsed.owner && parsed.owner !== String(owner)) {
      sessionStorage.removeItem(BULK_JOB_STORAGE_KEY)
      return null
    }
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
  const resumeFiles = files.filter((f) => /\.(pdf|docx?|webp|tiff?)$/i.test(f.name))

  if (!zipFiles.length && !resumeFiles.length) {
    const err = new Error('No valid resume files (PDF, DOC, DOCX, WEBP, TIF) or ZIP')
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

const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/** .xlsx is a ZIP container — every valid workbook starts with "PK\x03\x04". */
async function isXlsxBlob(blob) {
  if (!blob || blob.size < 4) return false
  const head = new Uint8Array(await blob.slice(0, 4).arrayBuffer())
  return head[0] === 0x50 && head[1] === 0x4b && head[2] === 0x03 && head[3] === 0x04
}

/**
 * Fetch the finished Excel export as a validated Blob.
 * If the server is regenerating a missing export, poll until ready (or timeout).
 * @returns {Promise<{ blob: Blob, filename: string }>}
 */
export async function fetchBulkResultBlob(jobId, filename = 'Parsed_Resumes.xlsx') {
  const url = `${BASE_URL}/api/admin/bulk-parse/download/${jobId}`
  const maxAttempts = 90
  const waitMs = 5000
  let refreshed = false

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const token = tokenService.getToken()
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'include',
    })
    if (res.ok) {
      const blob = await res.blob()
      if (!(await isXlsxBlob(blob))) {
        const err = new Error('The server did not return a valid Excel file. Try Download again, or re-run the parse.')
        err.status = 502
        err.data = { error: err.message }
        throw err
      }
      const disposition = res.headers.get('Content-Disposition')
      const match = disposition && disposition.match(/filename="?([^"]+)"?/)
      return {
        blob: blob.type === XLSX_MIME ? blob : blob.slice(0, blob.size, XLSX_MIME),
        filename: match ? match[1] : filename,
      }
    }

    let message = res.statusText || 'Download failed'
    let code = ''
    try {
      const data = await res.json()
      if (data?.error) message = data.error
      if (data?.code) code = data.code
    } catch {
      // response was not JSON
    }

    if (isSessionAuthError(res.status, message) && !refreshed) {
      refreshed = true
      await tryRefresh()
      continue
    }

    if (res.status === 202 || code === 'EXPORT_REGENERATING') {
      if (attempt < maxAttempts - 1) {
        await new Promise((r) => setTimeout(r, waitMs))
        continue
      }
      const err = new Error(
        message || 'Excel export is still regenerating. Wait a minute and try Download again.'
      )
      err.status = 202
      err.data = { error: message, code: 'EXPORT_REGENERATING' }
      throw err
    }

    if (res.status === 502 || res.status === 503) {
      const err = new Error(
        message === 'Service Unavailable' || /unavailable/i.test(message)
          ? 'Download failed. The Excel export may still be writing — wait a moment and try again, or re-run the parse.'
          : message
      )
      err.status = res.status
      err.data = { error: message }
      throw err
    }
    const err = new Error(message)
    err.status = res.status
    err.data = { error: message, code }
    throw err
  }
  const err = new Error('Download failed')
  err.status = 0
  throw err
}

/** Hand a Blob to the browser's normal download flow. */
export function saveBlobAsDownload(blob, filename) {
  const href = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  a.rel = 'noopener'
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  a.remove()
  // Revoking synchronously can cancel the download before the browser reads the blob.
  setTimeout(() => URL.revokeObjectURL(href), 60000)
}

/**
 * Write the workbook to the output the user picked in step 2.
 * - `fileHandle`: FileSystemFileHandle from showSaveFilePicker (browser)
 * - `dirHandle`: FileSystemDirectoryHandle from showDirectoryPicker (browser)
 * - `path`: absolute file or folder path (Electron desktop only)
 * The browser picker creates an empty placeholder file immediately, so this
 * must run or the user is left with a 0-byte .xlsx Excel refuses to open.
 * @returns {Promise<string>} human-readable location written
 */
export async function writeBulkResultToOutput(
  blob,
  target,
  filename = 'Parsed_Resumes.xlsx',
  { interactive = true } = {}
) {
  if (target?.fileHandle) {
    await ensureOutputWritable(target, { interactive })
    const writable = await target.fileHandle.createWritable()
    try {
      await writable.write(blob)
      await writable.close()
    } catch (e) {
      try { await writable.abort() } catch { /* ignore */ }
      throw e
    }
    return target.fileHandle.name
  }
  if (target?.dirHandle) {
    await ensureOutputWritable(target, { interactive })
    const fileHandle = await target.dirHandle.getFileHandle(filename, { create: true })
    await writeBulkResultToOutput(blob, { fileHandle }, filename, { interactive })
    return `${target.dirHandle.name}/${filename}`
  }
  const electron = typeof window !== 'undefined' && window.electron
  if (target?.path && electron?.writeFile) {
    const written = await electron.writeFile(target.path, await blob.arrayBuffer(), {
      isFolder: !!target.isFolder,
      defaultName: filename,
    })
    return written || target.path
  }
  throw new Error('No writable output location selected.')
}

/**
 * Make sure the browser lets us write to a picked file/folder handle.
 * A handle restored after a reload usually comes back as 'prompt', and the
 * browser only shows that prompt from a click — so automatic saves pass
 * `interactive: false` and get a PERMISSION_REQUIRED error to surface as a
 * "Save to …" button instead.
 */
export async function ensureOutputWritable(target, { interactive = true } = {}) {
  const handle = target?.fileHandle || target?.dirHandle
  if (typeof handle?.queryPermission !== 'function') return
  const opts = { mode: 'readwrite' }
  if ((await handle.queryPermission(opts)) === 'granted') return
  if (interactive && (await handle.requestPermission(opts)) === 'granted') return
  const err = new Error(
    interactive
      ? 'Permission to write the output file was denied.'
      : 'The browser needs your permission again to write the output file.'
  )
  err.name = 'NotAllowedError'
  err.code = interactive ? 'PERMISSION_DENIED' : 'PERMISSION_REQUIRED'
  throw err
}

// ---------------------------------------------------------------------------
// Output target persistence. A file/folder handle lives only in page memory,
// so a reload or leaving the page mid-parse used to lose it — and the 0-byte
// file the save picker had already created was never filled. Handles (and the
// Electron path objects) are structured-cloneable, so they go to IndexedDB.
// ---------------------------------------------------------------------------
const OUTPUT_DB = 'bulkParseOutput'
const OUTPUT_STORE = 'targets'
const OUTPUT_KEY = 'active'

function openOutputDb() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'))
      return
    }
    const req = indexedDB.open(OUTPUT_DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(OUTPUT_STORE)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function withOutputStore(mode, fn) {
  const db = await openOutputDb()
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(OUTPUT_STORE, mode)
      const req = fn(tx.objectStore(OUTPUT_STORE))
      tx.oncomplete = () => resolve(req?.result)
      tx.onerror = () => reject(tx.error)
      tx.onabort = () => reject(tx.error)
    })
  } finally {
    db.close()
  }
}

/** Remember where job `jobId`'s workbook should be written (survives reloads). */
export async function saveBulkOutputTarget(jobId, owner, target, display = '') {
  if (!jobId || !target) return
  try {
    await withOutputStore('readwrite', (store) =>
      store.put({ jobId, owner: String(owner || ''), target, display }, OUTPUT_KEY)
    )
  } catch {
    // Private mode / storage blocked — fall back to in-memory only.
  }
}

/** @returns {Promise<{ target: object, display: string } | null>} */
export async function loadBulkOutputTarget(jobId, owner) {
  if (!jobId) return null
  try {
    const rec = await withOutputStore('readonly', (store) => store.get(OUTPUT_KEY))
    if (!rec || rec.jobId !== jobId) return null
    if (owner && rec.owner && rec.owner !== String(owner)) return null
    return { target: rec.target, display: rec.display || '' }
  } catch {
    return null
  }
}

export async function clearBulkOutputTarget() {
  try {
    await withOutputStore('readwrite', (store) => store.delete(OUTPUT_KEY))
  } catch {
    // ignore
  }
}

/** Fetch the Excel export and save it via the browser's download flow. */
export async function downloadBulkResult(jobId, filename = 'Parsed_Resumes.xlsx') {
  const { blob, filename: name } = await fetchBulkResultBlob(jobId, filename)
  saveBlobAsDownload(blob, name)
}
