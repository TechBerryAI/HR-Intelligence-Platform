import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiRequest } from '../../utils/api.js'
import { tokenService } from '../../utils/tokenService.js'
import { useAsyncAction } from '../../hooks/useAsyncAction.js'
import PanelShell, { usePanelBasePath, usePanelReadOnly } from '../org/PanelShell.jsx'
import { FiTrash2, FiRefreshCw, FiBriefcase, FiSearch, FiDownload } from 'react-icons/fi'
import { generateJobsPdf } from '../../utils/pdfReportUtils.js'

const Spinner = () => (
  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
)

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function HeadHrJobs() {
  const navigate = useNavigate()
  const basePath = usePanelBasePath()
  const readOnly = usePanelReadOnly()
  const { run: runRefresh, loading: refreshLoading } = useAsyncAction()
  const { run: runReport, loading: reportLoading } = useAsyncAction()
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [deleting, setDeleting] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [toast, setToast] = useState(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const token = tokenService.getToken()
      const data = await apiRequest('/api/head-hr/jobs', { method: 'GET', token })
      setJobs(data.jobs || [])
    } catch (err) {
      setError(err?.message || 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleDelete = async (jdid) => {
    setDeleting(jdid)
    try {
      const token = tokenService.getToken()
      await apiRequest(`/api/head-hr/jobs/${jdid}`, { method: 'DELETE', token })
      setJobs((prev) => prev.filter((j) => j.jdid !== jdid))
      showToast('Job deleted successfully')
    } catch (err) {
      showToast(err?.message || 'Failed to delete job', 'error')
    } finally {
      setDeleting(null)
      setConfirmDelete(null)
    }
  }

  const filtered = jobs.filter(
    (j) =>
      !search ||
      j.title?.toLowerCase().includes(search.toLowerCase()) ||
      j.company?.toLowerCase().includes(search.toLowerCase()) ||
      j.location?.toLowerCase().includes(search.toLowerCase()) ||
      j.posted_by_name?.toLowerCase().includes(search.toLowerCase()) ||
      j.jdid?.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <PanelShell>
      {toast && (
        <div
          className={`fixed top-20 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl text-sm font-medium ${
            toast.type === 'error'
              ? 'bg-red-500/20 border border-red-500/30 text-red-300'
              : 'bg-green-500/20 border border-green-500/30 text-green-300'
          }`}
        >
          {toast.msg}
        </div>
      )}

      {confirmDelete && !readOnly && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-sm rounded-2xl bg-zinc-900 border border-zinc-700 p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-white">Delete Job?</h3>
            <p className="mt-2 text-sm text-zinc-400">
              This will permanently delete the job{' '}
              <span className="text-white font-medium">"{confirmDelete.title}"</span>. All associated applications will also be removed.
            </p>
            <div className="mt-5 flex gap-3 justify-end">
              <button
                onClick={() => setConfirmDelete(null)}
                className="px-4 py-2 rounded-lg text-sm font-medium text-zinc-300 bg-zinc-800 hover:bg-zinc-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(confirmDelete.jdid)}
                disabled={deleting === confirmDelete.jdid}
                className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-500 disabled:opacity-50 transition-colors"
              >
                {deleting === confirmDelete.jdid ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="org-page-title flex items-center gap-2">
            <FiBriefcase className="org-page-icon" /> All Jobs
          </h1>
          <p className="org-page-subtitle">{jobs.length} job{jobs.length !== 1 ? 's' : ''} in system</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => runRefresh(load)}
            disabled={refreshLoading}
            className="org-btn-secondary"
          >
            {refreshLoading ? <Spinner /> : <FiRefreshCw className="w-4 h-4" />}
            {refreshLoading ? 'Refreshing…' : 'Refresh'}
          </button>
          <button
            onClick={() => runReport(() => { generateJobsPdf(filtered.length ? filtered : jobs) })}
            disabled={jobs.length === 0 || reportLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            {reportLoading ? <Spinner /> : <FiDownload className="w-4 h-4" />}
            {reportLoading ? 'Preparing…' : 'Download Report'}
          </button>
        </div>
      </div>

      <div className="relative mb-5">
        <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          placeholder="Search by title, company, location or HR admin…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="org-search-input"
        />
      </div>

      {error && (
        <div className="org-error-banner">{error}</div>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="org-skeleton" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="org-empty-state">
          {search ? 'No jobs match your search.' : 'No jobs found.'}
        </div>
      ) : (
        <div className="org-table-wrap">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="org-table-head">
                  <th className="org-th">ID</th>
                  <th className="org-th">Title</th>
                  <th className="org-th">Company</th>
                  <th className="org-th">Location</th>
                  <th className="org-th">Posted By</th>
                  <th className="org-th">Status</th>
                  <th className="org-th">Posted</th>
                  {!readOnly && (
                    <th className="org-th text-right">Actions</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                {filtered.map((job) => (
                  <tr
                    key={job.jdid}
                    role="button"
                    tabIndex={0}
                    onClick={() => navigate(`${basePath}/jobs/${encodeURIComponent(job.jdid)}`)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`${basePath}/jobs/${encodeURIComponent(job.jdid)}`) } }}
                    className="org-table-row-clickable"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-purple-600 dark:text-purple-400">{job.jdid}</td>
                    <td className="org-td-primary max-w-[180px] truncate">{job.title}</td>
                    <td className="org-td-secondary">{job.company}</td>
                    <td className="org-td-muted text-xs">{job.location}</td>
                    <td className="org-td-secondary text-xs">{job.posted_by_name || '—'}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          job.enabled
                            ? 'bg-green-50 dark:bg-green-500/15 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-500/20'
                            : 'bg-slate-100 dark:bg-slate-700/50 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
                        }`}
                      >
                        {job.enabled ? 'Active' : 'Disabled'}
                      </span>
                    </td>
                    <td className="org-td-muted">{formatDate(job.posted_on)}</td>
                    {!readOnly && (
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={(e) => { e.stopPropagation(); setConfirmDelete(job) }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 border border-red-200 dark:border-red-500/30 transition-all"
                      >
                        <FiTrash2 className="w-3.5 h-3.5" /> Delete
                      </button>
                    </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </PanelShell>
  )
}
