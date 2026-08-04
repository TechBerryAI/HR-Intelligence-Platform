import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import PanelShell, { usePanelBasePath } from '@/features/organization/pages/org/PanelShell.jsx'
import JobDescriptionView from '@/shared/components/JobDescriptionView.jsx'
import { getApplicationDisplayMatch } from '@/features/analytics/components/MatchExplanation'
import { FiArrowLeft, FiBriefcase, FiMapPin, FiDollarSign, FiUser, FiCalendar, FiUsers } from 'react-icons/fi'

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function HeadHrJobDetail() {
  const { jdid } = useParams()
  const navigate = useNavigate()
  const basePath = usePanelBasePath()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') === 'candidates' ? 'candidates' : 'details'
  const [job, setJob] = useState(null)
  const [applicants, setApplicants] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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
    setSearchParams(next === 'candidates' ? { tab: 'candidates' } : {}, { replace: true })
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
          <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0">
            <FiBriefcase className="w-6 h-6 text-slate-500 dark:text-slate-400" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-xl font-bold text-[#F5F7FA]">{job.title || 'Job'}</h1>
            <p className="text-slate-500 dark:text-slate-400 mt-0.5">{job.company || '—'}</p>
            <p className="text-slate-500 text-sm font-mono mt-1">{job.jdid}</p>
          </div>
          <span
            className={`flex-shrink-0 inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
              job.enabled ? 'bg-green-500/15 text-green-400 border border-green-500/20' : 'bg-zinc-700/50 text-slate-500 border border-slate-200 dark:border-slate-700'
            }`}
          >
            {job.enabled ? 'Active' : 'Disabled'}
          </span>
        </div>

        <div className="flex gap-6 mb-6 border-b border-white/[0.08]">
          {[
            { id: 'details', label: 'Job Details' },
            { id: 'candidates', label: `Candidates (${applicants.length})` },
          ].map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`relative px-1 py-3 text-sm font-medium transition-colors duration-[180ms] ${
                tab === id
                  ? 'text-white'
                  : 'text-[#77899B] hover:text-[#DCE3EA]'
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

        {tab === 'details' ? (
          <div className="space-y-4">
            <div className={sectionClass}>
              <h2 className={labelClass}>Details</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3">
                {job.location && (
                  <div className="flex items-start gap-2">
                    <FiMapPin className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-slate-500">Location</p>
                      <p className="org-section-value">{job.location}</p>
                    </div>
                  </div>
                )}
                {job.salary != null && job.salary !== '' && (
                  <div className="flex items-start gap-2">
                    <FiDollarSign className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-slate-500">Salary</p>
                      <p className="org-section-value">{job.salary}</p>
                    </div>
                  </div>
                )}
                {job.experience != null && job.experience !== '' && (
                  <div className="flex items-start gap-2">
                    <FiBriefcase className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs text-slate-500">Experience</p>
                      <p className="org-section-value">{job.experience}</p>
                    </div>
                  </div>
                )}
                <div className="flex items-start gap-2">
                  <FiUser className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs text-slate-500">Posted by</p>
                    <p className="org-section-value">{job.posted_by_name || '—'}</p>
                    {job.posted_by_email && (
                      <p className="text-xs text-slate-500">{job.posted_by_email}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <FiCalendar className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs text-slate-500">Posted on</p>
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
                  titleClassName="text-[#DCE3EA]"
                  textClassName="text-[#A0ABB6]"
                />
              </div>
            </div>
          </div>
        ) : (
          <div className={sectionClass}>
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className={`${labelClass} flex items-center gap-2`}>
                <FiUsers className="w-4 h-4" /> Applied candidates
              </h2>
              <span className="text-xs text-slate-500">{applicants.length} applicant{applicants.length === 1 ? '' : 's'}</span>
            </div>
            {applicants.length === 0 ? (
              <p className="text-sm text-[#8796A5] py-4">No applications for this job yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.08] text-left">
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[#83909C] uppercase tracking-[0.08em]">Candidate</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[#83909C] uppercase tracking-[0.08em]">Email</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[#83909C] uppercase tracking-[0.08em]">Match</th>
                      <th className="pb-2.5 pr-3 text-[11px] font-semibold text-[#83909C] uppercase tracking-[0.08em]">Status</th>
                      <th className="pb-2.5 text-[11px] font-semibold text-[#83909C] uppercase tracking-[0.08em]">Applied</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.06]">
                    {applicants.map((app) => {
                      const { score } = getApplicationDisplayMatch(app)
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
                          className="cursor-pointer transition-colors duration-[180ms] hover:bg-white/[0.05] focus:outline-none focus-visible:bg-white/[0.06] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#3AA9FF]/35"
                        >
                          <td className="py-3 pr-3 text-[#F5F7FA] font-medium">{app.candidate_name || app.candidate_id}</td>
                          <td className="py-3 pr-3 text-[#A0ABB6]">{app.candidate_email || '—'}</td>
                          <td className="py-3 pr-3 tabular-nums font-semibold">
                            {score != null ? (
                              <span className={score >= 60 ? 'text-[#36D6A0]' : 'text-[#F5B94C]'}>{score}%</span>
                            ) : (
                              <span className="text-[#738394]">—</span>
                            )}
                          </td>
                          <td className="py-3 pr-3 capitalize text-[#A0ABB6]">
                            {app.shortlisted ? 'Shortlisted' : status === 'ats_failed' ? 'ATS failed' : status}
                          </td>
                          <td className="py-3 text-[#8796A5]">{formatDate(app.applied_at)}</td>
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
