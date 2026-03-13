import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiRequest } from '../../utils/api.js'
import { tokenService } from '../../utils/tokenService.js'
import SuperAdminLayout from './SuperAdminLayout.jsx'
import { FiRefreshCw, FiFileText, FiSearch, FiDownload } from 'react-icons/fi'
import { generateApplicationsPdf } from '../../utils/pdfReportUtils.js'

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

function StatusBadge({ status }) {
  const map = {
    pending: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/20',
    shortlisted: 'bg-green-500/15 text-green-400 border-green-500/20',
    rejected: 'bg-red-500/15 text-red-400 border-red-500/20',
    reviewed: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border capitalize ${
        map[status] || 'bg-zinc-700/50 text-zinc-400 border-zinc-700'
      }`}
    >
      {status || 'pending'}
    </span>
  )
}

export default function SuperAdminApplications() {
  const navigate = useNavigate()
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
      const data = await apiRequest('/api/super-admin/applications', { method: 'GET', token })
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
    <SuperAdminLayout>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <FiFileText className="w-5 h-5 text-zinc-300" /> All Applications
          </h1>
          <p className="mt-0.5 text-sm text-zinc-400">
            {applications.length} total &bull; {shortlistedCount} shortlisted &bull; {pendingCount} pending
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-white bg-zinc-800 hover:bg-zinc-700 transition-colors border border-zinc-700"
          >
            <FiRefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button
            onClick={() => {
              setReportError('')
              try {
                generateApplicationsPdf(filtered.length ? filtered : applications)
              } catch (e) {
                console.error('PDF generation failed:', e)
                setReportError(e?.message || 'Failed to generate PDF')
              }
            }}
            disabled={applications.length === 0}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            <FiDownload className="w-4 h-4" /> Download Report
          </button>
        </div>
      </div>

      {reportError && (
        <div className="mb-4 px-4 py-2 rounded-lg bg-red-500/15 text-red-400 border border-red-500/30 text-sm">
          {reportError}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1">
          <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Search by candidate, job or admin…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-rose-500/50 transition-colors"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-sm text-zinc-300 focus:outline-none focus:border-rose-500/50 transition-colors"
        >
          <option value="all">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="shortlisted">Shortlisted</option>
          <option value="rejected">Rejected</option>
          <option value="reviewed">Reviewed</option>
        </select>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">{error}</div>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-zinc-900/60 border border-zinc-800 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-zinc-500 text-sm">
          {search || statusFilter !== 'all' ? 'No applications match your filters.' : 'No applications found.'}
        </div>
      ) : (
        <div className="rounded-2xl border border-zinc-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/80">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">#</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Candidate</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Job</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">HR Admin</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Match</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Applied</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {filtered.map((app) => (
                  <tr
                    key={app.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => navigate(`/super-admin/applications/${app.id}`)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/super-admin/applications/${app.id}`) } }}
                    className="bg-zinc-900/30 hover:bg-zinc-800/40 transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-inset focus:ring-rose-500/50"
                  >
                    <td className="px-4 py-3 text-zinc-600 text-xs font-mono">#{app.id}</td>
                    <td className="px-4 py-3">
                      <p className="text-zinc-100 font-medium">{app.candidate_name || '—'}</p>
                      <p className="text-zinc-500 text-xs">{app.candidate_email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-zinc-300 font-medium max-w-[160px] truncate">{app.job_title || '—'}</p>
                      <p className="text-zinc-500 text-xs">{app.job_company}</p>
                    </td>
                    <td className="px-4 py-3 text-zinc-400 text-xs">{app.hr_name || '—'}</td>
                    <td className="px-4 py-3">
                      {app.match_score != null ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-zinc-700 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-amber-500 to-green-500"
                              style={{ width: `${Math.min(100, app.match_score)}%` }}
                            />
                          </div>
                          <span className="text-xs text-zinc-400 tabular-nums">
                            {Math.round(app.match_score)}%
                          </span>
                        </div>
                      ) : (
                        <span className="text-zinc-600 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={app.shortlisted ? 'shortlisted' : app.status} />
                    </td>
                    <td className="px-4 py-3 text-zinc-500">{formatDate(app.applied_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </SuperAdminLayout>
  )
}
