/**
 * Admin-only: Bulk Resume Parsing. Select Folders + File Processing Status.
 * Styled to match enterprise org panel (glass + blue accent).
 */
import React, { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  FiFolder,
  FiHardDrive,
  FiUpload,
  FiDownload,
  FiCheck,
  FiX,
  FiLoader,
  FiChevronDown,
  FiFileText,
  FiAlertCircle,
  FiRefreshCw,
  FiClock,
  FiCheckCircle,
  FiAlertTriangle,
  FiFolderPlus,
  FiPause,
  FiPlay,
} from 'react-icons/fi'
import { Layers } from 'lucide-react'
import {
  uploadBulkResumes,
  getBulkProgress,
  fetchBulkResultBlob,
  saveBlobAsDownload,
  writeBulkResultToOutput,
  ensureOutputWritable,
  saveBulkOutputTarget,
  loadBulkOutputTarget,
  clearBulkOutputTarget,
  saveBulkJobSession,
  loadBulkJobSession,
  pauseBulkJob,
  resumeBulkJob,
  clearBulkJobSession,
  refreshForBulkPoll,
  BULK_POLL_INTERVAL_MS,
} from '@/features/admin/services/bulkParsingService.js'
import { isSessionAuthError } from '@/core/api/api.js'
import { useApp } from '@/core/context/AppContext.jsx'

const RESUME_EXT = ['pdf', 'docx', 'doc', 'webp', 'tif', 'tiff']
const OUTPUT_FILENAME = 'Parsed_Resumes.xlsx'
/** Consecutive "Job not found" polls before the saved job is dropped (survives a brief cold start). */
const JOB_GONE_POLL_LIMIT = 3

/** The login itself is no longer valid (vs. a permission answer for this job). */
function isAuthPollError(err) {
  return isSessionAuthError(err?.status, err?.data?.error || err?.message)
}

/** The job belongs to another account (403 Access denied) or no longer exists (404). */
function isJobUnavailableError(err) {
  return (err?.status === 403 && !isAuthPollError(err)) || err?.status === 404
}

/** False-positive from optional external bulk parser (port 8001) — ignore when local job finished. */
function isStaleBulkServiceError(message) {
  return /service unavailable|bulk parsing service unavailable|BULK_PARSER_UNREACHABLE|BULK_PARSER_NOT_CONFIGURED/i.test(
    String(message || '')
  )
}

