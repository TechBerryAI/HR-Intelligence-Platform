import React, { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { useOrgPanel } from '@/core/context/OrgPanelContext.jsx'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import { FiUsers, FiUser, FiBriefcase, FiFileText, FiCheckCircle, FiTrendingUp, FiBarChart2, FiPieChart, FiRefreshCw } from 'react-icons/fi'
import RecruiterJobDashboard from '@/features/dashboard/components/recruiter/RecruiterJobDashboard.jsx'

const ACCENT_ICON = {
  purple: 'bg-[rgba(121,87,255,0.15)] text-[#A78BFA]',
  blue: 'bg-[rgba(0,166,255,0.12)] text-[#00A6FF]',
  green: 'bg-[rgba(54,214,160,0.12)] text-[#36D6A0]',
  rose: 'bg-[rgba(255,102,133,0.12)] text-[#FF6685]',
  teal: 'bg-[rgba(45,212,191,0.12)] text-[#2DD4BF]',
  slate: 'bg-[rgba(156,168,181,0.12)] text-[#9CA8B5]',
}

function StatCard({ icon: Icon, label, value, accent, onClick, disabled, compact = false }) {
  const className = `org-glass-card group text-left w-full ${
    compact ? 'p-3.5' : 'p-5'
  } ${disabled ? 'cursor-default hover:transform-none' : 'cursor-pointer'}`

  const iconWrap = (
    <div
      className={`rounded-xl grid place-items-center flex-shrink-0 ${
        compact ? 'w-9 h-9' : 'w-10 h-10'
      } ${ACCENT_ICON[accent] || ACCENT_ICON.slate}`}
    >
      <Icon className={compact ? 'w-4 h-4' : 'w-5 h-5'} />
    </div>
  )

  const inner = compact ? (
    <div className="flex items-center gap-3">
      {iconWrap}
      <div className="min-w-0 flex-1">
        <p className="text-xl font-bold text-[#F5F7FA] tabular-nums leading-tight">{value ?? '—'}</p>
        <p className="text-xs text-[#8E9BA8] truncate">{label}</p>
      </div>
      {!disabled && onClick && (
        <FiTrendingUp className="w-3.5 h-3.5 text-[#71808E] group-hover:text-[#00A6FF] transition-colors flex-shrink-0" />
      )}
    </div>
  ) : (
    <>
      <div className="flex items-start justify-between">
        {iconWrap}
        {!disabled && <FiTrendingUp className="w-4 h-4 text-[#71808E] group-hover:text-[#00A6FF] transition-colors" />}
      </div>
      <p className="mt-4 text-3xl font-bold text-[#F5F7FA] tabular-nums">{value ?? '—'}</p>
      <p className="mt-1 text-sm text-[#8E9BA8]">{label}</p>
    </>
  )
  if (disabled || !onClick) {
    return <div className={className}>{inner}</div>
  }
  return (
    <button type="button" onClick={onClick} className={className}>
      {inner}
    </button>
  )
}

function BarRow({ label, count, total, colorClass }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="text-sm text-[#A0ABB6] w-24 flex-shrink-0 capitalize">{label}</span>
      <div className="flex-1 h-6 rounded-md bg-white/[0.06] overflow-hidden">
        <div className={`h-full rounded-md transition-all duration-500 ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm text-[#8E9BA8] tabular-nums w-10 text-right">{count}</span>
    </div>
  )
}

export default function OrgOverviewDashboard({ variant = 'head-hr', showJobPosting = false }) {
  const { auth } = useApp()
  const { basePath, readOnly } = useOrgPanel()
  const navigate = useNavigate()
  const isCeo = variant === 'ceo' || readOnly
  const showAnalytics = isCeo
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
      const statsRes = await apiRequest('/api/head-hr/stats', { method: 'GET', token })
      setStats(statsRes)
      if (showAnalytics) {
        const [appsRes, jobsRes] = await Promise.all([
          apiRequest('/api/head-hr/applications', { method: 'GET', token }),
          apiRequest('/api/head-hr/jobs', { method: 'GET', token }),
        ])
        setApplications(appsRes.applications || [])
        setJobs(jobsRes.jobs || [])
      } else {
        setApplications([])
        setJobs([])
      }
    } catch (err) {
      setError(err?.message || 'Failed to load stats')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [showAnalytics])

  useEffect(() => {
    load()
  }, [load])

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

    return { byStatus, total, avgScore, scoreBuckets, scoreCount, topJobs, shortlistRate }
  }, [applications, jobs])

  const go = (segment) => {
    if (segment) navigate(`${basePath}/${segment}`)
    else navigate(basePath)
  }

  const statItems = [
    {
      icon: FiUsers,
      label: isCeo ? 'HR Team Members' : 'Total HR Admins',
      value: stats?.totalAdmins,
      accent: 'slate',
      disabled: isCeo,
      onClick: isCeo ? undefined : () => go('admins'),
    },
    { icon: FiUser, label: 'Total Candidates', value: stats?.totalCandidates, accent: 'blue', onClick: () => go('jobs') },
    { icon: FiBriefcase, label: 'Total Jobs', value: stats?.totalJobs, accent: 'purple', onClick: () => go('jobs') },
    { icon: FiBriefcase, label: 'Active Jobs', value: stats?.activeJobs, accent: 'green', onClick: () => go('jobs') },
    { icon: FiFileText, label: 'Total Applications', value: stats?.totalApplications, accent: 'rose', onClick: () => go('jobs') },
    { icon: FiCheckCircle, label: 'Shortlisted', value: stats?.shortlistedApplications, accent: 'teal', onClick: () => go('jobs') },
  ]

  const renderStatCards = (compact = false) =>
    statItems.map(({ icon, label, value, accent, disabled, onClick }) => (
      <StatCard
        key={label}
        icon={icon}
        label={label}
        value={value}
        accent={accent}
        disabled={disabled}
        onClick={onClick}
        compact={compact}
      />
    ))

  const renderStatsSidebar = () => (
    <aside className="org-glass-panel p-[18px]">
      <h2 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#83909C] mb-3 px-0.5">
        Organization Snapshot
      </h2>
      <div className="space-y-2">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-14 rounded-[14px] border border-white/[0.08] bg-white/[0.035] animate-pulse" />
            ))
          : renderStatCards(true)}
      </div>
      {!loading && !isCeo && (
        <p className="mt-4 text-xs text-[#71808E] leading-relaxed px-0.5">
          CEO accounts are excluded from HR admin totals. Tap a metric to jump to the relevant section.
        </p>
      )}
    </aside>
  )

  return (
    <>
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="org-page-title">
            {isCeo ? 'Executive Dashboard' : 'Admin Dashboard'}
          </h1>
          <p className="org-page-subtitle">
            {isCeo
              ? 'Read-only company analytics'
              : showJobPosting
              ? 'Post jobs and monitor organization health'
              : 'Organization administration'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {auth?.email && (
            <span className="org-account-pill">
              <span className="text-[#00A6FF] font-semibold">{isCeo ? 'Exec' : 'Admin'}</span>
              <span className="text-white/25">•</span>
              <span className="truncate max-w-[220px]">{auth.email}</span>
            </span>
          )}
          <button
            type="button"
            onClick={() => load(true)}
            disabled={refreshing || loading}
            className="org-btn-ghost"
          >
            <FiRefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div className="org-error-banner mb-6 flex items-center gap-2">
          {error}
        </div>
      )}

      {!showJobPosting && loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="org-glass-card p-5 animate-pulse hover:transform-none">
              <div className="w-10 h-10 rounded-xl bg-white/[0.06]" />
              <div className="mt-4 h-8 w-16 rounded bg-white/[0.06]" />
              <div className="mt-2 h-4 w-28 rounded bg-white/[0.06]" />
            </div>
          ))}
        </div>
      )}

      {!showJobPosting && !loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {renderStatCards(false)}
        </div>
      )}

      {showJobPosting && (
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(260px,320px)] gap-7 items-start">
          <div className="min-w-0">
            <RecruiterJobDashboard embedded onJobChange={() => load(true)} />
          </div>
          <div className="lg:sticky lg:top-6">
            {renderStatsSidebar()}
          </div>
        </div>
      )}

      {!loading && !showAnalytics && !showJobPosting && (
        <div className="mt-10 org-card p-5">
          <h2 className="text-sm font-semibold text-[#DCE3EA] mb-2">Quick access</h2>
          <p className="text-sm text-[#8E9BA8] mb-4">
            Use the sidebar to manage HR admins, jobs, and platform settings.
            Open a job to review candidates who applied and their match scores.
          </p>
          <div className="flex flex-wrap gap-2">
            {[
              { label: 'HR Admins', segment: 'admins' },
              { label: 'Jobs', segment: 'jobs' },
              ...(isCeo ? [] : [{ label: 'Settings', segment: 'settings' }]),
            ].map(({ label, segment }) => (
              <button
                key={segment}
                type="button"
                onClick={() => go(segment)}
                className="org-btn-ghost"
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {!loading && showAnalytics && (
        <div className="mt-10 space-y-6">
          <h2 className="text-lg font-semibold text-[#F5F7FA] flex items-center gap-2">
            <FiBarChart2 className="w-5 h-5 text-[#00A6FF]" /> Analytics
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="org-card p-5">
              <h3 className="text-sm font-semibold text-[#DCE3EA] flex items-center gap-2 mb-4">
                <FiPieChart className="w-4 h-4" /> Applications by status
              </h3>
              <div className="space-y-1">
                {[
                  { key: 'shortlisted', label: 'Shortlisted', color: 'bg-emerald-500' },
                  { key: 'applied', label: 'Applied', color: 'bg-sky-500' },
                  { key: 'reviewed', label: 'Reviewed', color: 'bg-violet-500' },
                  { key: 'rejected', label: 'Rejected', color: 'bg-rose-500' },
                ].map(({ key, label, color }) => (
                  <BarRow key={key} label={label} count={analytics.byStatus[key] || 0} total={analytics.total} colorClass={color} />
                ))}
              </div>
              {analytics.total === 0 && <p className="text-sm text-[#71808E] py-4">No applications yet</p>}
            </div>
            <div className="org-card p-5">
              <h3 className="text-sm font-semibold text-[#DCE3EA] mb-4">Match score & shortlist rate</h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="rounded-xl bg-white/[0.035] p-4 border border-white/[0.08]">
                  <p className="text-xs text-[#83909C] uppercase tracking-wider">Avg. match score</p>
                  <p className="text-2xl font-bold text-[#F5F7FA] mt-1 tabular-nums">{analytics.avgScore != null ? `${analytics.avgScore}%` : '—'}</p>
                  <p className="text-xs text-[#71808E] mt-0.5">{analytics.scoreCount} with score</p>
                </div>
                <div className="rounded-xl bg-white/[0.035] p-4 border border-white/[0.08]">
                  <p className="text-xs text-[#83909C] uppercase tracking-wider">Shortlist rate</p>
                  <p className="text-2xl font-bold text-[#36D6A0] mt-1 tabular-nums">{analytics.shortlistRate}%</p>
                  <p className="text-xs text-[#71808E] mt-0.5">of applications</p>
                </div>
              </div>
              <div>
                <p className="text-xs text-[#83909C] uppercase tracking-wider mb-2">Score distribution</p>
                <div className="flex gap-2">
                  <div className="flex-1 rounded-lg overflow-hidden bg-white/[0.06] h-8 flex">
                    <div className="bg-red-500/80 transition-all duration-500" style={{ width: `${analytics.scoreCount ? (analytics.scoreBuckets.low / analytics.scoreCount) * 100 : 0}%` }} />
                    <div className="bg-amber-500/80 transition-all duration-500" style={{ width: `${analytics.scoreCount ? (analytics.scoreBuckets.medium / analytics.scoreCount) * 100 : 0}%` }} />
                    <div className="bg-green-500/80 transition-all duration-500" style={{ width: `${analytics.scoreCount ? (analytics.scoreBuckets.high / analytics.scoreCount) * 100 : 0}%` }} />
                  </div>
                </div>
                <div className="flex gap-4 mt-2 text-xs text-[#71808E]">
                  <span><span className="inline-block w-2 h-2 rounded bg-red-500/80 mr-1" /> Low (&lt;30%)</span>
                  <span><span className="inline-block w-2 h-2 rounded bg-amber-500/80 mr-1" /> Medium (30–60%)</span>
                  <span><span className="inline-block w-2 h-2 rounded bg-green-500/80 mr-1" /> High (60%+)</span>
                </div>
              </div>
            </div>
          </div>
          <div className="org-card p-5">
            <h3 className="text-sm font-semibold text-[#DCE3EA] mb-1">Job-level insight</h3>
            <p className="text-xs text-[#71808E] mb-4">Applications, shortlisted count, and average match score per job.</p>
            {analytics.topJobs.length > 0 ? (
              <div className="space-y-2">
                {analytics.topJobs.map(({ id, title, count, shortlisted, reviewed, rejected, avgScore }) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => navigate(`${basePath}/jobs/${encodeURIComponent(id)}?tab=candidates`)}
                    className="w-full flex flex-wrap items-center gap-x-4 gap-y-1 py-3 px-3 rounded-xl bg-white/[0.035] border border-white/[0.08] hover:border-[rgba(0,166,255,0.3)] hover:bg-white/[0.05] transition-all duration-[180ms] text-left"
                  >
                    <span className="text-sm font-medium text-[#F5F7FA] truncate flex-1 min-w-0">{title || id}</span>
                    <span className="text-xs text-[#8E9BA8] tabular-nums">
                      <span className="text-[#DCE3EA]">{count}</span> applied
                      {(reviewed || 0) > 0 && <span className="text-amber-400 ml-2">{reviewed} reviewed</span>}
                      {shortlisted > 0 && <span className="text-[#36D6A0] ml-2">{shortlisted} shortlisted</span>}
                      {(rejected || 0) > 0 && <span className="text-[#FF6685] ml-2">{rejected} rejected</span>}
                      {avgScore != null && <span className="text-[#A78BFA] ml-2">avg {avgScore}% match</span>}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[#71808E] py-4">No applications yet</p>
            )}
          </div>
        </div>
      )}
    </>
  )
}
