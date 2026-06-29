import React, { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext.jsx'
import { apiRequest } from '../../utils/api.js'
import { tokenService } from '../../utils/tokenService.js'
import HeadHrLayout from './HeadHrLayout.jsx'
import { FiUsers, FiUser, FiBriefcase, FiFileText, FiCheckCircle, FiTrendingUp, FiBarChart2, FiPieChart, FiRefreshCw } from 'react-icons/fi'

function StatCard({ icon: Icon, label, value, accent, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`group text-left w-full rounded-2xl border bg-white dark:bg-slate-800/80 p-5 shadow-card hover:shadow-card-hover transition-all duration-200 ${
        accent === 'purple'
          ? 'border-primary/20 dark:border-accent-blue/30 hover:border-primary/40 dark:hover:border-accent-blue/50'
          : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
      }`}
    >
      <div className="flex items-start justify-between">
        <div
          className={`w-10 h-10 rounded-xl grid place-items-center ${
            accent === 'purple'
              ? 'bg-primary/10 dark:bg-accent-blue/20 text-primary dark:text-accent-blue'
              : accent === 'blue'
              ? 'bg-accent-blue/10 text-accent-blue'
              : accent === 'green'
              ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
              : accent === 'rose'
              ? 'bg-rose-500/15 text-rose-600 dark:text-rose-400'
              : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400'
          }`}
        >
          <Icon className="w-5 h-5" />
        </div>
        <FiTrendingUp className="w-4 h-4 text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300 transition-colors" />
      </div>
      <p className="mt-4 text-3xl font-bold text-slate-900 dark:text-white tabular-nums">{value ?? '—'}</p>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{label}</p>
    </button>
  )
}