export default function BulkResumeParser({ embedded = false }) {
  const { user, auth } = useApp()
  const owner = user?.hrId || auth?.email || ''
  const [inputFolderPath, setInputFolderPath] = useState('')
  const [inputFolderFound, setInputFolderFound] = useState(false)
  const [outputType, setOutputType] = useState('file')
  const [outputPath, setOutputPath] = useState('')
  const [outputFolderFound, setOutputFolderFound] = useState(false)

  const [files, setFiles] = useState([])
  const [append, setAppend] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState('')
  const [downloading, setDownloading] = useState(false)
  const [pausing, setPausing] = useState(false)
  const [resuming, setResuming] = useState(false)
  /** Explicit control state so Pause/Resume buttons don't flicker on stale polls. */
  const [runControl, setRunControl] = useState(null) // 'running' | 'paused' | null
  const ignorePausedUntilRef = useRef(0)
  const [instructionsOpen, setInstructionsOpen] = useState(false)
  const [sessionExpired, setSessionExpired] = useState(false)
  const [listFilter, setListFilter] = useState('all') // all | processed | failed | queued
  const [savedTo, setSavedTo] = useState('')
  const [saveError, setSaveError] = useState('')
  const [savingOutput, setSavingOutput] = useState(false)
  /** Where step 2 points: { fileHandle } | { dirHandle } (browser) or { path, isFolder } (Electron). */
  const outputTargetRef = useRef(null)
  /** jobId whose workbook has already been written to the output target. */
  const savedJobRef = useRef(null)
  /** Bumped whenever outputTargetRef changes so the auto-save effect re-checks. */
  const [outputTargetVersion, setOutputTargetVersion] = useState(0)
  /** A restored file handle needs a click before the browser lets us write again. */
  const [needsSavePermission, setNeedsSavePermission] = useState(false)

  const folderInputRef = useRef(null)
  const zipInputRef = useRef(null)
  const restoredRef = useRef(false)

  const b64ToFile = (name, b64) => {
    const bin = atob(b64)
    const arr = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i)
    return new File([arr], name)
  }

  const addFiles = (list, { allowZip = false } = {}) => {
    const valid = Array.from(list).filter((f) => {
      const ext = (f.name.split('.').pop() || '').toLowerCase()
      if (allowZip) return ext === 'zip'
      return RESUME_EXT.includes(ext)
    })
    // Keep subfolder path in the filename so nested duplicates stay distinct when uploaded
    const named = valid.map((f) => {
      const rel = (f.webkitRelativePath || '').replace(/\\/g, '/')
      if (!rel || !rel.includes('/')) return f
      const flat = rel.split('/').filter(Boolean).join('__')
      return flat && flat !== f.name ? new File([f], flat, { type: f.type || 'application/octet-stream' }) : f
    })
    if (named.length) {
      setFiles((prev) => [...prev, ...named])
      const first = valid[0]
      const folderName = first.webkitRelativePath ? first.webkitRelativePath.split('/')[0] : ''
      setInputFolderPath(folderName || (allowZip ? first.name : 'Selected folder'))
      setInputFolderFound(true)
    }
    setError(null)
  }

  /**
   * Point step 2 at a new output. While a job is running it is also persisted,
   * so a reload / leaving the page mid-parse can still fill the file once the
   * job completes.
   */
  const setOutputTarget = (target, display = '') => {
    outputTargetRef.current = target
    setOutputTargetVersion((v) => v + 1)
    setNeedsSavePermission(false)
    if (!jobId) return
    if (target) saveBulkOutputTarget(jobId, owner, target, display)
    else clearBulkOutputTarget()
  }

  const handleInputFolderBrowse = async () => {
    const electron = typeof window !== 'undefined' && window.electron
    if (electron?.selectInputFolder) {
      try {
        const result = await electron.selectInputFolder()
        if (!result?.folderPath) return
        const fileList = (result.files || []).map(({ name, data }) => b64ToFile(name, data))
        if (fileList.length) {
          setFiles((prev) => [...prev, ...fileList])
          setInputFolderPath(result.folderPath)
          setInputFolderFound(true)
          setError(null)
        } else {
          setError('No PDF, DOC/DOCX, or supported image files found in that folder.')
        }
      } catch (err) {
        setError(err?.message || 'Could not read folder.')
      }
      return
    }
    folderInputRef.current?.click()
  }

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
    if (files.length <= 1) {
      setInputFolderPath('')
      setInputFolderFound(false)
    }
  }

  const handleOutputBrowse = async () => {
    try {
      // Prefer Electron dialogs when running as desktop app — no browser restrictions (full access to any folder/file)
      const electron = typeof window !== 'undefined' && window.electron
      if (outputType === 'folder') {
        if (electron?.selectFolder) {
          const fullPath = await electron.selectFolder()
          if (fullPath) {
            setOutputTarget({ path: fullPath, isFolder: true }, fullPath)
            setOutputPath(fullPath)
            setOutputFolderFound(true)
            setError(null)
          }
          return
        }
        if (typeof window.showDirectoryPicker !== 'function') {
          setError('Folder picker is not supported in this browser. Run the app in Electron for full folder access.')
          return
        }
        const dirHandle = await window.showDirectoryPicker({ startIn: 'downloads', mode: 'readwrite' })
        setOutputTarget({ dirHandle }, dirHandle.name)
        setOutputPath(dirHandle.name)
        setOutputFolderFound(true)
        setError(null)
      } else {
        if (electron?.selectSaveFile) {
          const fullPath = await electron.selectSaveFile(OUTPUT_FILENAME)
          if (fullPath) {
            setOutputTarget({ path: fullPath, isFolder: false }, fullPath)
            setOutputPath(fullPath)
            setOutputFolderFound(true)
            setError(null)
          }
          return
        }
        if (typeof window.showSaveFilePicker !== 'function') {
          setError('Save file picker is not supported in this browser. Run the app in Electron for full file access.')
          return
        }
        // The browser creates this file (0 bytes) right away — the completed
        // workbook is written into it through outputTargetRef once parsing ends.
        const fileHandle = await window.showSaveFilePicker({
          suggestedName: OUTPUT_FILENAME,
          types: [
            {
              description: 'Excel workbook',
              accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
            },
          ],
        })
        setOutputTarget({ fileHandle }, fileHandle.name)
        setOutputPath(fileHandle.name)
        setOutputFolderFound(true)
        setError(null)
      }
    } catch (err) {
      if (err.name === 'AbortError') return
      const msg = err?.message || ''
      const isSystemFiles = msg.toLowerCase().includes('system files')
      const isSecurity = err.name === 'SecurityError' || isSystemFiles
      if (isSecurity || isSystemFiles) {
        setError(
          "That folder can't be used in the browser (restriction). Run the app as a desktop app (Electron) to access any folder — see README."
        )
      } else {
        setError(msg || 'Could not open picker. Try entering the path manually.')
      }
    }
  }

  const startUpload = async () => {
    if (!files.length) {
      setError('Select at least one file (PDF, DOCX, DOC, WEBP, TIF/TIFF) or a ZIP archive.')
      return
    }
    setError(null)
    setSessionExpired(false)
    setUploading(true)
    setUploadStatus('Preparing upload…')
    setJobId(null)
    setProgress(null)
    setRunControl(null)
    setSavedTo('')
    setSaveError('')
    savedJobRef.current = null
    ignorePausedUntilRef.current = 0
    clearBulkJobSession()
    try {
      const res = await uploadBulkResumes(files, append, {
        onProgress: (msg) => setUploadStatus(msg),
      })
      setJobId(res.job_id)
      saveBulkJobSession(res.job_id, owner)
      if (outputTargetRef.current) saveBulkOutputTarget(res.job_id, owner, outputTargetRef.current, outputPath)
      else clearBulkOutputTarget()
      setUploadStatus('')
      setRunControl('running')
      setProgress({
        status: res.status || 'started',
        total_files: res.total_files || files.filter((f) => !/\.zip$/i.test(f.name)).length,
        processed_files: 0,
        failed_files: 0,
        message: res.message || 'Processing started',
        failed_details: [],
      })
    } catch (e) {
      const status = e?.status
      const code = e?.data?.code
      const msg = e?.data?.error || e?.message
      setJobId(null)
      setProgress(null)
      setRunControl(null)
      clearBulkJobSession()
      if (status === 413) {
        setError(
          'Upload was rejected as too large (413). Files are uploaded in batches automatically — try again, or upload a ZIP of resumes instead.'
        )
      } else if (status === 502 || status === 503 || code === 'BULK_PARSER_UNREACHABLE' || code === 'BULK_PARSER_NOT_CONFIGURED') {
        setError(msg || 'Bulk parsing service unavailable. Ensure the parsing service is running (see README).')
      } else if (/timeout|abort|network/i.test(String(msg || ''))) {
        setError(msg || 'Upload timed out or lost connection. Try a ZIP upload or fewer files per batch.')
      } else {
        setError(msg || 'Upload failed')
      }
    } finally {
      setUploading(false)
      setUploadStatus('')
    }
  }

  // Restore job after re-login / reload / remount.
  // restoredRef flips only once a restore has actually been applied: the lazy
  // route's Suspense boundary can disconnect and reconnect this effect on the
  // same instance right after mount, and the first (cancelled) run must not
  // block the reconnected one — that left the page "Idle" after every reload.
  useEffect(() => {
    if (restoredRef.current) return
    const saved = loadBulkJobSession(owner)
    if (!saved?.jobId) {
      restoredRef.current = true
      return
    }
    let cancelled = false
    ;(async () => {
      // Bring back the step-2 output picked before the reload, so the
      // workbook can still be written there when this job completes.
      const restored = await loadBulkOutputTarget(saved.jobId, owner)
      if (!cancelled && restored?.target && !outputTargetRef.current) {
        const t = restored.target
        outputTargetRef.current = t
        setOutputTargetVersion((v) => v + 1)
        setOutputType(t.dirHandle || t.isFolder ? 'folder' : 'file')
        setOutputPath(restored.display || t.fileHandle?.name || t.dirHandle?.name || t.path || '')
        setOutputFolderFound(true)
      }
      try {
        let data
        try {
          data = await getBulkProgress(saved.jobId)
        } catch (err) {
          if (!isAuthPollError(err) || !(await refreshForBulkPoll())) throw err
          data = await getBulkProgress(saved.jobId)
        }
        if (cancelled) return
        restoredRef.current = true
        const st = data?.status
        if (st === 'started' || st === 'pending' || st === 'paused' || st === 'completed' || st === 'failed') {
          setJobId(saved.jobId)
          setProgress(data)
          setSessionExpired(false)
          if (st === 'completed' || st === 'failed') {
            setError((prev) => (isStaleBulkServiceError(prev) ? null : prev))
          }
          if (st === 'paused') setRunControl('paused')
          else if (st === 'started' || st === 'pending') setRunControl('running')
          else setRunControl(null)
        } else {
          clearBulkJobSession()
        }
      } catch (err) {
        if (cancelled) return
        restoredRef.current = true
        if (isJobUnavailableError(err)) {
          // Started by another account in this tab, or long gone — not ours to watch.
          clearBulkJobSession()
          clearBulkOutputTarget()
          outputTargetRef.current = null
          setOutputPath('')
          setOutputFolderFound(false)
        } else if (isAuthPollError(err)) {
          setJobId(saved.jobId)
          setSessionExpired(true)
        } else {
          // Job may still exist after cold start — keep id and let poll retry
          setJobId(saved.jobId)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  // Chained 2s polling — await previous poll; never logout from poll failures
  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    let timer = null
    let goneCount = 0

    const schedule = (ms) => {
      if (cancelled) return
      timer = setTimeout(runPoll, ms)
    }

    const runPoll = async () => {
      try {
        const data = await getBulkProgress(jobId)
        if (cancelled) return
        const status = data?.status
        // After Resume, ignore one or more stale "paused" responses from in-flight polls.
        if (status === 'paused' && Date.now() < ignorePausedUntilRef.current) {
          schedule(BULK_POLL_INTERVAL_MS)
          return
        }
        goneCount = 0
        setProgress(data)
        setSessionExpired(false)
        if (status === 'started' || status === 'pending') {
          setRunControl('running')
          ignorePausedUntilRef.current = 0
        } else if (status === 'paused') {
          setRunControl('paused')
        } else if (status === 'completed' || status === 'failed' || status === 'cancelled') {
          setRunControl(null)
          ignorePausedUntilRef.current = 0
          setError((prev) => (isStaleBulkServiceError(prev) ? null : prev))
        }
        if (status === 'completed' || status === 'failed') {
          return
        }
        schedule(BULK_POLL_INTERVAL_MS)
      } catch (err) {
        if (cancelled) return
        if (isAuthPollError(err)) {
          const refreshed = await refreshForBulkPoll()
          if (cancelled) return
          if (refreshed) {
            schedule(BULK_POLL_INTERVAL_MS)
            return
          }
          setSessionExpired(true)
          // Keep jobId / sessionStorage; retry slowly until user re-logs in
          schedule(BULK_POLL_INTERVAL_MS * 5)
          return
        }
        if (isJobUnavailableError(err)) {
          goneCount += err?.status === 403 ? JOB_GONE_POLL_LIMIT : 1
          if (goneCount >= JOB_GONE_POLL_LIMIT) {
            clearBulkJobSession()
            clearBulkOutputTarget()
            setJobId(null)
            setProgress(null)
            setRunControl(null)
            setSessionExpired(false)
            setError(
              err?.status === 403
                ? 'That bulk job was started by another account. Start a new job to parse resumes.'
                : 'That bulk job no longer exists on the server. Start a new job to parse resumes.'
            )
            return
          }
        }
        schedule(BULK_POLL_INTERVAL_MS)
      }
    }

    runPoll()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [jobId])

  /** Write the finished workbook to the step-2 output (browser handle or Electron path). */
  const saveToOutput = async (id, fetched, { interactive = true } = {}) => {
    const target = outputTargetRef.current
    if (!id || !target) return false
    setSavingOutput(true)
    setSaveError('')
    try {
      // Permission first: a click's user activation expires while the
      // workbook downloads, and the browser only prompts during one.
      await ensureOutputWritable(target, { interactive })
      const { blob } = fetched || (await fetchBulkResultBlob(id, OUTPUT_FILENAME))
      const where = await writeBulkResultToOutput(blob, target, OUTPUT_FILENAME, { interactive })
      savedJobRef.current = id
      setSavedTo(where)
      setNeedsSavePermission(false)
      // Written — nothing left for a later reload to resume.
      clearBulkOutputTarget()
      return true
    } catch (e) {
      if (e?.data?.code === 'EXPORT_REGENERATING' || e?.status === 202) throw e
      if (e?.code === 'PERMISSION_REQUIRED') {
        savedJobRef.current = null
        setNeedsSavePermission(true)
        return false
      }
      setSaveError(
        `Could not save to ${outputPath || 'the selected output'}: ${e?.message || 'write failed'}. Use Download Excel instead.`
      )
      return false
    } finally {
      setSavingOutput(false)
    }
  }

  // Once parsing completes, write the workbook to the chosen output. The
  // browser save picker already created an empty placeholder file there, so
  // skipping this leaves a 0-byte .xlsx that Excel refuses to open.
  useEffect(() => {
    if (progress?.status !== 'completed' || !jobId) return
    if (!outputTargetRef.current || savedJobRef.current === jobId) return
    savedJobRef.current = jobId
    saveToOutput(jobId, null, { interactive: false }).catch(() => {
      // Export still regenerating — leave it to Download Excel to retry.
      savedJobRef.current = null
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [progress?.status, jobId, outputTargetVersion])

  /** "Save to <file>" — the click lets the browser re-grant write access after a reload. */
  const handleSaveToOutput = async () => {
    if (!jobId || savingOutput) return
    try {
      await saveToOutput(jobId)
    } catch (e) {
      setError(e?.data?.error || e?.message || 'Excel export is still being prepared — try again shortly.')
    }
  }

  const handleDownload = async () => {
    if (!jobId || (progress?.status !== 'completed' && progress?.status !== 'started')) return
    // Allow download while regenerating (server returns 202 until Excel is ready)
    if (progress?.status === 'started' && !/regenerat/i.test(String(progress?.message || ''))) {
      return
    }
    setDownloading(true)
    setError(null)
    try {
      // Ask for output write access while this click's activation is still live.
      if (outputTargetRef.current && savedJobRef.current !== jobId) {
        await ensureOutputWritable(outputTargetRef.current).catch(() => {})
      }
      const fetched = await fetchBulkResultBlob(jobId, OUTPUT_FILENAME)
      saveBlobAsDownload(fetched.blob, fetched.filename)
      // Also fill the step-2 output if the automatic save hasn't landed there yet.
      if (outputTargetRef.current && savedJobRef.current !== jobId) {
        await saveToOutput(jobId, fetched)
      }
      setError(null)
    } catch (e) {
      const raw = e?.data?.error || e?.message || 'Download failed'
      if (e?.data?.code === 'EXPORT_REGENERATING' || e?.status === 202) {
        setError(raw)
        setProgress((prev) => ({
          ...(prev || {}),
          status: 'started',
          message: raw,
        }))
        setRunControl('running')
      } else if (isStaleBulkServiceError(raw)) {
        setError(
          'Excel export is missing for this completed job. Re-run bulk parse to regenerate the download.'
        )
      } else {
        setError(raw)
      }
    } finally {
      setDownloading(false)
    }
  }

  const handlePause = async () => {
    if (!jobId || pausing || resuming) return
    setPausing(true)
    setError(null)
    setRunControl('paused')
    try {
      const data = await pauseBulkJob(jobId)
      setProgress((prev) => ({
        ...(prev || {}),
        ...(data || {}),
        status: 'paused',
        message: data?.message || 'Paused',
      }))
    } catch (e) {
      setRunControl('running')
      setError(e?.message || 'Failed to pause parsing')
    } finally {
      setPausing(false)
    }
  }

  const handleResume = async () => {
    if (!jobId || resuming || pausing) return
    setResuming(true)
    setError(null)
    setRunControl('running')
    ignorePausedUntilRef.current = Date.now() + 15000
    setProgress((prev) => ({
      ...(prev || {}),
      status: 'started',
      message: 'Resuming…',
    }))
    try {
      const data = await resumeBulkJob(jobId)
      setProgress((prev) => ({
        ...(prev || {}),
        ...(data || {}),
        status: data?.status === 'paused' ? 'started' : (data?.status || 'started'),
        message: data?.message || 'Resuming…',
      }))
      setRunControl('running')
      // Keep ignoring stale paused polls a bit longer after a successful resume.
      ignorePausedUntilRef.current = Date.now() + 15000
    } catch (e) {
      ignorePausedUntilRef.current = 0
      setRunControl('paused')
      setProgress((prev) => ({
        ...(prev || {}),
        status: 'paused',
      }))
      setError(e?.message || 'Failed to resume parsing')
    } finally {
      setResuming(false)
    }
  }

  const reset = () => {
    clearBulkJobSession()
    setJobId(null)
    setProgress(null)
    setFiles([])
    setError(null)
    setUploadStatus('')
    setSessionExpired(false)
    setSavedTo('')
    setSaveError('')
    setNeedsSavePermission(false)
    savedJobRef.current = null
    clearBulkOutputTarget()
    setListFilter('all')
    setInputFolderPath('')
    setInputFolderFound(false)
    setRunControl(null)
    ignorePausedUntilRef.current = 0
  }

  // Always drop false "service unavailable" once the local job is terminal
  // (poll may already have stopped, so render-time + effect both clear it).
  useEffect(() => {
    const st = progress?.status
    if (st !== 'completed' && st !== 'failed' && st !== 'cancelled') return
    setError((prev) => (isStaleBulkServiceError(prev) ? null : prev))
  }, [progress?.status])

  // When export rebuild starts, clear the old "export is missing" nag
  useEffect(() => {
    if (!/regenerat/i.test(String(progress?.message || ''))) return
    setError((prev) =>
      prev && /excel export is missing|re-run bulk parse/i.test(String(prev)) ? null : prev
    )
  }, [progress?.message])

  const resumeFiles = files.filter((f) => /\.(pdf|docx|doc|webp|tif|tiff)$/i.test(f.name))
  const zipSelected = files.some((f) => /\.zip$/i.test(f.name))
  // Only treat files as "in queue" when a real job is running — avoids fake stuck UI after failed upload
  const total = progress?.total_files ?? (jobId ? resumeFiles.length : 0)
  const processed = progress?.processed_files ?? 0
  const failed = progress?.failed_files ?? 0
  const failedDetails = progress?.failed_details ?? progress?.failedDetails ?? []
  const terminalJob =
    progress?.status === 'completed' ||
    progress?.status === 'failed' ||
    progress?.status === 'cancelled'
  const displayError =
    error && !(terminalJob && isStaleBulkServiceError(error)) ? error : null
  const failedFilenames =
    failedDetails.length > 0
      ? failedDetails.map((d) => d.filename || d.name).filter(Boolean)
      : progress?.failed_filenames ?? progress?.failedFilenames ?? []
  const successFilenames = progress?.success_filenames ?? progress?.successFilenames ?? []
  const queuedFilenames = progress?.queued_filenames ?? progress?.queuedFilenames ?? []
  const hasDetailedLists = successFilenames.length > 0 || failedFilenames.length > 0 || failedDetails.length > 0
  const failedCount = failedDetails.length || failedFilenames.length || failed
  const processingCount = jobId ? Math.max(0, queuedFilenames.length || total - processed) : 0
  const progressPct = total ? Math.round((processed / total) * 100) : 0
  const isPaused =
    runControl === 'paused' ||
    (runControl == null && progress?.status === 'paused')
  const isRunning =
    !isPaused &&
    (runControl === 'running' ||
      progress?.status === 'started' ||
      progress?.status === 'pending' ||
      (!progress?.status && jobId && processingCount > 0 && progress?.status !== 'completed' && progress?.status !== 'failed'))
  const currentFile =
    queuedFilenames[0] ||
    progress?.message?.replace(/^Processing:\s*/i, '').trim() ||
    (jobId ? resumeFiles[processed]?.name ?? '' : '')
  const inProgressFilenames = !jobId
    ? []
    : progress?.status === 'completed' || progress?.status === 'failed'
      ? []
      : queuedFilenames.length
        ? queuedFilenames
        : hasDetailedLists && resumeFiles.length
          ? resumeFiles.map((f) => f.name).filter((name) => !successFilenames.includes(name) && !failedFilenames.includes(name))
          : resumeFiles.slice(processed).map((f) => f.name)
  const processedDisplayNames = hasDetailedLists
    ? successFilenames
    : jobId
      ? resumeFiles.slice(0, processed).map((f) => f.name)
      : []

  const failedEntries =
    failedDetails.length > 0
      ? failedDetails.map((d) => ({
          name: d.filename || d.name || 'Unknown',
          error: d.error || d.message || '',
          code: d.code || '',
        }))
      : failedFilenames.map((name) => ({ name, error: '', code: '' }))

  const showProcessedList = listFilter === 'all' || listFilter === 'processed'
  const showQueuedList = listFilter === 'all' || listFilter === 'queued'
  const showFailedList = listFilter === 'all' || listFilter === 'failed'

  const statusLabel =
    progress?.status === 'completed'
      ? 'Completed'
      : progress?.status === 'failed'
        ? 'Failed'
        : uploading
          ? 'Uploading'
          : jobId
            ? 'Processing'
            : files.length
              ? 'Ready'
              : 'Idle'

  const statusDot =
    progress?.status === 'completed'
      ? 'bg-[var(--ei-accent-green)]'
      : progress?.status === 'failed'
        ? 'bg-[var(--ei-accent-red)]'
        : uploading || jobId
          ? 'bg-[var(--ei-accent-blue)] animate-pulse'
          : files.length
            ? 'bg-[var(--ei-accent-teal)]'
            : 'bg-[var(--ei-text-muted)]'

  const pathInputClass =
    'w-full min-w-0 px-3.5 py-2.5 rounded-xl bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] text-[var(--ei-text-primary)] text-sm placeholder:text-[var(--ei-text-placeholder)] focus:outline-none focus:border-[var(--ei-border-focus)] transition-colors'

  const metrics = [
    { label: 'Selected', value: files.length, icon: FiFileText, accent: 'rgba(156,168,181,0.14)', color: '#9CA8B5' },
    { label: 'Processed', value: processedDisplayNames.length, icon: FiCheckCircle, accent: 'rgba(54,214,160,0.14)', color: '#36D6A0' },
    { label: 'In queue', value: inProgressFilenames.length, icon: FiClock, accent: 'rgba(0,166,255,0.14)', color: '#00A6FF' },
    { label: 'Failed', value: failedCount, icon: FiAlertTriangle, accent: 'rgba(255,102,133,0.14)', color: '#FF6685' },
  ]

  const hasFiles = files.length > 0
  const showStatusLists = (hasFiles && jobId) || jobId || uploading

  return (
    <div
      className={embedded ? 'text-[var(--ei-text-primary)]' : 'text-[var(--ei-text-primary)]'}
    >
      <div className={embedded ? 'w-full max-w-5xl' : 'max-w-5xl mx-auto px-6 py-10'}>
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              {!embedded && (
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ei-text-muted)] mb-1">
                  Recruiter workspace
                </p>
              )}
              <h1 className="org-page-title flex items-center gap-2.5">
                <Layers size={32} className="org-page-icon" />
                Bulk Parsing
              </h1>
              <p className="org-page-subtitle">
                Select resumes, choose an output path, then parse to Excel
              </p>
            </div>
            <div className="org-account-pill self-center">
              <span className={`w-1.5 h-1.5 rounded-full ${statusDot}`} />
              {statusLabel}
            </div>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
            {metrics.map((m) => {
              const Icon = m.icon
              return (
                <div
                  key={m.label}
                  className="org-glass-card hover:transform-none px-3.5 py-3 flex items-center gap-3"
                >
                  <div
                    className="w-9 h-9 rounded-xl grid place-items-center flex-shrink-0"
                    style={{ background: m.accent, color: m.color }}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xl font-bold tabular-nums leading-none text-[var(--ei-text-primary)]">{m.value}</p>
                    <p className="text-[11px] mt-1 text-[var(--ei-text-muted)] truncate">{m.label}</p>
                  </div>
                </div>
              )
            })}
          </div>

          {sessionExpired && (
            <div className="org-error-banner flex items-start gap-2 border-[rgba(255,180,80,0.35)] bg-[rgba(255,180,80,0.1)]">
              <FiAlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-400" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--ei-text-primary)]">Session expired</p>
                <p className="text-xs text-[var(--ei-text-muted)] mt-0.5">
                  Your login expired while parsing. The job is still running — sign in again to keep watching progress. Job ID is kept until you start a new job.
                </p>
                <Link
                  to="/login/admin"
                  className="inline-flex items-center gap-1.5 mt-2 text-xs font-semibold text-[var(--ei-accent-blue)] hover:underline"
                >
                  Go to login
                </Link>
              </div>
            </div>
          )}

          {displayError && (
            <div className="org-error-banner flex items-start gap-2">
              <FiAlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span className="flex-1 min-w-0">{displayError}</span>
              <button
                type="button"
                onClick={() => setError(null)}
                className="shrink-0 text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)] p-0.5"
                aria-label="Dismiss error"
              >
                <FiX className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Main workspace */}
          <section className="org-glass-card hover:transform-none overflow-hidden">
            {/* Step rail */}
            <div className="px-5 sm:px-6 py-3.5 border-b border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)]">
              <div className="flex items-center gap-2 sm:gap-3 text-xs sm:text-sm flex-wrap">
                {[
                  { n: 1, label: 'Select resumes', done: hasFiles },
                  { n: 2, label: 'Set output', done: !!outputPath.trim() },
                  { n: 3, label: 'Parse', done: progress?.status === 'completed' },
                ].map((step, idx) => (
                  <React.Fragment key={step.n}>
                    {idx > 0 && <span className="hidden sm:block w-6 h-px bg-[var(--ei-border-primary)]" />}
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-6 h-6 rounded-full grid place-items-center text-[11px] font-semibold border ${
                          step.done
                            ? 'bg-[rgba(54,214,160,0.15)] border-[rgba(54,214,160,0.35)] text-[var(--ei-accent-green)]'
                            : 'bg-[var(--ei-surface-hover)] border-[var(--ei-border-primary)] text-[var(--ei-text-muted)]'
                        }`}
                      >
                        {step.done ? <FiCheck className="w-3 h-3" /> : step.n}
                      </span>
                      <span className={step.done ? 'text-[var(--ei-text-secondary)]' : 'text-[var(--ei-text-muted)]'}>
                        {step.label}
                      </span>
                    </div>
                  </React.Fragment>
                ))}
              </div>
            </div>

            <div className="p-5 sm:p-6 space-y-5">
              {/* Step 1 — drop zone */}
              <div>
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <label className="text-sm font-medium text-[var(--ei-text-label)]">1. Input folder or ZIP</label>
                  <span className="text-[11px] text-[var(--ei-text-muted)]">PDF · DOCX · DOC · WEBP · TIF · ZIP</span>
                </div>

                {/* Keep file inputs outside buttons — nesting inputs in <button> breaks pickers in Chrome */}
                <input
                  ref={folderInputRef}
                  type="file"
                  multiple
                  webkitdirectory=""
                  directory=""
                  onChange={(e) => {
                    addFiles(e.target.files || [], { allowZip: false })
                    e.target.value = ''
                  }}
                  className="hidden"
                  aria-hidden
                  tabIndex={-1}
                />
                <input
                  ref={zipInputRef}
                  type="file"
                  accept=".zip,application/zip,application/x-zip-compressed"
                  onChange={(e) => {
                    addFiles(e.target.files || [], { allowZip: true })
                    e.target.value = ''
                  }}
                  className="hidden"
                  aria-hidden
                  tabIndex={-1}
                />

                <button
                  type="button"
                  onClick={handleInputFolderBrowse}
                  className={`w-full text-left rounded-2xl border border-dashed transition-all duration-200 p-5 sm:p-6 ${
                    hasFiles
                      ? 'border-[rgba(54,214,160,0.35)] bg-[rgba(54,214,160,0.06)]'
                      : 'border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)] hover:border-[rgba(0,166,255,0.4)] hover:bg-[rgba(0,166,255,0.05)]'
                  }`}
                >
                  <div className="flex items-start sm:items-center gap-4 flex-col sm:flex-row">
                    <div
                      className={`w-12 h-12 rounded-2xl grid place-items-center flex-shrink-0 ${
                        hasFiles
                          ? 'bg-[rgba(54,214,160,0.15)] text-[var(--ei-accent-green)]'
                          : 'bg-[rgba(0,166,255,0.12)] text-[var(--ei-accent-blue)]'
                      }`}
                    >
                      {hasFiles ? <FiCheckCircle className="w-6 h-6" /> : <FiFolderPlus className="w-6 h-6" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-[var(--ei-text-primary)]">
                        {hasFiles
                          ? zipSelected
                            ? `${files.filter((f) => /\.zip$/i.test(f.name)).length} ZIP ready`
                            : `${resumeFiles.length} resume${resumeFiles.length !== 1 ? 's' : ''} ready`
                          : 'Click to browse a folder'}
                      </p>
                      <p className="text-xs text-[var(--ei-text-muted)] mt-1 truncate">
                        {hasFiles
                          ? inputFolderPath || 'Selected files'
                          : 'Or upload a ZIP of resumes — large folders upload in batches'}
                      </p>
                    </div>
                    <span className="org-btn-ghost pointer-events-none shrink-0">
                      <FiFolder className="w-4 h-4" />
                      Browse
                    </span>
                  </div>
                </button>

                <div className="mt-2.5 flex gap-2 flex-wrap">
                  <div className="relative flex-1 min-w-0">
                    <FiFolder className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--ei-text-muted)] pointer-events-none" />
                    <input
                      type="text"
                      value={inputFolderPath}
                      onChange={(e) => {
                        setInputFolderPath(e.target.value)
                        setInputFolderFound(!!e.target.value.trim())
                      }}
                      placeholder="Or enter path: C:/Users/.../HR Data"
                      className={`${pathInputClass} pl-9`}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      zipInputRef.current?.click()
                    }}
                    className="org-btn-ghost shrink-0"
                  >
                    <FiUpload className="w-4 h-4" />
                    Upload ZIP
                  </button>
                </div>
              </div>

              {/* Step 2 — output */}
              <div>
                <div className="flex items-center justify-between gap-3 mb-2.5 flex-wrap">
                  <label className="text-sm font-medium text-[var(--ei-text-label)]">2. Output location</label>
                  <div className="inline-flex p-0.5 rounded-lg bg-[var(--ei-surface-hover)] border border-[var(--ei-border-primary)]">
                    {[
                      { id: 'file', label: 'File path' },
                      { id: 'folder', label: 'Folder path' },
                    ].map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => {
                          if (opt.id === outputType) return
                          setOutputType(opt.id)
                          setOutputPath('')
                          setOutputFolderFound(false)
                          setOutputTarget(null)
                        }}
                        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                          outputType === opt.id
                            ? 'bg-[rgba(0,166,255,0.18)] text-[var(--ei-accent-blue)] border border-[rgba(0,166,255,0.3)]'
                            : 'text-[var(--ei-text-muted)] hover:text-[var(--ei-text-secondary)] border border-transparent'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex gap-2">
                  <div className="relative flex-1 min-w-0">
                    <FiHardDrive className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--ei-text-muted)] pointer-events-none" />
                    <input
                      type="text"
                      value={outputPath}
                      onChange={(e) => {
                        const value = e.target.value
                        setOutputPath(value)
                        setOutputFolderFound(!!value.trim())
                        // Only the desktop app can write to a typed path; in
                        // the browser it falls back to Download Excel.
                        setOutputTarget(
                          value.trim() && typeof window !== 'undefined' && window.electron?.writeFile
                            ? { path: value.trim(), isFolder: outputType === 'folder' }
                            : null,
                          value.trim()
                        )
                      }}
                      placeholder={
                        outputType === 'file'
                          ? 'C:/Users/.../Desktop/Parsed_Resumes.xlsx'
                          : 'C:/Users/.../Desktop'
                      }
                      className={`${pathInputClass} pl-9`}
                    />
                  </div>
                  <button type="button" onClick={handleOutputBrowse} className="org-btn-secondary shrink-0">
                    <FiFolder className="w-4 h-4" />
                    Browse
                  </button>
                </div>
                {outputFolderFound && outputPath && (
                  outputTargetRef.current ? (
                    <p className="mt-2 text-xs text-[var(--ei-accent-green)] flex items-center gap-1.5">
                      <FiCheck className="w-3.5 h-3.5" />
                      Output set — the file stays empty until parsing completes; open it after you see &quot;Saved to&quot;
                    </p>
                  ) : (
                    <p className="mt-2 text-xs text-[var(--ei-text-muted)] flex items-center gap-1.5">
                      <FiAlertCircle className="w-3.5 h-3.5" />
                      A typed path can&apos;t be written from the browser — use Browse, or Download Excel when done
                    </p>
                  )
                )}
              </div>

              {/* Step 3 — actions */}
              {!jobId && (
                <div className="pt-1 flex items-center justify-between gap-3 flex-wrap">
                  <label className="flex items-center gap-2.5 text-sm text-[var(--ei-text-secondary)] cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={append}
                      onChange={(e) => setAppend(e.target.checked)}
                      className="rounded border-[var(--ei-border-primary)] accent-[var(--ei-accent-blue)] bg-[var(--ei-surface-hover)] w-4 h-4"
                    />
                    Append to existing Excel
                  </label>
                  <button
                    type="button"
                    onClick={startUpload}
                    disabled={uploading || !files.length}
                    className="org-btn-primary min-w-[180px] disabled:opacity-45 disabled:cursor-not-allowed disabled:transform-none"
                  >
                    {uploading ? <FiLoader className="w-4 h-4 animate-spin" /> : <FiUpload className="w-4 h-4" />}
                    {uploading ? (uploadStatus || 'Uploading…') : 'Upload and parse'}
                  </button>
                </div>
              )}

              {/* Live progress inside workspace */}
              {jobId && (
                <div className="rounded-2xl border border-[rgba(0,166,255,0.22)] bg-[rgba(0,166,255,0.06)] p-4 space-y-3">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <p className="text-sm font-semibold text-[var(--ei-text-primary)]">
                        {isPaused
                          ? 'Parsing paused'
                          : progress?.status === 'completed'
                            ? 'Parsing complete'
                            : progress?.status === 'failed'
                              ? 'Parsing failed'
                              : 'Parsing in progress'}
                      </p>
                      <p className="text-xs text-[var(--ei-text-muted)] mt-0.5">
                        Processed {processed} / {total}
                        {failed > 0 ? ` · Failed ${failed}` : ''}
                        {processingCount > 0 ? ` · ${processingCount} queued` : ''}
                        {currentFile && processingCount > 0 && !isPaused
                          ? ` · ${currentFile}`
                          : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {isRunning && progress?.status !== 'completed' && progress?.status !== 'failed' && (
                        <button
                          type="button"
                          onClick={handlePause}
                          disabled={pausing || resuming}
                          className="org-btn-ghost text-xs px-3 py-1.5 disabled:opacity-50"
                          title="Pause after current file(s) finish"
                        >
                          {pausing ? (
                            <FiLoader className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <FiPause className="w-3.5 h-3.5" />
                          )}
                          {pausing ? 'Pausing…' : 'Pause'}
                        </button>
                      )}
                      {isPaused && (
                        <button
                          type="button"
                          onClick={handleResume}
                          disabled={resuming || pausing}
                          className="org-btn-primary text-xs px-3 py-1.5 disabled:opacity-50"
                          title="Resume remaining files"
                        >
                          {resuming ? (
                            <FiLoader className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <FiPlay className="w-3.5 h-3.5" />
                          )}
                          {resuming ? 'Resuming…' : 'Resume'}
                        </button>
                      )}
                      <span className="text-2xl font-bold tabular-nums text-[var(--ei-accent-blue)]">{progressPct}%</span>
                    </div>
                  </div>
                  <div className="h-2 rounded-full overflow-hidden bg-black/25">
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${progressPct}%`,
                        background: 'linear-gradient(90deg, var(--ei-accent-blue), var(--ei-accent-blue-2))',
                      }}
                    />
                  </div>
                  {processingCount > 0 && currentFile && !isPaused && (
                    <p className="text-xs text-[var(--ei-text-secondary)] flex items-center gap-2">
                      <FiLoader className="w-3.5 h-3.5 text-[var(--ei-accent-blue)] animate-spin flex-shrink-0" />
                      <span className="truncate">{currentFile}</span>
                    </p>
                  )}
                  {isPaused && processingCount > 0 && (
                    <p className="text-xs text-[var(--ei-text-muted)]">
                      {processingCount} file{processingCount === 1 ? '' : 's'} remaining — click Resume to continue.
                    </p>
                  )}
                  {progress?.status === 'completed' && needsSavePermission && !savingOutput && (
                    <div className="flex items-center gap-2 flex-wrap text-xs text-[var(--ei-text-secondary)]">
                      <FiAlertCircle className="w-3.5 h-3.5 flex-shrink-0 text-amber-400" />
                      <span className="min-w-0">
                        The page was reloaded, so the browser needs one click to write to {outputPath || 'your output file'}.
                      </span>
                      <button type="button" onClick={handleSaveToOutput} className="org-btn-secondary text-xs px-3 py-1.5">
                        <FiHardDrive className="w-3.5 h-3.5" />
                        Save to {outputPath || 'output'}
                      </button>
                    </div>
                  )}
                  {progress?.status === 'completed' && (savingOutput || savedTo || saveError) && (
                    <p
                      className={`text-xs flex items-center gap-1.5 ${
                        saveError ? 'text-[var(--ei-accent-red)]' : 'text-[var(--ei-accent-green)]'
                      }`}
                    >
                      {savingOutput ? (
                        <FiLoader className="w-3.5 h-3.5 animate-spin flex-shrink-0" />
                      ) : saveError ? (
                        <FiAlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                      ) : (
                        <FiCheck className="w-3.5 h-3.5 flex-shrink-0" />
                      )}
                      <span className="min-w-0 break-words">
                        {savingOutput ? 'Saving Excel to output…' : saveError || `Saved to ${savedTo}`}
                      </span>
                    </p>
                  )}
                  {(progress?.status === 'completed' ||
                    /regenerat/i.test(String(progress?.message || ''))) && (
                    <div className="flex gap-2 flex-wrap pt-1">
                      <button
                        type="button"
                        onClick={handleDownload}
                        disabled={downloading}
                        className="org-btn-primary disabled:opacity-50"
                        style={{
                          background: 'linear-gradient(135deg, #1f9d6a, #36d6a0)',
                          boxShadow: '0 8px 24px rgba(54,214,160,0.2)',
                        }}
                      >
                        {downloading ? <FiLoader className="w-4 h-4 animate-spin" /> : <FiDownload className="w-4 h-4" />}
                        {downloading
                          ? /regenerat/i.test(String(progress?.message || ''))
                            ? 'Regenerating Excel…'
                            : 'Downloading…'
                          : 'Download Excel'}
                      </button>
                      <button type="button" onClick={reset} className="org-btn-ghost">
                        <FiRefreshCw className="w-4 h-4" />
                        New job
                      </button>
                    </div>
                  )}
                  {progress?.status === 'failed' && (
                    <button type="button" onClick={reset} className="org-btn-ghost">
                      <FiRefreshCw className="w-4 h-4" />
                      Start over
                    </button>
                  )}
                </div>
              )}
            </div>
          </section>

          {/* File lists — only when relevant */}
          {showStatusLists ? (
            <section className="org-glass-card p-4 sm:p-5 hover:transform-none">
              <div className="flex items-center justify-between gap-3 mb-3.5 flex-wrap">
                <div className="flex items-center gap-2">
                  <FiFileText className="w-4 h-4 text-[var(--ei-text-muted)]" />
                  <h2 className="text-sm font-semibold text-[var(--ei-text-primary)]">File activity</h2>
                </div>
                <div className="inline-flex p-0.5 rounded-lg bg-[var(--ei-surface-hover)] border border-[var(--ei-border-primary)] flex-wrap">
                  {[
                    { id: 'all', label: 'All' },
                    { id: 'processed', label: 'Processed' },
                    { id: 'failed', label: 'Failed' },
                    { id: 'queued', label: 'Queued' },
                  ].map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => setListFilter(opt.id)}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                        listFilter === opt.id
                          ? 'bg-[rgba(0,166,255,0.18)] text-[var(--ei-accent-blue)] border border-[rgba(0,166,255,0.3)]'
                          : 'text-[var(--ei-text-muted)] hover:text-[var(--ei-text-secondary)] border border-transparent'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {showProcessedList && (
                <div className="rounded-xl border border-[var(--ei-border-primary)] overflow-hidden bg-[var(--ei-surface-hover)]">
                  <div className="px-3.5 py-2 border-b border-[var(--ei-border-primary)] flex items-center justify-between">
                    <span className="text-xs font-medium text-[var(--ei-text-secondary)]">Processed</span>
                    <span className="text-[11px] font-semibold tabular-nums px-1.5 py-0.5 rounded bg-[rgba(54,214,160,0.12)] text-[var(--ei-accent-green)]">
                      {processedDisplayNames.length}
                    </span>
                  </div>
                  <div className="min-h-[140px] max-h-[240px] overflow-auto p-2">
                    {processedDisplayNames.length === 0 ? (
                      <p className="text-xs text-[var(--ei-text-muted)] text-center py-8">Waiting for results…</p>
                    ) : (
                      <ul className="space-y-0.5">
                        {processedDisplayNames.map((name, i) => (
                          <li
                            key={`s-${i}`}
                            className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-[var(--ei-text-secondary)] hover:bg-[var(--ei-surface-hover)]"
                          >
                            <FiCheck className="w-3.5 h-3.5 flex-shrink-0 text-[var(--ei-accent-green)]" />
                            <span className="truncate" title={name}>{name}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
                )}

                {(showQueuedList || showFailedList) && (
                <div className="rounded-xl border border-[var(--ei-border-primary)] overflow-hidden bg-[var(--ei-surface-hover)] md:col-span-1">
                  <div className="px-3.5 py-2 border-b border-[var(--ei-border-primary)] flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-[var(--ei-text-secondary)]">
                      {listFilter === 'failed' ? 'Failed' : listFilter === 'queued' ? 'Queued' : 'Queue & failed'}
                    </span>
                    <div className="flex items-center gap-1">
                      {showQueuedList && (
                        <span className="text-[11px] font-semibold tabular-nums px-1.5 py-0.5 rounded bg-[rgba(0,166,255,0.12)] text-[var(--ei-accent-blue)]">
                          {inProgressFilenames.length}
                        </span>
                      )}
                      {showFailedList && (
                        <span className="text-[11px] font-semibold tabular-nums px-1.5 py-0.5 rounded bg-[rgba(255,102,133,0.12)] text-[var(--ei-accent-red)]">
                          {failedCount}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="min-h-[140px] max-h-[240px] overflow-auto p-2">
                    <ul className="space-y-0.5">
                      {showQueuedList &&
                        inProgressFilenames.map((name, i) => (
                          <li
                            key={`p-${i}`}
                            className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-[var(--ei-text-secondary)] hover:bg-[var(--ei-surface-hover)]"
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-[var(--ei-accent-blue)] flex-shrink-0" />
                            <span className="truncate" title={name}>{name}</span>
                          </li>
                        ))}
                      {showFailedList &&
                        failedEntries.map((entry, i) => (
                          <li
                            key={`f-${i}`}
                            className="flex items-start gap-2 px-2 py-1.5 rounded-lg text-xs text-[var(--ei-accent-red)] hover:bg-[var(--ei-surface-hover)]"
                            title={entry.error || entry.name}
                          >
                            <FiX className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                            <span className="min-w-0 flex-1">
                              <span className="truncate block">{entry.name}</span>
                              {entry.error ? (
                                <span className="block text-[10px] text-[var(--ei-text-muted)] truncate mt-0.5">
                                  {entry.error.length > 120 ? `${entry.error.slice(0, 120)}…` : entry.error}
                                </span>
                              ) : null}
                            </span>
                          </li>
                        ))}
                      {showFailedList && failedCount > 0 && failedEntries.length === 0 && (
                        <li className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-[var(--ei-accent-red)]">
                          <FiX className="w-3.5 h-3.5 flex-shrink-0" />
                          <span>{failedCount} file(s) failed</span>
                        </li>
                      )}
                      {(!showQueuedList || inProgressFilenames.length === 0) &&
                        (!showFailedList || failedCount === 0) && (
                          <p className="text-xs text-[var(--ei-text-muted)] text-center py-8">Queue is clear</p>
                        )}
                    </ul>
                  </div>
                </div>
                )}
              </div>
            </section>
          ) : (
            <section className="org-glass-card hover:transform-none px-5 py-8 text-center">
              <div className="mx-auto w-12 h-12 rounded-2xl grid place-items-center bg-[var(--ei-surface-hover)] border border-[var(--ei-border-primary)] mb-3">
                <FiFileText className="w-5 h-5 text-[var(--ei-text-muted)]" />
              </div>
              <p className="text-sm font-medium text-[var(--ei-text-secondary)]">No resumes selected yet</p>
              <p className="text-xs text-[var(--ei-text-muted)] mt-1.5 max-w-sm mx-auto leading-relaxed">
                Browse a folder above to load PDF, DOC/DOCX, or image (WEBP/TIF) files. Processed and queued files will appear here.
              </p>
            </section>
          )}

          {/* Instructions */}
          <section className="org-glass-card overflow-hidden hover:transform-none">
            <button
              type="button"
              onClick={() => setInstructionsOpen((o) => !o)}
              className="w-full flex items-center justify-between gap-3 px-5 py-3 text-left text-sm font-medium text-[var(--ei-text-secondary)] hover:text-[var(--ei-text-primary)] hover:bg-[var(--ei-surface-hover)] transition-colors"
            >
              <span>How it works</span>
              <FiChevronDown
                className={`w-4 h-4 text-[var(--ei-text-muted)] transition-transform ${instructionsOpen ? 'rotate-180' : ''}`}
              />
            </button>
            {instructionsOpen && (
              <div className="px-5 pb-4 text-sm text-[var(--ei-text-muted)] border-t border-[var(--ei-border-primary)] space-y-2 pt-3 leading-relaxed">
                <p>
                  Use <strong className="text-[var(--ei-text-secondary)]">Browse</strong> to pick a resume folder, set
                  where Excel should be saved, then run <strong className="text-[var(--ei-text-secondary)]">Upload and parse</strong>.
                </p>
                <p>
                  Enable <strong className="text-[var(--ei-text-secondary)]">Append to existing Excel</strong> to add rows
                  to a previous export. Large batches update progress live.
                </p>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
