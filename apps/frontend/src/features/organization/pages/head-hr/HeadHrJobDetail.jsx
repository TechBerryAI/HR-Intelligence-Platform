import React, { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import PanelShell, { usePanelBasePath } from '@/features/organization/pages/org/PanelShell.jsx'
import JobDescriptionView from '@/shared/components/JobDescriptionView.jsx'
import { getApplicationDisplayMatch } from '@/features/analytics/components/MatchExplanation'
import { FiArrowLeft, FiBriefcase, FiMapPin, FiDollarSign, FiUser, FiCalendar, FiUsers, FiClock, FiVideo, FiMail } from 'react-icons/fi'

const JOB_TABS = ['details', 'candidates', 'emails', 'interviews']

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
  const [searchParams, setSearchParams] = useSearchParams()
  const rawTab = searchParams.get('tab')
  const tab = JOB_TABS.includes(rawTab) ? rawTab : 'details'
  const [job, setJob] = useState(null)
  const [applicants, setApplicants] = useState([])
  const [interviews, setInterviews] = useState([])
  const [emails, setEmails] = useState([])
  const [loading, setLoading] = useState(true)
  const [interviewsLoading, setInterviewsLoading] = useState(false)
  const [interviewsError, setInterviewsError] = useState('')
  const [emailsLoading, setEmailsLoading] = useState(false)
  const [emailsError, setEmailsError] = useState('')
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
    async function loadInterviews() {
      setInterviewsLoading(true)
      setInterviewsError('')
      try {
        const token = tokenService.getToken()
        const res = await apiRequest(
          `/api/head-hr/jobs/${encodeURIComponent(jdid)}/interviews`,
          { method: 'GET', token },
        )
        if (!cancelled) setInterviews(res?.interviews || [])
      } catch (err) {
        if (!cancelled) {
          setInterviews([])
          setInterviewsError(err?.message || 'Failed to load interview schedule')
        }
      } finally {
        if (!cancelled) setInterviewsLoading(false)
      }
    }
    loadInterviews()
    return () => { cancelled = true }
  }, [tab, jdid])

  useEffect(() => {
    if (tab !== 'emails' || !jdid) return undefined
    let cancelled = false
    async function loadEmails() {
      setEmailsLoading(true)
      setEmailsError('')
      try {
        const token = tokenService.getToken()
        const res = await apiRequest(
          `/api/head-hr/jobs/${encodeURIComponent(jdid)}/emails`,
          { method: 'GET', token },
        )
        if (!cancelled) setEmails(res?.emails || [])
      } catch (err) {
        if (!cancelled) {
          setEmails([])
          setEmailsError(err?.message || 'Failed to load email status')
        }
      } finally {
        if (!cancelled) setEmailsLoading(false)
      }
    }
    loadEmails()
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

  const shortlistedEmails = useMemo(
    () =>
      emails.filter((item) => {
        const status = String(item.applicationStatus || '')
        return (
          status === 'Shortlisted'
          || status === 'Interview'
          || item.shortlistEmail?.sent
          || item.interviewEmail?.sent
        )
      }),
    [emails],
  )

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
            { id: 'emails', label: 'Email' },
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
                        <th className="pb-2.5 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Applied</th>
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
                            <td className="py-3 text-[var(--ei-text-muted)]">{formatDate(app.applied_at)}</td>
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

        {tab === 'emails' && (
          <div className={sectionClass}>
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className={`${labelClass} flex items-center gap-2`}>
                <FiMail className="w-4 h-4" /> Email status
              </h2>
              <span className="text-xs text-[var(--ei-text-muted)]">
                {shortlistedEmails.length} shortlisted candidate{shortlistedEmails.length === 1 ? '' : 's'}
              </span>
            </div>
            {emailsLoading ? (
              <div className="space-y-2 py-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="org-skeleton" />
                ))}
              </div>
            ) : emailsError ? (
              <p className="text-sm text-red-400 py-4">{emailsError}</p>
            ) : shortlistedEmails.length === 0 ? (
              <p className="text-sm text-[var(--ei-text-muted)] py-4">
                No shortlisted candidates for this job yet. Shortlist emails appear here once a candidate is shortlisted.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--ei-border-primary)] text-left">
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Candidate</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Email</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Shortlist mail</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Interview mail</th>
                      <th className="pb-2.5 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Overall</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--ei-border-primary)]">
                    {shortlistedEmails.map((item) => {
                      const shortlist = item.shortlistEmail || {}
                      const interview = item.interviewEmail || {}
                      const overall = String(item.overallStatus || 'Pending')
                      const badge = (payload) => {
                        const sent = !!payload?.sent
                        const failed = String(payload?.status || '').toLowerCase() === 'failed'
                        const raw = String(payload?.status || '').toLowerCase()
                        const label = failed
                          ? 'Failed'
                          : sent || raw === 'sent'
                            ? 'Sent'
                            : 'Pending'
                        const cls = failed
                          ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                          : label === 'Sent'
                            ? 'bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)] border border-[var(--ei-tone-success-border)]'
                            : 'bg-[var(--ei-tone-warning-bg,rgba(245,158,11,0.12))] text-[var(--ei-tone-warning)] border border-[var(--ei-tone-warning-border,rgba(245,158,11,0.25))]'
                        return (
                          <div>
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
                              {label}
                            </span>
                            {payload?.sentAt && label === 'Sent' && (
                              <p className="text-[11px] text-[var(--ei-text-muted)] mt-1">{formatDateTime(payload.sentAt)}</p>
                            )}
                          </div>
                        )
                      }
                      return (
                        <tr
                          key={item.applicationId || item.candidateId}
                          role="button"
                          tabIndex={0}
                          onClick={() => item.candidateId && openCandidate(item.candidateId)}
                          onKeyDown={(e) => {
                            if ((e.key === 'Enter' || e.key === ' ') && item.candidateId) {
                              e.preventDefault()
                              openCandidate(item.candidateId)
                            }
                          }}
                          className="cursor-pointer transition-colors duration-[180ms] hover:bg-[var(--ei-surface-hover)] focus:outline-none focus-visible:bg-[var(--ei-surface-hover)] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#3AA9FF]/35"
                        >
                          <td className="py-3 pr-3 text-[var(--ei-text-primary)] font-medium">{item.candidateName}</td>
                          <td className="py-3 pr-3 text-[var(--ei-text-secondary)]">{item.candidateEmail || '—'}</td>
                          <td className="py-3 pr-3">{badge(shortlist)}</td>
                          <td className="py-3 pr-3">{badge(interview)}</td>
                          <td className="py-3">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                overall === 'Sent'
                                  ? 'bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)] border border-[var(--ei-tone-success-border)]'
                                  : 'bg-[var(--ei-tone-warning-bg,rgba(245,158,11,0.12))] text-[var(--ei-tone-warning)] border border-[var(--ei-tone-warning-border,rgba(245,158,11,0.25))]'
                              }`}
                            >
                              {overall === 'Sent' ? 'Sent' : 'Pending'}
                            </span>
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

        {tab === 'interviews' && (
          <div className={sectionClass}>
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className={`${labelClass} flex items-center gap-2`}>
                <FiClock className="w-4 h-4" /> Interview schedule
              </h2>
              <span className="text-xs text-[var(--ei-text-muted)]">
                {interviews.length} interview{interviews.length === 1 ? '' : 's'}
              </span>
            </div>
            {interviewsLoading ? (
              <div className="space-y-2 py-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="org-skeleton" />
                ))}
              </div>
            ) : interviewsError ? (
              <p className="text-sm text-red-400 py-4">{interviewsError}</p>
            ) : interviews.length === 0 ? (
              <p className="text-sm text-[var(--ei-text-muted)] py-4">
                No interview invites or booked slots for this job yet. Shortlisted candidates receive a booking link automatically when Google Calendar is connected.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--ei-border-primary)] text-left">
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Candidate</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Status</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Date</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Time</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Recruiter</th>
                      <th className="pb-2.5 text-[11px] font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]">Meet</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--ei-border-primary)]">
                    {interviews.map((item) => {
                      const status = String(item.status || '')
                      const isScheduled = status.toLowerCase() === 'scheduled'
                      const when = isScheduled ? formatInterviewWhen(item.scheduledAt) : null
                      return (
                        <tr
                          key={item.id}
                          role="button"
                          tabIndex={0}
                          onClick={() => item.candidateId && openCandidate(item.candidateId)}
                          onKeyDown={(e) => {
                            if ((e.key === 'Enter' || e.key === ' ') && item.candidateId) {
                              e.preventDefault()
                              openCandidate(item.candidateId)
                            }
                          }}
                          className="cursor-pointer transition-colors duration-[180ms] hover:bg-[var(--ei-surface-hover)] focus:outline-none focus-visible:bg-[var(--ei-surface-hover)] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#3AA9FF]/35"
                        >
                          <td className="py-3 pr-3">
                            <p className="text-[var(--ei-text-primary)] font-medium">{item.candidateName}</p>
                            <p className="text-xs text-[var(--ei-text-muted)]">{item.candidateEmail || '—'}</p>
                          </td>
                          <td className="py-3 pr-3">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                isScheduled
                                  ? 'bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)] border border-[var(--ei-tone-success-border)]'
                                  : 'bg-[var(--ei-surface-hover)] text-[var(--ei-text-secondary)] border border-[var(--ei-border-primary)]'
                              }`}
                            >
                              {status || '—'}
                            </span>
                            {!isScheduled && item.openSlots > 0 && (
                              <p className="text-[11px] text-[var(--ei-text-muted)] mt-1">
                                {item.openSlots} open slot{item.openSlots === 1 ? '' : 's'}
                              </p>
                            )}
                          </td>
                          <td className="py-3 pr-3">
                            {isScheduled ? (
                              <p className="text-[var(--ei-text-primary)] font-medium">{when.date}</p>
                            ) : (
                              <p className="text-[var(--ei-text-muted)] text-xs">
                                {item.inviteExpiresAt
                                  ? `Invite expires ${formatDateTime(item.inviteExpiresAt)}`
                                  : 'Awaiting booking'}
                              </p>
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
                            {item.recruiterName || item.assignedTo || '—'}
                          </td>
                          <td className="py-3">
                            {item.meetLink ? (
                              <a
                                href={item.meetLink}
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
