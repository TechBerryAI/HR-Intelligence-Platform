/**
 * Admin-only: Bulk Resume Parsing. Select Folders + File Processing Status.
 * Styled to match enterprise org panel (glass + blue accent).
 */
import React, { useState, useRef, useEffect } from 'react'
import {
  FiLayers,
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
} from 'react-icons/fi'
import { uploadBulkResumes, getBulkProgress, downloadBulkResult } from '@/features/admin/services/bulkParsingService.js'

const POLL_INTERVAL_MS = 500
const ALLOWED_EXT = ['pdf', 'doc', 'docx']

export default function BulkResumeParser({ embedded = false }) {
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
  const [downloading, setDownloading] = useState(false)
  const [instructionsOpen, setInstructionsOpen] = useState(false)

  const folderInputRef = useRef(null)

  const b64ToFile = (name, b64) => {
    const bin = atob(b64)
    const arr = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i)
    return new File([arr], name)
  }

  const addFiles = (list) => {
    const valid = Array.from(list).filter((f) => {
      const ext = (f.name.split('.').pop() || '').toLowerCase()
      return ALLOWED_EXT.includes(ext)
    })
    if (valid.length) {
      setFiles((prev) => [...prev, ...valid])
      const first = valid[0]
      const folderName = first.webkitRelativePath ? first.webkitRelativePath.split('/')[0] : ''
      setInputFolderPath(folderName || 'Selected folder')
      setInputFolderFound(true)
    }
    setError(null)
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
          setError('No PDF, DOC, or DOCX files found in that folder.')
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
        const dirHandle = await window.showDirectoryPicker({ startIn: 'downloads' })
        setOutputPath(dirHandle.name)
        setOutputFolderFound(true)
        setError(null)
      } else {
        if (electron?.selectSaveFile) {
          const fullPath = await electron.selectSaveFile('Parsed_Resumes.xlsx')
          if (fullPath) {
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
        const fileHandle = await window.showSaveFilePicker({
          suggestedName: 'Parsed_Resumes.xlsx',
          types: [
            {
              description: 'Excel workbook',
              accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
            },
          ],
        })
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
      setError('Select at least one file (PDF, DOC, DOCX).')
      return
    }
    setError(null)
    setUploading(true)
    try {
      const res = await uploadBulkResumes(files, append)
      setJobId(res.job_id)
      setProgress({
        status: res.status || 'started',
        total_files: res.total_files || files.length,
        processed_files: 0,
        failed_files: 0,
        message: res.message || 'Processing started',
      })
    } catch (e) {
      const status = e?.status
      const code = e?.data?.code
      const msg = e?.data?.error || e?.message
      if (status === 502 || status === 503 || code === 'BULK_PARSER_UNREACHABLE' || code === 'BULK_PARSER_NOT_CONFIGURED') {
        setError(msg || 'Bulk parsing service unavailable. Ensure the parsing service is running (see README).')
      } else {
        setError(msg || 'Upload failed')
      }
    } finally {
      setUploading(false)
    }
  }

  useEffect(() => {
    if (!jobId) return
    const id = setInterval(async () => {
      try {
        const data = await getBulkProgress(jobId)
        setProgress(data)
        if (data.status === 'completed' || data.status === 'failed') clearInterval(id)
      } catch {
        // ignore poll errors
      }
    }, POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [jobId])

  const handleDownload = async () => {
    if (!jobId || progress?.status !== 'completed') return
    setDownloading(true)
    setError(null)
    try {
      await downloadBulkResult(jobId)
    } catch (e) {
      setError(e?.message || 'Download failed')
    } finally {
      setDownloading(false)
    }
  }

  const reset = () => {
    setJobId(null)
    setProgress(null)
    setFiles([])
    setError(null)
    setInputFolderPath('')
    setInputFolderFound(false)
  }

  const total = progress?.total_files ?? files.length
  const processed = progress?.processed_files ?? 0
  const failed = progress?.failed_files ?? 0
  const failedFilenames = progress?.failed_filenames ?? progress?.failedFilenames ?? []
  const successFilenames = progress?.success_filenames ?? progress?.successFilenames ?? []
  const hasDetailedLists = successFilenames.length > 0 || failedFilenames.length > 0
  const failedCount = failedFilenames.length || failed
  const processingCount = Math.max(0, total - processed)
  const progressPct = total ? Math.round((processed / total) * 100) : 0
  const currentFile =
    progress?.message?.replace(/^Processing:\s*/i, '').trim() ||
    (files[processed]?.name ?? (files.length ? files[0]?.name : ''))
  const inProgressFilenames = hasDetailedLists
    ? files.map((f) => f.name).filter((name) => !successFilenames.includes(name) && !failedFilenames.includes(name))
    : files.slice(processed).map((f) => f.name)
  const processedDisplayNames = hasDetailedLists ? successFilenames : files.slice(0, processed).map((f) => f.name)

  const statusLabel =
    progress?.status === 'completed'
      ? 'Completed'
      : progress?.status === 'failed'
        ? 'Failed'
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
        : jobId
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
  const showStatusLists = hasFiles || jobId

  return (
    <div
      className={embedded ? 'text-[var(--ei-text-primary)]' : 'min-h-screen org-shell text-[var(--ei-text-primary)]'}
    >
      <div className={embedded ? 'w-full max-w-5xl' : 'max-w-5xl mx-auto p-6'}>
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              <h1 className="org-page-title flex items-center gap-2.5">
                <span className="w-10 h-10 rounded-xl grid place-items-center bg-[rgba(0,166,255,0.12)] border border-[rgba(0,166,255,0.22)]">
                  <FiLayers className="w-5 h-5 text-[var(--ei-accent-blue)]" />
                </span>
                Bulk Parsing
              </h1>
              <p className="org-page-subtitle pl-[3.25rem]">
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
                    <p className="text-xl font-bold tabular-nums leading-none text-[#F5F7FA]">{m.value}</p>
                    <p className="text-[11px] mt-1 text-[var(--ei-text-muted)] truncate">{m.label}</p>
                  </div>
                </div>
              )
            })}
          </div>

          {error && (
            <div className="org-error-banner flex items-start gap-2">
              <FiAlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Main workspace */}
          <section className="org-glass-card hover:transform-none overflow-hidden">
            {/* Step rail */}
            <div className="px-5 sm:px-6 py-3.5 border-b border-[var(--ei-border-primary)] bg-white/[0.015]">
              <div className="flex items-center gap-2 sm:gap-3 text-xs sm:text-sm flex-wrap">
                {[
                  { n: 1, label: 'Select resumes', done: hasFiles },
                  { n: 2, label: 'Set output', done: !!outputPath.trim() },
                  { n: 3, label: 'Parse', done: progress?.status === 'completed' },
                ].map((step, idx) => (
                  <React.Fragment key={step.n}>
                    {idx > 0 && <span className="hidden sm:block w-6 h-px bg-white/10" />}
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-6 h-6 rounded-full grid place-items-center text-[11px] font-semibold border ${
                          step.done
                            ? 'bg-[rgba(54,214,160,0.15)] border-[rgba(54,214,160,0.35)] text-[var(--ei-accent-green)]'
                            : 'bg-white/[0.04] border-white/10 text-[var(--ei-text-muted)]'
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
                  <label className="text-sm font-medium text-[var(--ei-text-label)]">1. Input folder</label>
                  <span className="text-[11px] text-[var(--ei-text-muted)]">PDF · DOC · DOCX</span>
                </div>

                <button
                  type="button"
                  onClick={handleInputFolderBrowse}
                  className={`w-full text-left rounded-2xl border border-dashed transition-all duration-200 p-5 sm:p-6 ${
                    hasFiles
                      ? 'border-[rgba(54,214,160,0.35)] bg-[rgba(54,214,160,0.06)]'
                      : 'border-white/15 bg-white/[0.02] hover:border-[rgba(0,166,255,0.4)] hover:bg-[rgba(0,166,255,0.05)]'
                  }`}
                >
                  <input
                    ref={folderInputRef}
                    type="file"
                    multiple
                    webkitdirectory=""
                    directory=""
                    onChange={(e) => {
                      addFiles(e.target.files || [])
                      e.target.value = ''
                    }}
                    className="hidden"
                  />
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
                          ? `${files.length} resume${files.length !== 1 ? 's' : ''} ready`
                          : 'Click to browse a folder'}
                      </p>
                      <p className="text-xs text-[var(--ei-text-muted)] mt-1 truncate">
                        {hasFiles
                          ? inputFolderPath || 'Selected folder'
                          : 'Or paste a folder path below — resumes load when you browse'}
                      </p>
                    </div>
                    <span className="org-btn-ghost pointer-events-none shrink-0">
                      <FiFolder className="w-4 h-4" />
                      Browse
                    </span>
                  </div>
                </button>

                <div className="mt-2.5 flex gap-2">
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
                </div>
              </div>

              {/* Step 2 — output */}
              <div>
                <div className="flex items-center justify-between gap-3 mb-2.5 flex-wrap">
                  <label className="text-sm font-medium text-[var(--ei-text-label)]">2. Output location</label>
                  <div className="inline-flex p-0.5 rounded-lg bg-white/[0.04] border border-[var(--ei-border-primary)]">
                    {[
                      { id: 'file', label: 'File path' },
                      { id: 'folder', label: 'Folder path' },
                    ].map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setOutputType(opt.id)}
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
                        setOutputPath(e.target.value)
                        setOutputFolderFound(!!e.target.value.trim())
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
                  <p className="mt-2 text-xs text-[var(--ei-accent-green)] flex items-center gap-1.5">
                    <FiCheck className="w-3.5 h-3.5" />
                    Output set
                  </p>
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
                      className="rounded border-white/20 accent-[var(--ei-accent-blue)] bg-white/5 w-4 h-4"
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
                    {uploading ? 'Uploading…' : 'Upload and parse'}
                  </button>
                </div>
              )}

              {/* Live progress inside workspace */}
              {jobId && (
                <div className="rounded-2xl border border-[rgba(0,166,255,0.22)] bg-[rgba(0,166,255,0.06)] p-4 space-y-3">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <p className="text-sm font-semibold text-[var(--ei-text-primary)]">Parsing in progress</p>
                      <p className="text-xs text-[var(--ei-text-muted)] mt-0.5">
                        {processed}/{total} done
                        {failed > 0 ? ` · ${failed} failed` : ''}
                        {processingCount > 0 ? ` · ${processingCount} queued` : ''}
                      </p>
                    </div>
                    <span className="text-2xl font-bold tabular-nums text-[var(--ei-accent-blue)]">{progressPct}%</span>
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
                  {processingCount > 0 && currentFile && (
                    <p className="text-xs text-[var(--ei-text-secondary)] flex items-center gap-2">
                      <FiLoader className="w-3.5 h-3.5 text-[var(--ei-accent-blue)] animate-spin flex-shrink-0" />
                      <span className="truncate">{currentFile}</span>
                    </p>
                  )}
                  {progress?.status === 'completed' && (
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
                        {downloading ? 'Downloading…' : 'Download Excel'}
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
              <div className="flex items-center gap-2 mb-3.5">
                <FiFileText className="w-4 h-4 text-[var(--ei-text-muted)]" />
                <h2 className="text-sm font-semibold text-[var(--ei-text-primary)]">File activity</h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="rounded-xl border border-[var(--ei-border-primary)] overflow-hidden bg-white/[0.02]">
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
                            className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-[var(--ei-text-secondary)] hover:bg-white/[0.03]"
                          >
                            <FiCheck className="w-3.5 h-3.5 flex-shrink-0 text-[var(--ei-accent-green)]" />
                            <span className="truncate">{name}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-[var(--ei-border-primary)] overflow-hidden bg-white/[0.02]">
                  <div className="px-3.5 py-2 border-b border-[var(--ei-border-primary)] flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-[var(--ei-text-secondary)]">Queue &amp; failed</span>
                    <div className="flex items-center gap-1">
                      <span className="text-[11px] font-semibold tabular-nums px-1.5 py-0.5 rounded bg-[rgba(0,166,255,0.12)] text-[var(--ei-accent-blue)]">
                        {inProgressFilenames.length}
                      </span>
                      <span className="text-[11px] font-semibold tabular-nums px-1.5 py-0.5 rounded bg-[rgba(255,102,133,0.12)] text-[var(--ei-accent-red)]">
                        {failedCount}
                      </span>
                    </div>
                  </div>
                  <div className="min-h-[140px] max-h-[240px] overflow-auto p-2">
                    <ul className="space-y-0.5">
                      {inProgressFilenames.map((name, i) => (
                        <li
                          key={`p-${i}`}
                          className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-[var(--ei-text-secondary)] hover:bg-white/[0.03]"
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-[var(--ei-accent-blue)] flex-shrink-0" />
                          <span className="truncate">{name}</span>
                        </li>
                      ))}
                      {failedFilenames.map((name, i) => (
                        <li
                          key={`f-${i}`}
                          className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-[var(--ei-accent-red)] hover:bg-white/[0.03]"
                        >
                          <FiX className="w-3.5 h-3.5 flex-shrink-0" />
                          <span className="truncate">{name}</span>
                        </li>
                      ))}
                      {failedCount > 0 && failedFilenames.length === 0 && (
                        <li className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-[var(--ei-accent-red)]">
                          <FiX className="w-3.5 h-3.5 flex-shrink-0" />
                          <span>{failedCount} file(s) failed</span>
                        </li>
                      )}
                      {inProgressFilenames.length === 0 && failedCount === 0 && (
                        <p className="text-xs text-[var(--ei-text-muted)] text-center py-8">Queue is clear</p>
                      )}
                    </ul>
                  </div>
                </div>
              </div>
            </section>
          ) : (
            <section className="org-glass-card hover:transform-none px-5 py-8 text-center">
              <div className="mx-auto w-12 h-12 rounded-2xl grid place-items-center bg-white/[0.04] border border-white/10 mb-3">
                <FiFileText className="w-5 h-5 text-[var(--ei-text-muted)]" />
              </div>
              <p className="text-sm font-medium text-[var(--ei-text-secondary)]">No resumes selected yet</p>
              <p className="text-xs text-[var(--ei-text-muted)] mt-1.5 max-w-sm mx-auto leading-relaxed">
                Browse a folder above to load PDF, DOC, or DOCX files. Processed and queued files will appear here.
              </p>
            </section>
          )}

          {/* Instructions */}
          <section className="org-glass-card overflow-hidden hover:transform-none">
            <button
              type="button"
              onClick={() => setInstructionsOpen((o) => !o)}
              className="w-full flex items-center justify-between gap-3 px-5 py-3 text-left text-sm font-medium text-[var(--ei-text-secondary)] hover:text-[var(--ei-text-primary)] hover:bg-white/[0.03] transition-colors"
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
