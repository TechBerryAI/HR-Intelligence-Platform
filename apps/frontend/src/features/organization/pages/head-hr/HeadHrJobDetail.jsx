import React, { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import PanelShell, { usePanelBasePath, usePanelReadOnly } from '@/features/organization/pages/org/PanelShell.jsx'
import JobDescriptionView from '@/shared/components/JobDescriptionView.jsx'
import { getApplicationDisplayMatch } from '@/features/analytics/components/MatchExplanation'
import ApplicationStatusActions from '@/features/organization/components/org/ApplicationStatusActions.jsx'
import { FiArrowLeft, FiBriefcase, FiMapPin, FiDollarSign, FiUser, FiCalendar, FiUsers, FiClock, FiVideo } from 'react-icons/fi'

const JOB_TABS = ['details', 'candidates', 'interviews']

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

function formatDateTime(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function formatInterviewWhen(ts) {
  if (!ts) return { date: '—', time: '' }
  const d = new Date(ts)
  return {
    date: d.toLocaleDateString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }),
    time: d.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    }),
  }
}

function inviteEmailBadge(payload) {
  const failed = String(payload?.status || '').toLowerCase() === 'failed'
  const sent = !!payload?.sent || String(payload?.status || '').toLowerCase() === 'sent'
  const label = failed ? 'Failed' : sent ? 'Sent' : 'Pending'
  const cls = failed
    ? 'bg-red-500/10 text-red-400 border border-red-500/20'
    : sent
      ? 'bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)] border border-[var(--ei-tone-success-border)]'
      : 'bg-[var(--ei-tone-warning-bg,rgba(245,158,11,0.12))] text-[var(--ei-tone-warning)] border border-[var(--ei-tone-warning-border,rgba(245,158,11,0.25))]'
  return (
    <div>
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
        {label}
      </span>
      {payload?.sentAt && sent && (
        <p className="text-[11px] text-[var(--ei-text-muted)] mt-1">{formatDateTime(payload.sentAt)}</p>
      )}
    </div>
  )
}

const SCORE_FILTERS = [
  { id: 'all', label: 'All', min: 0, max: 100 },
  { id: '80+', label: '80% and above', min: 80, max: 100 },
  { id: '70-80', label: '70-80%', min: 70, max: 80 },
  { id: '60-70', label: '60-70%', min: 60, max: 70 },
  { id: '50-60', label: '50-60%', min: 50, max: 60 },
  { id: '40-50', label: '40-50%', min: 40, max: 50 },
  { id: 'below-40', label: '40% and below', min: 0, max: 40 },
]

function getApplicantScore(app) {
  const { score } = getApplicationDisplayMatch(app)
  if (score != null && Number.isFinite(Number(score))) return Number(score)
  const fallback = app.match_score ?? app.matchScore ?? app.score
  return fallback != null && Number.isFinite(Number(fallback)) ? Number(fallback) : null
}

function scoreMatchesFilter(score, filter) {
  if (filter.id === 'all') return true
  if (score == null || !Number.isFinite(score)) return false
  if (filter.id === '80+') return score >= 80 && score <= 100
  if (filter.id === 'below-40') return score >= 0 && score < 40
  return score >= filter.min && score < filter.max
}

