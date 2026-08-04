import React, { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOrgPanel } from '@/core/context/OrgPanelContext.jsx'
import { useApp } from '@/core/context/AppContext.jsx'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import { FiUsers, FiUser, FiBriefcase, FiFileText, FiCheckCircle, FiTrendingUp, FiBarChart2, FiPieChart, FiArrowRight, FiEdit2, FiX } from 'react-icons/fi'
import { LayoutDashboard, Home, RefreshCw } from 'lucide-react'
import RecruiterJobDashboard from '@/features/dashboard/components/recruiter/RecruiterJobDashboard.jsx'
import PremiumInput from '@/shared/components/PremiumInput.jsx'
import PremiumButton from '@/shared/components/PremiumButton.jsx'
import ThemeToggle from '@/shared/components/ThemeToggle.jsx'

const ACCENT_ICON = {
  purple: 'bg-[rgba(121,87,255,0.15)] text-[#A78BFA]',
  blue: 'bg-[rgba(0,166,255,0.12)] text-[#00A6FF]',
  green: 'bg-[rgba(54,214,160,0.12)] text-[#36D6A0]',
  rose: 'bg-[rgba(255,102,133,0.12)] text-[#FF6685]',
  teal: 'bg-[rgba(45,212,191,0.12)] text-[#2DD4BF]',
  slate: 'bg-[rgba(156,168,181,0.12)] text-[#9CA8B5]',
}

