import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import { useAsyncAction } from '@/shared/hooks/useAsyncAction.js'
import PanelShell, { usePanelBasePath } from '@/features/organization/pages/org/PanelShell.jsx'
import { FiRefreshCw, FiFileText, FiSearch, FiDownload } from 'react-icons/fi'
import { generateApplicationsPdf } from '@/shared/utils/pdfReportUtils.js'

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

function StatusBadge({ status }) {
  const map = {
    pending: 'bg-yellow-50 dark:bg-yellow-500/15 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-500/20',
    shortlisted: 'bg-green-50 dark:bg-green-500/15 text-green-700 dark:text-green-400 border-green-200 dark:border-green-500/20',
    rejected: 'bg-red-50 dark:bg-red-500/15 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20',
    reviewed: 'bg-blue-50 dark:bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border capitalize ${
        map[status] || 'bg-slate-100 dark:bg-slate-700/50 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
      }`}
    >
      {status || 'pending'}
    </span>
  )
}

export default function HeadHrApplications() {
  const navigate = useNavigate()
  const basePath = usePanelBasePath()
  const { run: runRefresh, loading: refreshLoading } = useAsyncAction()
  const { run: runReport, loading: reportLoading } = useAsyncAction()
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reportError, setReportError] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const token = tokenService.getToken()
      const data = await apiRequest('/api/head-hr/applications', { method: 'GET', token })
      setApplications(data.applications || [])
    } catch (err) {
      setError(err?.message || 'Failed to load applications')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = applications.filter((a) => {
    const matchSearch =
      !search ||
      a.candidate_name?.toLowerCase().includes(search.toLowerCase()) ||
      a.candidate_email?.toLowerCase().includes(search.toLowerCase()) ||
      a.job_title?.toLowerCase().includes(search.toLowerCase()) ||
      a.job_company?.toLowerCase().includes(search.toLowerCase()) ||
      a.hr_name?.toLowerCase().includes(search.toLowerCase())
    const matchStatus = statusFilter === 'all' || a.status === statusFilter
    return matchSearch && matchStatus
  })

  const shortlistedCount = applications.filter((a) => a.shortlisted).length
  const pendingCount = applications.filter((a) => a.status === 'pending').length

  return (
    <PanelShell>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="org-page-title flex items-center gap-2">
            <FiFileText className="org-page-icon" /> All Applications
          </h1>
          <p className="org-page-subtitle">
            {applications.length} total &bull; {shortlistedCount} shortlisted &bull; {pendingCount} pending
          </p>
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
            onClick={() => runReport(() => {
              setReportError('')
              try {
                generateApplicationsPdf(filtered.length ? filtered : applications)
              } catch (e) {
                console.error('PDF generation failed:', e)
                setReportError(e?.message || 'Failed to generate PDF')
              }
            })}
            disabled={applications.length === 0 || reportLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            {reportLoading ? <Spinner /> : <FiDownload className="w-4 h-4" />}
            {reportLoading ? 'Preparing…' : 'Download Report'}
          </button>
        </div>
      </div>

      {reportError && (
        <div className="org-error-banner mb-4">
          {reportError}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1">
          <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by candidate, job or admin…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="org-search-input"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="org-select-input"
        >
          <option value="all">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="shortlisted">Shortlisted</option>
          <option value="rejected">Rejected</option>
          <option value="reviewed">Reviewed</option>
        </select>
      </div>

      {error && (
        <div className="org-error-banner">{error}</div>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="org-skeleton" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="org-empty-state">
          {search || statusFilter !== 'all' ? 'No applications match your filters.' : 'No applications found.'}
        </div>
      ) : (
        <div className="org-table-wrap">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="org-table-head">
                  <th className="org-th">#</th>
                  <th className="org-th">Candidate</th>
                  <th className="org-th">Job</th>
                  <th className="org-th">HR Admin</th>
                  <th className="org-th">Match</th>
                  <th className="org-th">Status</th>
                  <th className="org-th">Applied</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                {filtered.map((app) => (
                  <tr
                    key={app.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => navigate(`${basePath}/applications/${app.id}`)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`${basePath}/applications/${app.id}`) } }}
                    className="org-table-row-clickable"
                  >
                    <td className="px-4 py-3 text-slate-500 text-xs font-mono">#{app.id}</td>
                    <td className="px-4 py-3">
                      <p className="text-slate-900 dark:text-slate-100 font-medium">{app.candidate_name || '—'}</p>
                      <p className="text-slate-500 text-xs">{app.candidate_email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-slate-800 dark:text-slate-200 font-medium max-w-[160px] truncate">{app.job_title || '—'}</p>
                      <p className="text-slate-500 text-xs">{app.job_company}</p>
                    </td>
                    <td className="org-td-secondary text-xs">{app.hr_name || '—'}</td>
                    <td className="px-4 py-3">
                      {app.match_score != null ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-amber-500 to-green-500"
                              style={{ width: `${Math.min(100, app.match_score)}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-600 dark:text-slate-400 tabular-nums">
                            {Math.round(app.match_score)}%
                          </span>
                        </div>
                      ) : (
                        <span className="text-slate-400 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={app.shortlisted ? 'shortlisted' : app.status} />
                    </td>
                    <td className="org-td-muted">{formatDate(app.applied_at)}</td>
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