export default function HeadHrJobDetail() {
  const { jdid } = useParams()
  const navigate = useNavigate()
  const basePath = usePanelBasePath()
  const readOnly = usePanelReadOnly()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawTab = searchParams.get('tab')
  const tab = rawTab === 'emails' ? 'interviews' : (JOB_TABS.includes(rawTab) ? rawTab : 'details')
  const [job, setJob] = useState(null)
  const [applicants, setApplicants] = useState([])
  const [interviews, setInterviews] = useState([])
  const [shortlistedInvites, setShortlistedInvites] = useState([])
  const [loading, setLoading] = useState(true)
  const [scheduleLoading, setScheduleLoading] = useState(false)
  const [scheduleError, setScheduleError] = useState('')
  const [error, setError] = useState('')
  const [selectedFilter, setSelectedFilter] = useState('all')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const token = tokenService.getToken()
        const [data, appsRes] = await Promise.all([
          apiRequest(`/api/head-hr/jobs/${encodeURIComponent(jdid)}`, { method: 'GET', token }),
          apiRequest('/api/head-hr/applications', { method: 'GET', token }),
        ])
        if (!cancelled) {
          setJob(data)
          const forJob = (appsRes?.applications || []).filter(
            (a) => String(a.job_id || a.jobId) === String(jdid),
          )
          setApplicants(forJob)
          setSelectedFilter('all')
        }
      } catch (err) {
        if (!cancelled) setError(err?.message || 'Failed to load job')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [jdid])

  useEffect(() => {
    if (tab !== 'interviews' || !jdid) return undefined
    let cancelled = false
    async function loadSchedule() {
      setScheduleLoading(true)
      setScheduleError('')
      try {
        const token = tokenService.getToken()
        const [interviewsRes, emailsRes] = await Promise.all([
          apiRequest(`/api/head-hr/jobs/${encodeURIComponent(jdid)}/interviews`, { method: 'GET', token }),
          apiRequest(`/api/head-hr/jobs/${encodeURIComponent(jdid)}/emails`, { method: 'GET', token }),
        ])
        if (!cancelled) {
          setInterviews(interviewsRes?.interviews || [])
          setShortlistedInvites(emailsRes?.emails || [])
        }
      } catch (err) {
        if (!cancelled) {
          setInterviews([])
          setShortlistedInvites([])
          setScheduleError(err?.message || 'Failed to load interview schedule')
        }
      } finally {
        if (!cancelled) setScheduleLoading(false)
      }
    }
    loadSchedule()
    return () => { cancelled = true }
  }, [tab, jdid])

  const filterCounts = useMemo(() => {
    const counts = {}
    for (const filter of SCORE_FILTERS) {
      counts[filter.id] = applicants.filter((app) => scoreMatchesFilter(getApplicantScore(app), filter)).length
    }
    return counts
  }, [applicants])

  const visibleFilters = useMemo(
    () => SCORE_FILTERS.filter((f) => f.id === 'all' || (filterCounts[f.id] || 0) > 0),
    [filterCounts],
  )

  useEffect(() => {
    if (!visibleFilters.some((f) => f.id === selectedFilter)) {
      setSelectedFilter('all')
    }
  }, [visibleFilters, selectedFilter])

  const filteredApplicants = useMemo(() => {
    const filter = SCORE_FILTERS.find((f) => f.id === selectedFilter) || SCORE_FILTERS[0]
    return applicants
      .filter((app) => scoreMatchesFilter(getApplicantScore(app), filter))
      .sort((a, b) => {
        const scoreA = getApplicantScore(a) ?? -1
        const scoreB = getApplicantScore(b) ?? -1
        return scoreB - scoreA
      })
  }, [applicants, selectedFilter])

  const scheduleRows = useMemo(() => {
    const byApp = new Map()
    const appKey = (id) => (id == null ? '' : String(id))

    const resolveInviteEmail = (inviteEmail, interview) => {
      const payload = inviteEmail || {}
      const sent = !!payload.sent || String(payload.status || '').toLowerCase() === 'sent'
      if (sent) return payload
      const ivStatus = String(interview?.status || '').toLowerCase()
      if (ivStatus === 'scheduled' || ivStatus === 'invited') {
        return {
          status: 'Sent',
          sent: true,
          sentAt: interview?.createdAt || interview?.scheduledAt || null,
          source: 'inferred',
        }
      }
      return payload
    }

    for (const invite of shortlistedInvites) {
      const key = appKey(invite.applicationId)
      if (!key) continue
      byApp.set(key, {
        applicationId: invite.applicationId,
        candidateId: invite.candidateId,
        candidateName: invite.candidateName,
        candidateEmail: invite.candidateEmail,
        inviteEmail: invite.inviteEmail || {},
        interview: null,
      })
    }
    for (const iv of interviews) {
      const key = appKey(iv.applicationId)
      if (!key) continue
      const existing = byApp.get(key) || {
        applicationId: iv.applicationId,
        candidateId: iv.candidateId,
        candidateName: iv.candidateName,
        candidateEmail: iv.candidateEmail,
        inviteEmail: {},
        interview: null,
      }
      existing.interview = iv
      if (!existing.candidateName) existing.candidateName = iv.candidateName
      if (!existing.candidateEmail) existing.candidateEmail = iv.candidateEmail
      if (!existing.candidateId) existing.candidateId = iv.candidateId
      existing.inviteEmail = resolveInviteEmail(existing.inviteEmail, iv)
      byApp.set(key, existing)
    }
    return Array.from(byApp.values()).map((row) => ({
      ...row,
      inviteEmail: resolveInviteEmail(row.inviteEmail, row.interview),
    }))
  }, [shortlistedInvites, interviews])

  if (loading) {
    return (
      <PanelShell>
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="org-skeleton" />
          ))}
        </div>
      </PanelShell>
    )
  }

  if (error || !job) {
    return (
      <PanelShell>
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error || 'Job not found'}
        </div>
        <button
          type="button"
          onClick={() => navigate(`${basePath}/jobs`)}
          className="org-back-link !mb-0"
        >
          <FiArrowLeft className="w-4 h-4" /> Back to Jobs
        </button>
      </PanelShell>
    )
  }

  const sectionClass = 'org-section'
  const labelClass = 'org-section-label'

  const setTab = (next) => {
    if (next === 'details') {
      setSearchParams({}, { replace: true })
      return
    }
    setSearchParams({ tab: next }, { replace: true })
  }

  const openCandidate = (candidateId) => {
    navigate(`${basePath}/jobs/${encodeURIComponent(jdid)}/candidates/${encodeURIComponent(candidateId)}`)
  }

  return (
    <PanelShell>
      <div className="max-w-4xl mx-auto">
        <button
          type="button"
          onClick={() => navigate(`${basePath}/jobs`)}
          className="org-back-link"
        >
          <FiArrowLeft className="w-4 h-4" /> Back to Jobs
        </button>

        <div className="flex items-start gap-3 mb-4">
          <div className="w-12 h-12 rounded-xl bg-[var(--ei-surface-hover)] border border-[var(--ei-border-primary)] flex items-center justify-center flex-shrink-0">
            <FiBriefcase className="w-6 h-6 text-[var(--ei-text-muted)]" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold text-[var(--ei-text-primary)]">{job.title || 'Job'}</h1>
            <p className="text-[var(--ei-text-muted)] mt-0.5">{job.company || '—'}</p>
            <p className="text-[var(--ei-text-muted)] text-sm font-mono mt-1">{job.jdid}</p>
          </div>
          <span
            className={`flex-shrink-0 inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
              job.enabled
                ? 'bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)] border border-[var(--ei-tone-success-border)]'
                : 'bg-[var(--ei-surface-hover)] text-[var(--ei-text-muted)] border border-[var(--ei-border-primary)]'
            }`}
          >
            {job.enabled ? 'Active' : 'Disabled'}
          </span>
        </div>

        <div className="flex gap-6 mb-6 border-b border-[var(--ei-border-primary)]">
          {[
            { id: 'details', label: 'Job Details' },
            { id: 'candidates', label: `Candidates (${applicants.length})` },
            { id: 'interviews', label: 'Interview Schedule' },
          ].map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`relative px-1 py-3 text-sm font-medium transition-colors duration-[180ms] ${
                tab === id
                  ? 'text-[var(--ei-text-primary)]'
                  : 'text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)]'
              }`}
            >
              {label}
              {tab === id && (
                <span
                  className="absolute left-0 right-0 bottom-0 h-0.5 rounded-full"
                  style={{ background: 'linear-gradient(90deg, #00A6FF, #7657FF)' }}
                  aria-hidden
                />
              )}
            </button>
          ))}
        </div>

        {tab === 'details' && (
          <div className="space-y-4">
            <div className={sectionClass}>
              <h2 className={labelClass}>Details</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3">
                {job.location && (
                  <div className="flex items-start gap-2">
                    <FiMapPin className="w-4 h-4 text-[var(--ei-text-muted)] flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-[var(--ei-text-muted)]">Location</p>
                      <p className="org-section-value">{job.location}</p>
                    </div>
                  </div>
                )}
                {job.salary != null && job.salary !== '' && (
                  <div className="flex items-start gap-2">
                    <FiDollarSign className="w-4 h-4 text-[var(--ei-text-muted)] flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-[var(--ei-text-muted)]">Salary</p>
                      <p className="org-section-value">{job.salary}</p>
                    </div>
                  </div>
                )}
                {job.experience != null && job.experience !== '' && (
                  <div className="flex items-start gap-2">
                    <FiBriefcase className="w-4 h-4 text-[var(--ei-text-muted)] flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-[var(--ei-text-muted)]">Experience</p>
                      <p className="org-section-value">{job.experience}</p>
                    </div>
                  </div>
                )}
                <div className="flex items-start gap-2">
                  <FiUser className="w-4 h-4 text-[var(--ei-text-muted)] flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs text-[var(--ei-text-muted)]">Posted by</p>
                    <p className="org-section-value">{job.posted_by_name || '—'}</p>
                    {job.posted_by_email && (
                      <p className="text-xs text-[var(--ei-text-muted)]">{job.posted_by_email}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <FiCalendar className="w-4 h-4 text-[var(--ei-text-muted)] flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs text-[var(--ei-text-muted)]">Posted on</p>
                    <p className="org-section-value">{formatDate(job.posted_on)}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className={sectionClass}>
              <h2 className={labelClass}>Job description</h2>
              <div className="mt-3">
                <JobDescriptionView
                  description={job.description}
                  titleClassName="text-[var(--ei-text-primary)]"
                  textClassName="text-[var(--ei-text-secondary)]"
                />
              </div>
            </div>
          </div>
        )}

        {tab === 'candidates' && (
          <div className={sectionClass}>
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className={`${labelClass} flex items-center gap-2`}>
                <FiUsers className="w-4 h-4" /> Applied candidates
              </h2>
              <span className="text-xs text-[var(--ei-text-muted)]">
                {filteredApplicants.length} of {applicants.length} applicant{applicants.length === 1 ? '' : 's'}
              </span>
            </div>
            {applicants.length === 0 ? (
              <p className="text-sm text-[var(--ei-text-muted)] py-4">No applications for this job yet.</p>
            ) : (
              <>
                {visibleFilters.length > 1 && (
                  <div className="flex flex-wrap gap-2 mb-4" role="tablist" aria-label="Filter by match score">
                    {visibleFilters.map((filter) => {
                      const count = filterCounts[filter.id] || 0
                      const active = selectedFilter === filter.id
                      return (
                        <button
                          key={filter.id}
                          type="button"
                          role="tab"
                          aria-selected={active}
                          onClick={() => setSelectedFilter(filter.id)}
                          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors duration-[180ms] ${
                            active
                              ? 'bg-[var(--ei-surface-hover)] border-[var(--ei-border-strong,var(--ei-border-primary))] text-[var(--ei-text-primary)]'
                              : 'bg-transparent border-[var(--ei-border-primary)] text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)] hover:bg-[var(--ei-surface-hover)]'
                          }`}
                        >
                          {filter.label}
                          <span className="tabular-nums opacity-80">({count})</span>
                        </button>
                      )
                    })}
                  </div>
                )}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--ei-border-primary)] text-left">
                        <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Candidate</th>
                        <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Email</th>
                        <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Match</th>
                        <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Status</th>
                        <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Applied</th>
                        {!readOnly && (
                          <th className="pb-2.5 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em] text-right">Decision</th>
                        )}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--ei-border-primary)]">
                      {filteredApplicants.map((app) => {
                        const score = getApplicantScore(app)
                        const status = String(app.status || 'applied').toLowerCase()
                        return (
                          <tr
                            key={app.id}
                            role="button"
                            tabIndex={0}
                            onClick={() => openCandidate(app.candidate_id)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                openCandidate(app.candidate_id)
                              }
                            }}
                            className="cursor-pointer transition-colors duration-[180ms] hover:bg-[var(--ei-surface-hover)] focus:outline-none focus-visible:bg-[var(--ei-surface-hover)] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#3AA9FF]/35"
                          >
                            <td className="py-3 pr-3 text-[var(--ei-text-primary)] font-medium">{app.candidate_name || app.candidate_id}</td>
                            <td className="py-3 pr-3 text-[var(--ei-text-secondary)]">{app.candidate_email || '—'}</td>
                            <td className="py-3 pr-3 tabular-nums font-semibold">
                              {score != null ? (
                                <span className={score >= 80 ? 'text-[var(--ei-tone-success)]' : 'text-[var(--ei-tone-warning)]'}>{Math.round(score)}%</span>
                              ) : (
                                <span className="text-[var(--ei-text-muted)]">—</span>
                              )}
                            </td>
                            <td className="py-3 pr-3 capitalize text-[var(--ei-text-secondary)]">
                              {app.shortlisted ? 'Shortlisted' : status === 'ats_failed' ? 'ATS failed' : status}
                            </td>
                            <td className="py-3 pr-3 text-[var(--ei-text-muted)]">{formatDate(app.applied_at)}</td>
                            {!readOnly && (
                              <td
                                className="py-3 pl-3 text-right"
                                onClick={(e) => e.stopPropagation()}
                                onKeyDown={(e) => e.stopPropagation()}
                              >
                                <ApplicationStatusActions
                                  jobId={jdid}
                                  candidateId={app.candidate_id}
                                  application={app}
                                  compact
                                  onUpdated={({ shortlisted, status }) => {
                                    setApplicants((prev) =>
                                      prev.map((row) =>
                                        row.id === app.id ? { ...row, shortlisted, status } : row,
                                      ),
                                    )
                                  }}
                                />
                              </td>
                            )}
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {tab === 'interviews' && (
          <div className={sectionClass}>
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className={`${labelClass} flex items-center gap-2`}>
                <FiClock className="w-4 h-4" /> Shortlist invites & scheduling
              </h2>
              <span className="text-xs text-[var(--ei-text-muted)]">
                {scheduleRows.length} shortlisted candidate{scheduleRows.length === 1 ? '' : 's'}
              </span>
            </div>
            {scheduleLoading ? (
              <div className="space-y-2 py-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="org-skeleton" />
                ))}
              </div>
            ) : scheduleError ? (
              <p className="text-sm text-red-400 py-4">{scheduleError}</p>
            ) : scheduleRows.length === 0 ? (
              <p className="text-sm text-[var(--ei-text-muted)] py-4">
                No shortlisted candidates yet. When someone is shortlisted, their combined shortlist + booking invite appears here, along with any booked interview slot.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--ei-border-primary)] text-left">
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Candidate</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Invite email</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Interview</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Date</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Time</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Recruiter</th>
                      <th className="pb-2.5 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Meet</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--ei-border-primary)]">
                    {scheduleRows.map((row) => {
                      const iv = row.interview
                      const status = String(iv?.status || '')
                      const isScheduled = status.toLowerCase() === 'scheduled'
                      const when = isScheduled ? formatInterviewWhen(iv.scheduledAt) : null
                      return (
                        <tr
                          key={row.applicationId || row.candidateId}
                          role="button"
                          tabIndex={0}
                          onClick={() => row.candidateId && openCandidate(row.candidateId)}
                          onKeyDown={(e) => {
                            if ((e.key === 'Enter' || e.key === ' ') && row.candidateId) {
                              e.preventDefault()
                              openCandidate(row.candidateId)
                            }
                          }}
                          className="cursor-pointer transition-colors duration-[180ms] hover:bg-[var(--ei-surface-hover)] focus:outline-none focus-visible:bg-[var(--ei-surface-hover)] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#3AA9FF]/35"
                        >
                          <td className="py-3 pr-3">
                            <p className="text-[var(--ei-text-primary)] font-medium">{row.candidateName}</p>
                            <p className="text-xs text-[var(--ei-text-muted)]">{row.candidateEmail || '—'}</p>
                          </td>
                          <td className="py-3 pr-3">{inviteEmailBadge(row.inviteEmail)}</td>
                          <td className="py-3 pr-3">
                            {iv ? (
                              <>
                                <span
                                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                    isScheduled
                                      ? 'bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)] border border-[var(--ei-tone-success-border)]'
                                      : 'bg-[var(--ei-surface-hover)] text-[var(--ei-text-secondary)] border border-[var(--ei-border-primary)]'
                                  }`}
                                >
                                  {status || '—'}
                                </span>
                                {!isScheduled && iv.openSlots > 0 && (
                                  <p className="text-[11px] text-[var(--ei-text-muted)] mt-1">
                                    {iv.openSlots} open slot{iv.openSlots === 1 ? '' : 's'}
                                  </p>
                                )}
                              </>
                            ) : (
                              <span className="text-[var(--ei-text-muted)] text-xs">Awaiting slots</span>
                            )}
                          </td>
                          <td className="py-3 pr-3">
                            {isScheduled ? (
                              <p className="text-[var(--ei-text-primary)] font-medium">{when.date}</p>
                            ) : iv?.inviteExpiresAt ? (
                              <p className="text-[var(--ei-text-muted)] text-xs">
                                Link expires {formatDateTime(iv.inviteExpiresAt)}
                              </p>
                            ) : (
                              <span className="text-[var(--ei-text-muted)]">—</span>
                            )}
                          </td>
                          <td className="py-3 pr-3">
                            {isScheduled ? (
                              <p className="text-[var(--ei-text-primary)] font-semibold tabular-nums">{when.time}</p>
                            ) : (
                              <span className="text-[var(--ei-text-muted)]">—</span>
                            )}
                          </td>
                          <td className="py-3 pr-3 text-[var(--ei-text-secondary)]">
                            {iv?.recruiterName || iv?.assignedTo || '—'}
                          </td>
                          <td className="py-3">
                            {iv?.meetLink ? (
                              <a
                                href={iv.meetLink}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1.5 text-[var(--ei-text-primary)] hover:underline"
                              >
                                <FiVideo className="w-3.5 h-3.5" />
                                Join
                              </a>
                            ) : (
                              <span className="text-[var(--ei-text-muted)]">—</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </PanelShell>
  )
}
