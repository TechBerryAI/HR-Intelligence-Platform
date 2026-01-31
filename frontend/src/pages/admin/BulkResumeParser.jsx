/**
 * Admin-only: Bulk Resume Parsing. Upload multiple resumes, parse via Bulk-Resume-Parser API (proxied by backend), export Excel.
 */
import React, { useState, useRef, useEffect } from 'react'
import { uploadBulkResumes, getBulkProgress, downloadBulkResult } from '../../services/bulkParsingService.js'

const POLL_INTERVAL_MS = 2000
const ALLOWED_EXT = ['pdf', 'doc', 'docx']

export default function BulkResumeParser() {
  const [files, setFiles] = useState([])
  const [append, setAppend] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const fileInputRef = useRef(null)
  const folderInputRef = useRef(null)

  const addFiles = (list) => {
    const valid = Array.from(list).filter((f) => {
      const ext = (f.name.split('.').pop() || '').toLowerCase()
      return ALLOWED_EXT.includes(ext)
    })
    setFiles((prev) => [...prev, ...valid])
    setError(null)
  }

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
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
      setError(e?.message || e?.data?.error || 'Upload failed')
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
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold text-white mb-2">Bulk Resume Parser</h1>
      <p className="text-zinc-400 text-sm mb-6">
        Add a whole folder from your computer or select individual files (PDF/DOC/DOCX). Parsing uses Grok via the Bulk-Resume-Parser API. Export results to Excel when complete.
      </p>

      {!jobId ? (
        <>
          <div className="mb-4">
            <label className="flex items-center gap-2 text-zinc-300">
              <input type="checkbox" checked={append} onChange={(e) => setAppend(e.target.checked)} className="rounded" />
              Append to existing output
            </label>
          </div>
          <div className="border border-white/10 rounded-lg p-4 mb-4">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={ALLOWED_EXT.map((e) => `.${e}`).join(',')}
              onChange={(e) => { addFiles(e.target.files || []); e.target.value = '' }}
              className="hidden"
            />
            <input
              ref={folderInputRef}
              type="file"
              multiple
              webkitdirectory=""
              directory=""
              onChange={(e) => { addFiles(e.target.files || []); e.target.value = '' }}
              className="hidden"
            />
            <div className="flex flex-wrap gap-3 mb-3">
              <button
                type="button"
                onClick={() => folderInputRef.current?.click()}
                className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg text-sm"
              >
                Select folder
              </button>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg text-sm"
              >
                Select files
              </button>
            </div>
            <p className="text-zinc-500 text-xs mb-2">
              Use &quot;Select folder&quot; to add all resumes from a folder (navigate to its location in the dialog). Only PDF, DOC, and DOCX are included.
            </p>
            {files.length > 0 && (
              <ul className="text-sm text-zinc-300 space-y-1">
                {files.map((f, i) => (
                  <li key={i} className="flex items-center justify-between">
                    <span>{f.name}</span>
                    <button type="button" onClick={() => removeFile(i)} className="text-red-400 hover:underline">
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <button
            type="button"
            onClick={startUpload}
            disabled={uploading || !files.length}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg"
          >
            {uploading ? 'Uploading…' : 'Upload and parse'}
          </button>
        </>
      ) : (
        <>
          <div className="border border-white/10 rounded-lg p-4 mb-4">
            <p className="text-zinc-300 text-sm">Job ID: {jobId}</p>
            <p className="text-zinc-300 text-sm mt-1">Status: {progress?.status ?? '—'}</p>
            <p className="text-zinc-300 text-sm">
              Processed: {progress?.processed_files ?? 0} / {progress?.total_files ?? 0}
              {progress?.failed_files > 0 && ` (failed: ${progress.failed_files})`}
            </p>
            {progress?.message && <p className="text-zinc-400 text-xs mt-1">{progress.message}</p>}
          </div>
          {progress?.status === 'completed' && (
            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleDownload}
                disabled={downloading}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg"
              >
                {downloading ? 'Downloading…' : 'Download Excel'}
              </button>
              <button type="button" onClick={reset} className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg">
                New job
              </button>
            </div>
          )}
          {progress?.status !== 'completed' && progress?.status !== 'failed' && (
            <p className="text-zinc-400 text-sm">Parsing in progress. You can wait here or come back later and use the same job ID to download.</p>
          )}
          {progress?.status === 'failed' && (
            <button type="button" onClick={reset} className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg">
              Start over
            </button>
          )}
        </>
      )}

      {error && (
        <div className="mt-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-200 text-sm">
          {error}
        </div>
      )}
    </div>
  )
}