function BarRow({ label, count, total, colorClass }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="text-sm text-slate-600 dark:text-slate-300 w-24 flex-shrink-0 capitalize">{label}</span>
      <div className="flex-1 h-6 rounded-md bg-slate-200 dark:bg-slate-700 overflow-hidden">
        <div
          className={`h-full rounded-md transition-all duration-500 ${colorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm text-slate-500 dark:text-slate-400 tabular-nums w-10 text-right">{count}</span>
    </div>
  )
}

export default function HeadHrDashboard() {
  const { auth } = useApp()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [applications, setApplications] = useState([])
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const load = React.useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    try {
      setError('')
      const token = tokenService.getToken()
      const [statsRes, appsRes, jobsRes] = await Promise.all([
        apiRequest('/api/head-hr/stats', { method: 'GET', token }),
        apiRequest('/api/head-hr/applications', { method: 'GET', token }),
        apiRequest('/api/head-hr/jobs', { method: 'GET', token }),
      ])
      setStats(statsRes)
      setApplications(appsRes.applications || [])
      setJobs(jobsRes.jobs || [])
    } catch (err) {
      setError(err?.message || 'Failed to load stats')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Refresh when user returns to the tab so dashboard is always up to date
  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') load(true)
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    return () => document.removeEventListener('visibilitychange', onVisibilityChange)
  }, [load])

  const analytics = useMemo(() => {
    const apps = applications
    const total = apps.length
    const byStatus = { applied: 0, shortlisted: 0, rejected: 0, reviewed: 0 }
    let scoreSum = 0
    let scoreCount = 0
    const scoreBuckets = { high: 0, medium: 0, low: 0 }
    const byJob = {}

    // Normalize DB status to dashboard keys (no "pending" - we only use applied, reviewed, shortlisted, rejected)
    const normalizeStatus = (a) => {
      if (a.shortlisted === true || a.shortlisted === 1) return 'shortlisted'
      const raw = String(a.status ?? a.Status ?? 'applied').toLowerCase().trim()
      if (raw === 'profile_viewed') return 'reviewed'
      if (raw === 'rejected' || raw === 'not_shortlisted') return 'rejected'
      if (raw === 'shortlisted') return 'shortlisted'
      if (raw === 'reviewed') return 'reviewed'
      return 'applied'
    }

    apps.forEach((a) => {
      const status = normalizeStatus(a)
      byStatus[status] = (byStatus[status] || 0) + 1
      const jobId = a.job_id || a.jobId
      if (jobId) {
        if (!byJob[jobId]) byJob[jobId] = { count: 0, shortlisted: 0, reviewed: 0, rejected: 0, scoreSum: 0, scoreN: 0 }
        byJob[jobId].count += 1
        if (a.shortlisted) byJob[jobId].shortlisted += 1
        if (status === 'reviewed') byJob[jobId].reviewed += 1
        if (status === 'rejected') byJob[jobId].rejected += 1
        const score = a.match_score != null ? Number(a.match_score) : null
        if (score != null && !Number.isNaN(score)) {
          byJob[jobId].scoreSum += score
          byJob[jobId].scoreN += 1
        }
      }
      const score = a.match_score != null ? Number(a.match_score) : null
      if (score != null && !Number.isNaN(score)) {
        scoreSum += score
        scoreCount += 1
        if (score >= 60) scoreBuckets.high += 1
        else if (score >= 30) scoreBuckets.medium += 1
        else scoreBuckets.low += 1
      }
    })

    const jobTitleById = {}
    jobs.forEach((j) => { jobTitleById[j.jdid] = j.title || j.jdid })
    const topJobs = Object.entries(byJob)
      .map(([id, data]) => ({
        id,
        title: jobTitleById[id] || id,
        count: data.count,
        shortlisted: data.shortlisted,
        reviewed: data.reviewed || 0,
        rejected: data.rejected || 0,
        avgScore: data.scoreN > 0 ? Math.round((data.scoreSum / data.scoreN) * 10) / 10 : null,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6)

    const avgScore = scoreCount > 0 ? Math.round((scoreSum / scoreCount) * 10) / 10 : null
    const shortlistedCount = byStatus.shortlisted || 0
    const shortlistRate = total > 0 ? Math.round((shortlistedCount / total) * 100) : 0

    return {
      byStatus,
      total,
      avgScore,
      scoreBuckets,
      scoreCount,
      topJobs,
      shortlistRate,
    }
  }, [applications, jobs])

  return (
    <HeadHrLayout>
      {/* Page header */}
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">System Overview</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Full-access dashboard — logged in as{' '}
            <span className="text-zinc-200 font-medium">{auth?.email}</span>
          </p>
        </div>
        <button
          type="button"
          onClick={() => load(true)}
          disabled={refreshing || loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl border border-zinc-600 hover:border-zinc-500 bg-zinc-800/60 hover:bg-zinc-700/60 text-zinc-300 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <FiRefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 animate-pulse">
              <div className="w-10 h-10 rounded-xl bg-zinc-800" />
              <div className="mt-4 h-8 w-16 rounded bg-zinc-800" />
              <div className="mt-2 h-4 w-28 rounded bg-zinc-800" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          <StatCard
            icon={FiUsers}
            label="Total HR Admins"
            value={stats?.totalAdmins}
            accent="purple"
            onClick={() => navigate('/head-hr/admins')}
          />
          <StatCard
            icon={FiUser}
            label="Total Candidates"
            value={stats?.totalCandidates}
            accent="blue"
            onClick={() => navigate('/head-hr/candidates')}
          />
          <StatCard
            icon={FiBriefcase}
            label="Total Jobs"
            value={stats?.totalJobs}
            accent="purple"
            onClick={() => navigate('/head-hr/jobs')}
          />
          <StatCard
            icon={FiBriefcase}
            label="Active Jobs"
            value={stats?.activeJobs}
            accent="green"
            onClick={() => navigate('/head-hr/jobs')}
          />
          <StatCard
            icon={FiFileText}
            label="Total Applications"
            value={stats?.totalApplications}
            accent="rose"
            onClick={() => navigate('/head-hr/applications')}
          />
          <StatCard
            icon={FiCheckCircle}
            label="Shortlisted"
            value={stats?.shortlistedApplications}
            accent="green"
            onClick={() => navigate('/head-hr/applications')}
          />
        </div>
      )}

      {/* Analytics */}
      {!loading && (
        <div className="mt-10 space-y-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <FiBarChart2 className="w-5 h-5 text-purple-400" /> Analytics
          </h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Application status breakdown */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
              <h3 className="text-sm font-semibold text-zinc-300 flex items-center gap-2 mb-4">
                <FiPieChart className="w-4 h-4" /> Applications by status
              </h3>
              <div className="space-y-1">
                {[
                  { key: 'shortlisted', label: 'Shortlisted', color: 'bg-green-500' },
                  { key: 'applied', label: 'Applied', color: 'bg-blue-500' },
                  { key: 'reviewed', label: 'Reviewed', color: 'bg-purple-500' },
                  { key: 'rejected', label: 'Rejected', color: 'bg-red-500' },
                ].map(({ key, label, color }) => (
                  <BarRow
                    key={key}
                    label={label}
                    count={analytics.byStatus[key] || 0}
                    total={analytics.total}
                    colorClass={color}
                  />
                ))}
              </div>
              {analytics.total === 0 && (
                <p className="text-sm text-zinc-500 py-4">No applications yet</p>
              )}
            </div>

            {/* Match score & shortlist rate */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
              <h3 className="text-sm font-semibold text-zinc-300 mb-4">Match score & shortlist rate</h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="rounded-xl bg-zinc-800/50 p-4 border border-zinc-700/50">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider">Avg. match score</p>
                  <p className="text-2xl font-bold text-white mt-1 tabular-nums">
                    {analytics.avgScore != null ? `${analytics.avgScore}%` : '—'}
                  </p>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {analytics.scoreCount} with score
                  </p>
                </div>
                <div className="rounded-xl bg-zinc-800/50 p-4 border border-zinc-700/50">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider">Shortlist rate</p>
                  <p className="text-2xl font-bold text-green-400 mt-1 tabular-nums">{analytics.shortlistRate}%</p>
                  <p className="text-xs text-zinc-500 mt-0.5">of applications</p>
                </div>
              </div>
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Score distribution</p>
                <div className="flex gap-2">
                  <div className="flex-1 rounded-lg overflow-hidden bg-zinc-800 h-8 flex">
                    <div
                      className="bg-red-500/80 transition-all duration-500"
                      style={{ width: `${analytics.scoreCount ? (analytics.scoreBuckets.low / analytics.scoreCount) * 100 : 0}%` }}
                    />
                    <div
                      className="bg-amber-500/80 transition-all duration-500"
                      style={{ width: `${analytics.scoreCount ? (analytics.scoreBuckets.medium / analytics.scoreCount) * 100 : 0}%` }}
                    />
                    <div
                      className="bg-green-500/80 transition-all duration-500"
                      style={{ width: `${analytics.scoreCount ? (analytics.scoreBuckets.high / analytics.scoreCount) * 100 : 0}%` }}
                    />
                  </div>
                </div>
                <div className="flex gap-4 mt-2 text-xs text-zinc-500">
                  <span><span className="inline-block w-2 h-2 rounded bg-red-500/80 mr-1" /> Low (&lt;30%)</span>
                  <span><span className="inline-block w-2 h-2 rounded bg-amber-500/80 mr-1" /> Medium (30–60%)</span>
                  <span><span className="inline-block w-2 h-2 rounded bg-green-500/80 mr-1" /> High (60%+)</span>
                </div>
              </div>
            </div>
          </div>

          {/* Job-level insight: applications, shortlisted, avg match */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
            <h3 className="text-sm font-semibold text-zinc-300 mb-1">Job-level insight</h3>
            <p className="text-xs text-zinc-500 mb-4">Applications, shortlisted count, and average match score per job. Click a job to view its full description.</p>
            {analytics.topJobs.length > 0 ? (
              <div className="space-y-2">
                {analytics.topJobs.map(({ id, title, count, shortlisted, reviewed, rejected, avgScore }) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => navigate(`/head-hr/jobs/${encodeURIComponent(id)}`)}
                    className="w-full flex flex-wrap items-center gap-x-4 gap-y-1 py-3 px-3 rounded-xl bg-zinc-800/50 border border-zinc-700/50 hover:border-purple-500/30 hover:bg-zinc-800 transition-colors text-left"
                  >
                    <span className="text-sm font-medium text-zinc-200 truncate flex-1 min-w-0">{title || id}</span>
                    <span className="text-xs text-zinc-400 tabular-nums">
                      <span className="text-zinc-300">{count}</span> applied
                      {(reviewed || 0) > 0 && <span className="text-amber-400 ml-2">{reviewed} reviewed</span>}
                      {shortlisted > 0 && <span className="text-green-400 ml-2">{shortlisted} shortlisted</span>}
                      {(rejected || 0) > 0 && <span className="text-red-400 ml-2">{rejected} rejected</span>}
                      {avgScore != null && <span className="text-purple-400 ml-2">avg {avgScore}% match</span>}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-500 py-4">No applications yet</p>
            )}
          </div>
        </div>
      )}
    </HeadHrLayout>
  )
}