function parseExperienceRange(experience) {
  const raw = String(experience || '').trim()
  if (!raw) return { from: '', to: '' }
  const range = raw.match(/(\d+(?:\.\d+)?)\s*[-–—to]+\s*(\d+(?:\.\d+)?)/i)
  if (range) return { from: range[1], to: range[2] }
  const single = raw.match(/(\d+(?:\.\d+)?)/)
  return { from: single ? single[1] : '', to: '' }
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
        <p className="text-xl font-bold text-[var(--ei-text-primary)] tabular-nums leading-tight">{value ?? '—'}</p>
        <p className="text-xs text-[var(--ei-text-secondary)] truncate">{label}</p>
      </div>
      {!disabled && onClick && (
        <FiTrendingUp className="w-3.5 h-3.5 text-[var(--ei-text-muted)] group-hover:text-[#00A6FF] transition-colors flex-shrink-0" />
      )}
    </div>
  ) : (
    <>
      <div className="flex items-start justify-between">
        {iconWrap}
        {!disabled && <FiTrendingUp className="w-4 h-4 text-[var(--ei-text-muted)] group-hover:text-[#00A6FF] transition-colors" />}
      </div>
      <p className="mt-4 text-3xl font-bold text-[var(--ei-text-primary)] tabular-nums">{value ?? '—'}</p>
      <p className="mt-1 text-sm text-[var(--ei-text-secondary)]">{label}</p>
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
      <span className="text-sm text-[var(--ei-text-secondary)] w-24 flex-shrink-0 capitalize">{label}</span>
      <div className="flex-1 h-6 rounded-md bg-white/[0.06] overflow-hidden">
        <div className={`h-full rounded-md transition-all duration-500 ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm text-[var(--ei-text-secondary)] tabular-nums w-10 text-right">{count}</span>
    </div>
  )
}

export default function OrgOverviewDashboard({ variant = 'head-hr', showJobPosting = false }) {
  const { basePath, readOnly } = useOrgPanel()
  const { setJobEnabled, updateJob } = useApp()
  const navigate = useNavigate()
  const isCeo = variant === 'ceo' || readOnly
  const showAnalytics = isCeo
  const [stats, setStats] = useState(null)
  const [applications, setApplications] = useState([])
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
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
  const [actionMessage, setActionMessage] = useState('')

  const load = React.useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    try {
      setError('')
      const token = tokenService.getToken()
      const statsRes = await apiRequest('/api/head-hr/stats', { method: 'GET', token })
      setStats(statsRes)
      // Jobs + applications for CEO analytics and Head HR overview (recent jobs / activity)
      if (showAnalytics || showJobPosting) {
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
  }, [showAnalytics, showJobPosting])

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

  const draftJobsCount = Math.max(0, (stats?.totalJobs ?? 0) - (stats?.activeJobs ?? 0))

  const appsByJobId = useMemo(() => {
    const map = {}
    applications.forEach((a) => {
      const id = String(a.job_id || a.jobId || '')
      if (!id) return
      map[id] = (map[id] || 0) + 1
    })
    return map
  }, [applications])

  const recentJobs = useMemo(() => {
    return [...jobs]
      .sort((a, b) => new Date(b.posted_on || 0) - new Date(a.posted_on || 0))
      .slice(0, 5)
  }, [jobs])

  const recentActivity = useMemo(() => {
    const items = []
    applications.forEach((a) => {
      const ts = a.applied_at || a.created_at
      if (!ts) return
      items.push({
        id: `app-${a.id || a.application_id}-${ts}`,
        at: new Date(ts).getTime(),
        text: a.candidate_name
          ? `${a.candidate_name} applied${a.job_title ? ` to ${a.job_title}` : ''}`
          : 'New candidate applied',
      })
    })
    jobs.forEach((j) => {
      const ts = j.posted_on || j.created_at
      if (!ts) return
      items.push({
        id: `job-${j.jdid || j.id}-${ts}`,
        at: new Date(ts).getTime(),
        text: j.enabled === false
          ? `Job draft/disabled: ${j.title || 'Untitled'}`
          : `Job posted: ${j.title || 'Untitled'}`,
      })
    })
    return items.sort((a, b) => b.at - a.at).slice(0, 6)
  }, [applications, jobs])

  const formatShortDate = (ts) => {
    if (!ts) return '—'
    return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const flashAction = (msg) => {
    setActionMessage(msg)
    setTimeout(() => setActionMessage(''), 2500)
  }

  const handleToggleEnabled = async (job, nextEnabled) => {
    const jdid = job.jdid || job.id
    if (!jdid || togglingJobId) return
    setTogglingJobId(jdid)
    const prevEnabled = job.enabled !== false
    setJobs((prev) =>
      prev.map((j) => ((j.jdid || j.id) === jdid ? { ...j, enabled: nextEnabled } : j)),
    )
    try {
      const token = tokenService.getToken()
      await apiRequest(`/api/jobs/${encodeURIComponent(jdid)}/enabled`, {
        method: 'PATCH',
        body: { enabled: nextEnabled },
        token,
      })
      await setJobEnabled(jdid, nextEnabled)
      flashAction(nextEnabled ? 'Job enabled' : 'Job disabled (draft)')
      await load(true)
    } catch (err) {
      setJobs((prev) =>
        prev.map((j) => ((j.jdid || j.id) === jdid ? { ...j, enabled: prevEnabled } : j)),
      )
      setError(err?.data?.error || err?.message || 'Failed to update job status')
    } finally {
      setTogglingJobId(null)
    }
  }

  const openEditJob = async (job) => {
    const jdid = job.jdid || job.id
    setEditError('')
    setEditingJob({ jdid, title: job.title })
    setEditTitle(job.title || '')
    setEditLocation(job.location || '')
    setEditSalary(job.salary || '')
    const parsed = parseExperienceRange(job.experience)
    setEditExperienceFrom(job.experienceFrom || parsed.from)
    setEditExperienceTo(job.experienceTo || parsed.to)
    setEditDescription(job.description || '')
    try {
      const token = tokenService.getToken()
      const detail = await apiRequest(`/api/head-hr/jobs/${encodeURIComponent(jdid)}`, {
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
      // Keep list-row fields if detail fetch fails
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
      flashAction('Job updated')
      setEditingJob(null)
      await load(true)
    } catch (err) {
      setEditError(err?.data?.error || err?.message || 'Failed to update job')
    } finally {
      setEditSaving(false)
    }
  }

  const overviewMetrics = [
    {
      label: 'Active Jobs',
      value: stats?.activeJobs,
      onClick: () => go('jobs'),
    },
    {
      label: 'Candidates',
      value: stats?.totalCandidates,
      onClick: () => go('candidates'),
    },
    {
      label: 'HR Admins',
      value: stats?.totalAdmins,
      disabled: isCeo,
      onClick: isCeo ? undefined : () => go('admins'),
    },
    {
      label: 'Draft Jobs',
      value: draftJobsCount,
      onClick: () => go('jobs'),
    },
  ]

  const snapshotItems = [
    { label: 'Active Jobs', value: stats?.activeJobs },
    { label: 'Candidates', value: stats?.totalCandidates },
    { label: 'HR Admins', value: stats?.totalAdmins },
    { label: 'Total Jobs', value: stats?.totalJobs },
    { label: 'Applications', value: stats?.totalApplications },
    { label: 'Shortlisted', value: stats?.shortlistedApplications },
  ]

  const statItems = [
    {
      icon: FiUsers,
      label: isCeo ? 'HR Team Members' : 'Total HR Admins',
      value: stats?.totalAdmins,
      accent: 'slate',
      disabled: isCeo,
      onClick: isCeo ? undefined : () => go('admins'),
    },
    { icon: FiUser, label: 'Total Candidates', value: stats?.totalCandidates, accent: 'blue', onClick: () => go('candidates') },
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

  return (
    <>
      {actionMessage && (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 z-[180] -translate-x-1/2 rounded-xl border border-[rgba(54,214,160,0.35)] bg-[rgba(16,24,32,0.95)] px-4 py-2.5 text-sm font-medium text-[#67DFB4] shadow-[0_12px_40px_rgba(0,0,0,0.45)] backdrop-blur-md pointer-events-none"
        >
          {actionMessage}
        </div>
      )}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="org-page-title flex items-center gap-2.5">
            <LayoutDashboard size={32} className="org-page-icon" />
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
          <button
            type="button"
            onClick={() => navigate('/')}
            className="org-btn-ghost"
          >
            <Home className="w-4 h-4" strokeWidth={2} />
            Home
          </button>
          <ThemeToggle variant="org" />
          <button
            type="button"
            onClick={() => load(true)}
            disabled={refreshing || loading}
            className="org-btn-ghost"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} strokeWidth={2} />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div className="org-error-banner mb-6 flex items-center gap-2">
          {error}
        </div>
      )}

      {showJobPosting && (
        <div className="mb-7 grid grid-cols-2 lg:grid-cols-4 gap-3">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-[72px] rounded-[14px] border border-[var(--ei-border-primary)] bg-white/[0.035] animate-pulse" />
              ))
            : overviewMetrics.map(({ label, value, onClick, disabled }) => {
                const className = `org-glass-card text-left p-4 ${disabled ? 'cursor-default' : 'cursor-pointer'}`
                const inner = (
                  <>
                    <p className="text-2xl font-bold text-[var(--ei-text-primary)] tabular-nums leading-none">{value ?? '—'}</p>
                    <p className="mt-2 text-xs font-medium text-[var(--ei-text-secondary)]">{label}</p>
                  </>
                )
                if (disabled || !onClick) {
                  return <div key={label} className={className}>{inner}</div>
                }
                return (
                  <button key={label} type="button" onClick={onClick} className={className}>
                    {inner}
                  </button>
                )
              })}
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
        <div className="space-y-7">
          <div id="job-posting-section" className="scroll-mt-6">
            <RecruiterJobDashboard embedded hideJobList onJobChange={() => load(true)} />
          </div>

          <section className="org-glass-panel p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div>
                <h2 className="font-display text-[18px] font-semibold text-[var(--ei-text-primary)] tracking-tight">
                  Recent / Active Jobs
                </h2>
                <p className="mt-0.5 text-sm text-[var(--ei-text-secondary)]">Latest postings across the organization</p>
              </div>
              <button
                type="button"
                onClick={() => go('jobs')}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-[#55B9FF] hover:text-white transition-colors"
              >
                View all jobs
                <FiArrowRight className="w-4 h-4" />
              </button>
            </div>

            {loading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-12 rounded-xl bg-white/[0.04] animate-pulse" />
                ))}
              </div>
            ) : recentJobs.length === 0 ? (
              <p className="text-sm text-[var(--ei-text-muted)] py-6 text-center">No jobs yet. Create one above.</p>
            ) : (
              <div className="overflow-x-auto -mx-1">
                <table className="w-full min-w-[720px] text-left">
                  <thead>
                    <tr className="border-b border-[var(--ei-border-primary)] text-[11px] uppercase tracking-[0.08em] text-[#738394]">
                      <th className="pb-3 pr-4 font-semibold">Job</th>
                      <th className="pb-3 pr-4 font-semibold">Status</th>
                      <th className="pb-3 pr-4 font-semibold">Candidates</th>
                      <th className="pb-3 pr-4 font-semibold">Posted</th>
                      {!isCeo && <th className="pb-3 font-semibold text-right">Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {recentJobs.map((job) => {
                      const jdid = job.jdid || job.id
                      const count = appsByJobId[String(jdid)] || 0
                      const active = job.enabled !== false
                      return (
                        <tr
                          key={jdid}
                          className="border-b border-white/[0.05] last:border-0 hover:bg-white/[0.03] transition-colors"
                        >
                          <td
                            className="py-3.5 pr-4 text-sm font-medium text-[#F2F5F8] cursor-pointer"
                            onClick={() => navigate(`${basePath}/jobs/${encodeURIComponent(jdid)}`)}
                          >
                            {job.title || '—'}
                          </td>
                          <td className="py-3.5 pr-4">
                            <span
                              className={`inline-flex items-center justify-center min-w-[4.25rem] rounded-full px-2.5 py-0.5 text-xs font-medium ${
                                active
                                  ? 'bg-[rgba(54,214,160,0.12)] text-[#67DFB4]'
                                  : 'bg-white/[0.06] text-[var(--ei-text-secondary)]'
                              }`}
                            >
                              {active ? 'Active' : 'Draft'}
                            </span>
                          </td>
                          <td className="py-3.5 pr-4 text-sm tabular-nums text-[var(--ei-text-secondary)]">
                            {count > 0 ? count : '—'}
                          </td>
                          <td className="py-3.5 pr-4 text-sm text-[var(--ei-text-secondary)]">{formatShortDate(job.posted_on)}</td>
                          {!isCeo && (
                            <td className="py-3.5 text-right whitespace-nowrap w-[1%]" onClick={(e) => e.stopPropagation()}>
                              <div className="inline-flex items-center justify-end gap-2.5 min-w-[9.5rem]">
                                <label
                                  className="inline-flex items-center cursor-pointer select-none"
                                  title={active ? 'Enabled — click to disable' : 'Disabled — click to enable'}
                                >
                                  <span className="sr-only">{active ? 'Enabled' : 'Disabled'}</span>
                                  <input
                                    type="checkbox"
                                    className="sr-only"
                                    checked={active}
                                    disabled={togglingJobId === jdid}
                                    onChange={(e) => handleToggleEnabled(job, e.target.checked)}
                                  />
                                  <span
                                    className={`relative inline-block w-11 h-6 shrink-0 rounded-full transition-colors ${
                                      active ? 'bg-emerald-500' : 'bg-white/20'
                                    } ${togglingJobId === jdid ? 'opacity-60' : ''}`}
                                    aria-hidden
                                  >
                                    <span
                                      className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                                        active ? 'translate-x-5' : 'translate-x-0'
                                      }`}
                                    />
                                  </span>
                                </label>
                                <button
                                  type="button"
                                  onClick={() => openEditJob(job)}
                                  className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--ei-border-primary)] bg-white/[0.05] px-3 py-1.5 text-xs font-medium text-[var(--ei-text-primary)] hover:bg-white/[0.09] transition-colors"
                                >
                                  <FiEdit2 className="w-3.5 h-3.5" />
                                  Edit
                                </button>
                              </div>
                            </td>
                          )}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {editingJob && (
            <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
              <button
                type="button"
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                aria-label="Close edit dialog"
                onClick={closeEditJob}
              />
              <div
                className="relative w-full max-w-2xl rounded-2xl overflow-hidden border border-[var(--ei-border-primary)] org-glass-panel"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--ei-border-primary)] bg-white/[0.03]">
                  <h3 className="text-xl font-semibold text-[var(--ei-text-primary)]">Edit Job Post</h3>
                  <button
                    type="button"
                    onClick={closeEditJob}
                    className="p-2 rounded-xl text-[var(--ei-text-secondary)] hover:text-white hover:bg-white/[0.05] transition-colors"
                  >
                    <FiX className="w-5 h-5" />
                  </button>
                </div>
                <form onSubmit={handleEditSubmit} className="px-6 py-6 space-y-5 max-h-[70vh] overflow-y-auto">
                  {editError && (
                    <p className="text-sm text-red-300 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                      {editError}
                    </p>
                  )}
                  <PremiumInput
                    label="Job Title"
                    icon={FiBriefcase}
                    required
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    placeholder="e.g., Senior React Developer"
                  />
                  <PremiumInput
                    label="Location"
                    required
                    value={editLocation}
                    onChange={(e) => setEditLocation(e.target.value)}
                    placeholder="Bengaluru, KA"
                  />
                  <div className="grid sm:grid-cols-2 gap-4">
                    <PremiumInput
                      label="Salary (optional)"
                      value={editSalary}
                      onChange={(e) => setEditSalary(e.target.value)}
                      placeholder="₹15-25 LPA"
                    />
                    <div>
                      <label className="block text-sm font-semibold text-[#C5D0DA] mb-2">
                        Experience Range (years)
                      </label>
                      <div className="grid grid-cols-2 gap-3">
                        <input
                          type="number"
                          min="0"
                          className="premium-input"
                          value={editExperienceFrom}
                          onChange={(e) => setEditExperienceFrom(e.target.value)}
                          placeholder="From"
                        />
                        <input
                          type="number"
                          min="0"
                          className="premium-input"
                          value={editExperienceTo}
                          onChange={(e) => setEditExperienceTo(e.target.value)}
                          placeholder="To"
                        />
                      </div>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-[#C5D0DA] mb-2">Description</label>
                    <textarea
                      className="premium-input min-h-[120px] resize-y"
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      placeholder="Describe responsibilities, requirements, and perks"
                    />
                  </div>
                  <div className="flex justify-end gap-3 pt-2">
                    <PremiumButton type="button" variant="secondary" onClick={closeEditJob} disabled={editSaving}>
                      Cancel
                    </PremiumButton>
                    <PremiumButton type="submit" variant="primary" loading={editSaving} disabled={editSaving}>
                      {editSaving ? 'Saving…' : 'Save changes'}
                    </PremiumButton>
                  </div>
                </form>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <section className="org-glass-panel p-5 sm:p-6">
              <h2 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#83909C] mb-4">
                Recent Activity
              </h2>
              {loading ? (
                <div className="space-y-3">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-8 rounded-lg bg-white/[0.04] animate-pulse" />
                  ))}
                </div>
              ) : recentActivity.length === 0 ? (
                <p className="text-sm text-[var(--ei-text-muted)]">No recent activity yet.</p>
              ) : (
                <ul className="space-y-3">
                  {recentActivity.map((item) => (
                    <li key={item.id} className="flex items-start gap-3 text-sm text-[#C5D0DA]">
                      <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[#00A6FF] flex-shrink-0" aria-hidden />
                      <span className="min-w-0 leading-relaxed">{item.text}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <aside className="org-glass-panel p-5 sm:p-6">
              <h2 className="text-[12px] font-semibold uppercase tracking-[0.08em] text-[#83909C] mb-4">
                Organization Snapshot
              </h2>
              <div className="space-y-2.5">
                {loading
                  ? Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-10 rounded-xl bg-white/[0.04] animate-pulse" />
                    ))
                  : snapshotItems.map(({ label, value }) => (
                      <div
                        key={label}
                        className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.025] px-3.5 py-2.5"
                      >
                        <span className="text-sm text-[var(--ei-text-secondary)]">{label}</span>
                        <span className="text-sm font-semibold tabular-nums text-[var(--ei-text-primary)]">{value ?? '—'}</span>
                      </div>
                    ))}
              </div>
            </aside>
          </div>
        </div>
      )}

      {!loading && !showAnalytics && !showJobPosting && (
        <div className="mt-10 org-card p-5">
          <h2 className="text-sm font-semibold text-[var(--ei-text-label)] mb-2">Quick access</h2>
          <p className="text-sm text-[var(--ei-text-secondary)] mb-4">
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
          <h2 className="text-lg font-semibold text-[var(--ei-text-primary)] flex items-center gap-2">
            <FiBarChart2 className="w-5 h-5 text-[#00A6FF]" /> Analytics
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="org-card p-5">
              <h3 className="text-sm font-semibold text-[var(--ei-text-label)] flex items-center gap-2 mb-4">
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
              {analytics.total === 0 && <p className="text-sm text-[var(--ei-text-muted)] py-4">No applications yet</p>}
            </div>
            <div className="org-card p-5">
              <h3 className="text-sm font-semibold text-[var(--ei-text-label)] mb-4">Match score & shortlist rate</h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="rounded-xl bg-white/[0.035] p-4 border border-[var(--ei-border-primary)]">
                  <p className="text-xs text-[#83909C] uppercase tracking-wider">Avg. match score</p>
                  <p className="text-2xl font-bold text-[var(--ei-text-primary)] mt-1 tabular-nums">{analytics.avgScore != null ? `${analytics.avgScore}%` : '—'}</p>
                  <p className="text-xs text-[var(--ei-text-muted)] mt-0.5">{analytics.scoreCount} with score</p>
                </div>
                <div className="rounded-xl bg-white/[0.035] p-4 border border-[var(--ei-border-primary)]">
                  <p className="text-xs text-[#83909C] uppercase tracking-wider">Shortlist rate</p>
                  <p className="text-2xl font-bold text-[#36D6A0] mt-1 tabular-nums">{analytics.shortlistRate}%</p>
                  <p className="text-xs text-[var(--ei-text-muted)] mt-0.5">of applications</p>
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
                <div className="flex gap-4 mt-2 text-xs text-[var(--ei-text-muted)]">
                  <span><span className="inline-block w-2 h-2 rounded bg-red-500/80 mr-1" /> Low (&lt;30%)</span>
                  <span><span className="inline-block w-2 h-2 rounded bg-amber-500/80 mr-1" /> Medium (30–60%)</span>
                  <span><span className="inline-block w-2 h-2 rounded bg-green-500/80 mr-1" /> High (60%+)</span>
                </div>
              </div>
            </div>
          </div>
          <div className="org-card p-5">
            <h3 className="text-sm font-semibold text-[var(--ei-text-label)] mb-1">Job-level insight</h3>
            <p className="text-xs text-[var(--ei-text-muted)] mb-4">Applications, shortlisted count, and average match score per job.</p>
            {analytics.topJobs.length > 0 ? (
              <div className="space-y-2">
                {analytics.topJobs.map(({ id, title, count, shortlisted, reviewed, rejected, avgScore }) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => navigate(`${basePath}/jobs/${encodeURIComponent(id)}?tab=candidates`)}
                    className="w-full flex flex-wrap items-center gap-x-4 gap-y-1 py-3 px-3 rounded-xl bg-white/[0.035] border border-[var(--ei-border-primary)] hover:border-[rgba(0,166,255,0.3)] hover:bg-white/[0.05] transition-all duration-[180ms] text-left"
                  >
                    <span className="text-sm font-medium text-[var(--ei-text-primary)] truncate flex-1 min-w-0">{title || id}</span>
                    <span className="text-xs text-[var(--ei-text-secondary)] tabular-nums">
                      <span className="text-[var(--ei-text-label)]">{count}</span> applied
                      {(reviewed || 0) > 0 && <span className="text-amber-400 ml-2">{reviewed} reviewed</span>}
                      {shortlisted > 0 && <span className="text-[#36D6A0] ml-2">{shortlisted} shortlisted</span>}
                      {(rejected || 0) > 0 && <span className="text-[#FF6685] ml-2">{rejected} rejected</span>}
                      {avgScore != null && <span className="text-[#A78BFA] ml-2">avg {avgScore}% match</span>}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--ei-text-muted)] py-4">No applications yet</p>
            )}
          </div>
        </div>
      )}
    </>
  )
}
