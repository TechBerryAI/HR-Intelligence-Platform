/**
 * Admin-only: Bulk Resume Parsing. Select Folders + File Processing Status.
 * Styled to match portal theme (dark, purple/blue accent).
 */
import React, { useState, useRef, useEffect } from 'react'
import { uploadBulkResumes, getBulkProgress, downloadBulkResult } from '@/features/admin/services/bulkParsingService.js'

const POLL_INTERVAL_MS = 500
const ALLOWED_EXT = ['pdf', 'doc', 'docx']

export default function BulkResumeParser() {
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

  const fileInputRef = useRef(null)
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

  return (
    <div className="min-h-screen text-gray-100" style={{ background: 'radial-gradient(ellipse at top, #1a1a2e 0%, #0a0a0f 50%, #000000 100%)' }}>
      <div className="max-w-6xl mx-auto p-6">
        <div className="space-y-5">
            <section className="glass-card rounded-xl p-5">
              <h2 className="text-lg font-bold text-white mb-4">Select Folders</h2>

              <div className="mb-4">
                <label className="block text-sm font-medium text-zinc-300 mb-1">Input Folder</label>
                <p className="text-xs text-zinc-500 mb-1">Enter path to folder containing resumes</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={inputFolderPath}
                    onChange={(e) => {
                      setInputFolderPath(e.target.value)
                      setInputFolderFound(!!e.target.value.trim())
                    }}
                    placeholder="C:/Users/.../HR Data"
                    className="flex-1 px-3 py-2 border border-white/10 rounded-lg bg-white/5 text-gray-200 text-sm focus:outline-none focus:border-purple-500/50 placeholder:text-zinc-500"
                  />
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
                  <button
                    type="button"
                    onClick={handleInputFolderBrowse}
                    className="px-4 py-2 bg-white/10 hover:bg-white/15 border border-white/10 rounded-lg text-sm font-medium text-gray-200 transition-colors"
                  >
                    Browse
                  </button>
                </div>
                {inputFolderFound && (
                  <div className="mt-2 flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm">
                    <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Folder found: {inputFolderPath || 'Selected'}
                  </div>
                )}
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-zinc-300 mb-1">Output Location</label>
                <div className="flex gap-4 mb-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="outputType"
                      checked={outputType === 'file'}
                      onChange={() => setOutputType('file')}
                      className="text-purple-500 accent-purple-500"
                    />
                    <span className="text-sm text-gray-200">File Path</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="outputType"
                      checked={outputType === 'folder'}
                      onChange={() => setOutputType('folder')}
                      className="text-purple-500 accent-purple-500"
                    />
                    <span className="text-sm text-gray-200">Folder Path</span>
                  </label>
                </div>
                <label className="block text-xs text-zinc-500 mb-1">
                  {outputType === 'file' ? 'Output File Path' : 'Output Folder Path'}
                </label>
                <p className="text-xs text-zinc-500 mb-1">
                  {outputType === 'file'
                    ? 'Enter output Excel file path. If file exists, data will be appended.'
                    : 'Enter folder path for output file(s).'}
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={outputPath}
                    onChange={(e) => {
                      setOutputPath(e.target.value)
                      setOutputFolderFound(!!e.target.value.trim())
                    }}
                    placeholder="C:/Users/.../Desktop"
                    className="flex-1 px-3 py-2 border border-white/10 rounded-lg bg-white/5 text-gray-200 text-sm focus:outline-none focus:border-purple-500/50 placeholder:text-zinc-500"
                  />
                  <button
                    type="button"
                    onClick={handleOutputBrowse}
                    className="px-4 py-2 bg-white/10 hover:bg-white/15 border border-white/10 rounded-lg text-sm font-medium text-gray-200 transition-colors"
                  >
                    Browse
                  </button>
                </div>
                {outputFolderFound && outputPath && (
                  <div className="mt-2 flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm">
                    <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Folder found: {outputPath}
                  </div>
                )}
              </div>

              {!jobId && (
                <div className="flex items-center gap-3 flex-wrap">
                  <label className="flex items-center gap-2 text-sm text-zinc-300">
                    <input
                      type="checkbox"
                      checked={append}
                      onChange={(e) => setAppend(e.target.checked)}
                      className="rounded border-white/20 text-purple-500 accent-purple-500 bg-white/5"
                    />
                    Append to existing output
                  </label>
                  <button
                    type="button"
                    onClick={startUpload}
                    disabled={uploading || !files.length}
                    className="px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white shadow-glow transition-all"
                  >
                    {uploading ? 'Uploading…' : 'Upload and parse'}
                  </button>
                </div>
              )}
            </section>

            {/* Progress */}
            {jobId && (
              <section className="glass-card rounded-xl p-5">
                <p className="text-sm text-zinc-300 mb-2">
                  Progress: {processed} / {total} files completed ({processed - failed} successful, {failed} failed)
                  {processingCount > 0 && ` • ${processingCount} currently processing`}
                </p>
                <div className="h-2 bg-white/10 rounded-full overflow-hidden mb-3">
                  <div
                    className="h-full bg-gradient-to-r from-purple-600 to-blue-600 rounded-full transition-all duration-300"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
                {processingCount > 0 && currentFile && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-purple-500/10 border border-purple-500/30 text-purple-300 text-sm mb-2">
                    <span className="font-medium">Currently processing:</span> {currentFile}
                  </div>
                )}
                <p className="text-xs text-zinc-500">
                  Status: {progress?.status === 'completed' ? 'Completed' : progress?.status === 'failed' ? 'Failed' : `Processing${currentFile ? `: ${currentFile}` : ''}`}
                </p>
                {progress?.status === 'completed' && (
                  <div className="flex gap-3 mt-3">
                    <button
                      type="button"
                      onClick={handleDownload}
                      disabled={downloading}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
                    >
                      {downloading ? 'Downloading…' : 'Download Excel'}
                    </button>
                    <button
                      type="button"
                      onClick={reset}
                      className="px-4 py-2 bg-white/10 hover:bg-white/15 border border-white/10 rounded-lg text-sm font-medium text-gray-200 transition-colors"
                    >
                      New job
                    </button>
                  </div>
                )}
                {progress?.status === 'failed' && (
                  <button
                    type="button"
                    onClick={reset}
                    className="mt-3 px-4 py-2 bg-white/10 hover:bg-white/15 border border-white/10 rounded-lg text-sm font-medium text-gray-200 transition-colors"
                  >
                    Start over
                  </button>
                )}
              </section>
            )}

            {/* File Processing Status */}
            <section className="glass-card rounded-xl p-5">
              <h2 className="text-lg font-bold text-white mb-4">File Processing Status</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="border border-white/10 rounded-lg overflow-hidden bg-white/5">
                  <div className="px-3 py-2 border-b border-white/10 font-medium text-sm text-zinc-300">
                    Processed ({processedDisplayNames.length})
                  </div>
                  <div className="min-h-[200px] max-h-[280px] overflow-auto p-3 bg-white/5">
                    {processedDisplayNames.length === 0 ? (
                      <p className="text-sm text-zinc-500 text-center py-8">No files processed yet</p>
                    ) : (
                      <ul className="text-sm text-gray-300 space-y-1">
                        {processedDisplayNames.map((name, i) => (
                          <li key={`s-${i}`} className="flex items-center gap-2">
                            <svg className="w-4 h-4 flex-shrink-0 text-emerald-500" fill="currentColor" viewBox="0 0 20 20" aria-hidden>
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                            {name}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
                <div className="border border-white/10 rounded-lg overflow-hidden bg-white/5">
                  <div className="px-3 py-2 border-b border-white/10 font-medium text-sm text-zinc-300">
                    Processing ({inProgressFilenames.length}) / Failed ({failedCount})
                  </div>
                  <div className="min-h-[200px] max-h-[280px] overflow-auto p-3 bg-white/5">
                    {files.length === 0 ? (
                      <p className="text-sm text-zinc-500 text-center py-8">No files selected</p>
                    ) : (
                      <ul className="text-sm text-gray-300 space-y-1">
                        {inProgressFilenames.map((name, i) => (
                          <li key={`p-${i}`} className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-sm bg-purple-500 flex-shrink-0" aria-hidden />
                            {name}
                          </li>
                        ))}
                        {failedFilenames.map((name, i) => (
                          <li key={`f-${i}`} className="flex items-center gap-2 text-red-400">
                            <svg className="w-4 h-4 flex-shrink-0 text-red-500" fill="currentColor" viewBox="0 0 20 20" aria-hidden>
                              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                            </svg>
                            {name}
                          </li>
                        ))}
                        {failedCount > 0 && failedFilenames.length === 0 && (
                          <li className="flex items-center gap-2 text-red-400">
                            <svg className="w-4 h-4 flex-shrink-0 text-red-500" fill="currentColor" viewBox="0 0 20 20" aria-hidden>
                              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                            </svg>
                            <span>{failedCount} file(s) failed (names not available from server)</span>
                          </li>
                        )}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            </section>

            {/* Instructions (collapsible) */}
            <section className="glass-card rounded-xl overflow-hidden">
              <button
                type="button"
                onClick={() => setInstructionsOpen((o) => !o)}
                className="w-full flex items-center gap-2 px-4 py-3 text-left font-medium text-gray-200 hover:bg-white/5 transition-colors"
              >
                <svg
                  className={`w-5 h-5 transition-transform ${instructionsOpen ? 'rotate-90' : ''}`}
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
                Instructions
              </button>
              {instructionsOpen && (
                <div className="px-4 pb-4 pt-0 text-sm text-zinc-400 border-t border-white/10">
                  <p className="mb-2">
                    Add a whole folder from your computer using <strong>Browse</strong> next to Input Folder, or enter a path if you have one.
                    Only PDF, DOC, and DOCX files are processed.
                  </p>
                  <p className="mb-2">
                    Parsing uses the Bulk-Resume-Parser API via the backend. When complete, use <strong>Download Excel</strong> to get the results.
                    You can append to an existing output by checking <strong>Append to existing output</strong>.
                  </p>
                  <p>
                    Large batches may take longer; the request will wait for processing to complete.
                  </p>
                </div>
              )}
            </section>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}
      </div>
    </div>
  )
}
