import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import { useApp } from '@/core/context/AppContext.jsx'
import { useAsyncAction } from '@/shared/hooks/useAsyncAction.js'
import PanelShell, { usePanelBasePath, usePanelReadOnly } from '@/features/organization/pages/org/PanelShell.jsx'
import PremiumInput from '@/shared/components/PremiumInput.jsx'
import PremiumButton from '@/shared/components/PremiumButton.jsx'
import { FiTrash2, FiRefreshCw, FiBriefcase, FiSearch, FiDownload, FiEdit2, FiX } from 'react-icons/fi'
import { generateJobsPdf } from '@/shared/utils/pdfReportUtils.js'

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

function parseExperienceRange(experience) {
  const raw = String(experience || '').trim()
  if (!raw) return { from: '', to: '' }
  const range = raw.match(/(\d+(?:\.\d+)?)\s*[-–—to]+\s*(\d+(?:\.\d+)?)/i)
  if (range) return { from: range[1], to: range[2] }
  const single = raw.match(/(\d+(?:\.\d+)?)/)
  return { from: single ? single[1] : '', to: '' }
}

export default function HeadHrJobs() {
  const navigate = useNavigate()
  const basePath = usePanelBasePath()
  const readOnly = usePanelReadOnly()
  const { setJobEnabled, updateJob } = useApp()
  const { run: runRefresh, loading: refreshLoading } = useAsyncAction()
  const { run: runReport, loading: reportLoading } = useAsyncAction()
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [deleting, setDeleting] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [toast, setToast] = useState(null)
  const [togglingJobId, setTogglingJobId] = useState(null)
  const [editingJob, setEditingJob] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [editLocation, setEditLocation] = useState('')
  const [editSalary, setEditSalary] = useState('')
  const [editExperienceFrom, setEditExperienceFrom] = useState('')
  const [editExperienceTo, setEditExperienceTo] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState('')

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

  const handleToggleEnabled = async (job, nextEnabled) => {
    const jdid = job.jdid
    if (!jdid || togglingJobId) return
    setTogglingJobId(jdid)
    const prevEnabled = !!job.enabled
    setJobs((prev) => prev.map((j) => (j.jdid === jdid ? { ...j, enabled: nextEnabled } : j)))
    try {
      const token = tokenService.getToken()
      await apiRequest(`/api/jobs/${encodeURIComponent(jdid)}/enabled`, {
        method: 'PATCH',
        body: { enabled: nextEnabled },
        token,
      })
      await setJobEnabled(jdid, nextEnabled)
      showToast(nextEnabled ? 'Job enabled' : 'Job disabled')
    } catch (err) {
      setJobs((prev) => prev.map((j) => (j.jdid === jdid ? { ...j, enabled: prevEnabled } : j)))
      showToast(err?.data?.error || err?.message || 'Failed to update job status', 'error')
    } finally {
      setTogglingJobId(null)
    }
  }

  const openEditJob = async (job) => {
    setEditError('')
    setEditingJob({ jdid: job.jdid, title: job.title })
    setEditTitle(job.title || '')
    setEditLocation(job.location || '')
    setEditSalary(job.salary || '')
    const parsed = parseExperienceRange(job.experience)
    setEditExperienceFrom(parsed.from)
    setEditExperienceTo(parsed.to)
    setEditDescription('')
    try {
      const token = tokenService.getToken()
      const detail = await apiRequest(`/api/head-hr/jobs/${encodeURIComponent(job.jdid)}`, {
        method: 'GET',
        token,
      })
      const exp = parseExperienceRange(detail.experience)
      setEditTitle(detail.title || job.title || '')
      setEditLocation(detail.location || '')
      setEditSalary(detail.salary || '')
      setEditExperienceFrom(exp.from)
      setEditExperienceTo(exp.to)
      setEditDescription(detail.description || '')
    } catch {
      // Keep list fields
    }
  }

  const closeEditJob = () => {
    if (editSaving) return
    setEditingJob(null)
    setEditError('')
  }

  const handleEditSubmit = async (e) => {
    e.preventDefault()
    if (!editingJob?.jdid) return
    if (!editTitle.trim() || !editLocation.trim()) {
      setEditError('Title and location are required')
      return
    }
    setEditSaving(true)
    setEditError('')
    try {
      const token = tokenService.getToken()
      await apiRequest(`/api/jobs/${encodeURIComponent(editingJob.jdid)}`, {
        method: 'PUT',
        body: {
          title: editTitle.trim(),
          location: editLocation.trim(),
          salary: editSalary.trim(),
          experienceFrom: editExperienceFrom,
          experienceTo: editExperienceTo,
          description: editDescription,
        },
        token,
      })
      await updateJob(editingJob.jdid, {
        title: editTitle.trim(),
        location: editLocation.trim(),
        salary: editSalary.trim(),
        experienceFrom: editExperienceFrom,
        experienceTo: editExperienceTo,
        description: editDescription,
      })
      showToast('Job updated successfully')
      setEditingJob(null)
      await load()
    } catch (err) {
      setEditError(err?.data?.error || err?.message || 'Failed to update job')
    } finally {
      setEditSaving(false)
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
                      <div className="inline-flex items-center justify-end gap-2 flex-wrap">
                        <label className="inline-flex items-center gap-2 cursor-pointer select-none">
                          <span className={`text-xs font-medium ${job.enabled ? 'text-green-400' : 'text-slate-400'}`}>
                            {job.enabled ? 'Enabled' : 'Disabled'}
                          </span>
                          <input
                            type="checkbox"
                            className="sr-only"
                            checked={!!job.enabled}
                            disabled={togglingJobId === job.jdid}
                            onChange={(e) => handleToggleEnabled(job, e.target.checked)}
                          />
                          <span
                            className={`relative inline-block w-11 h-6 rounded-full transition-colors ${
                              job.enabled ? 'bg-emerald-500' : 'bg-zinc-600'
                            } ${togglingJobId === job.jdid ? 'opacity-60' : ''}`}
                            aria-hidden
                          >
                            <span
                              className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                                job.enabled ? 'translate-x-[22px]' : 'translate-x-0.5'
                              }`}
                            />
                          </span>
                        </label>
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); openEditJob(job) }}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#E8EDF3] hover:bg-white/10 border border-white/15 transition-all"
                        >
                          <FiEdit2 className="w-3.5 h-3.5" /> Edit
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setConfirmDelete(job) }}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 border border-red-200 dark:border-red-500/30 transition-all"
                        >
                          <FiTrash2 className="w-3.5 h-3.5" /> Delete
                        </button>
                      </div>
                    </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {editingJob && !readOnly && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-2xl rounded-2xl bg-zinc-900 border border-zinc-700 shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700">
              <h3 className="text-lg font-semibold text-white">Edit Job Post</h3>
              <button type="button" onClick={closeEditJob} className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800">
                <FiX className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleEditSubmit} className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
              {editError && (
                <p className="text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{editError}</p>
              )}
              <PremiumInput label="Job Title" required value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
              <PremiumInput label="Location" required value={editLocation} onChange={(e) => setEditLocation(e.target.value)} />
              <div className="grid sm:grid-cols-2 gap-4">
                <PremiumInput label="Salary (optional)" value={editSalary} onChange={(e) => setEditSalary(e.target.value)} />
                <div>
                  <label className="block text-sm font-semibold text-zinc-300 mb-2">Experience Range (years)</label>
                  <div className="grid grid-cols-2 gap-3">
                    <input type="number" min="0" className="premium-input" value={editExperienceFrom} onChange={(e) => setEditExperienceFrom(e.target.value)} placeholder="From" />
                    <input type="number" min="0" className="premium-input" value={editExperienceTo} onChange={(e) => setEditExperienceTo(e.target.value)} placeholder="To" />
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-sm font-semibold text-zinc-300 mb-2">Description</label>
                <textarea className="premium-input min-h-[110px] resize-y" value={editDescription} onChange={(e) => setEditDescription(e.target.value)} />
              </div>
              <div className="flex justify-end gap-3 pt-1">
                <PremiumButton type="button" variant="secondary" onClick={closeEditJob} disabled={editSaving}>Cancel</PremiumButton>
                <PremiumButton type="submit" variant="primary" loading={editSaving} disabled={editSaving}>
                  {editSaving ? 'Saving…' : 'Save changes'}
                </PremiumButton>
              </div>
            </form>
          </div>
        </div>
      )}
    </PanelShell>
  )
}
