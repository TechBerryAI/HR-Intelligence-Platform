import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiRequest, BASE_URL } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import PanelShell, { usePanelBasePath } from '@/features/organization/pages/org/PanelShell.jsx'
import { getApplicationDisplayMatch } from '@/features/analytics/components/MatchExplanation'
import {
  FiArrowLeft, FiUser, FiMail, FiPhone, FiMapPin, FiBriefcase, FiBook, FiAward, FiFileText, FiArrowRight,
} from 'react-icons/fi'

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function HeadHrCandidateDetail() {
  const { cid } = useParams()
  const navigate = useNavigate()
  const basePath = usePanelBasePath()
  const [candidate, setCandidate] = useState(null)
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [resumeLoading, setResumeLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const token = tokenService.getToken()
        const [data, appsRes] = await Promise.all([
          apiRequest(`/api/head-hr/candidates/${encodeURIComponent(cid)}`, { method: 'GET', token }),
          apiRequest('/api/head-hr/applications', { method: 'GET', token }),
        ])
        if (cancelled) return
        setCandidate(data)
        const apps = (appsRes?.applications || []).filter(
          (a) => String(a.candidate_id || a.candidateId) === String(cid),
        )
        setApplications(apps)
      } catch (err) {
        if (!cancelled) setError(err?.message || 'Failed to load candidate')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [cid])

  const handleViewResume = async () => {
    if (!candidate?.hasResume || resumeLoading) return
    setResumeLoading(true)
    try {
      const token = tokenService.getToken()
      const url = `${BASE_URL || ''}/api/head-hr/candidates/${encodeURIComponent(cid)}/resume`
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'include',
      })
      if (!res.ok) throw new Error('Failed to load resume')
      const blob = await res.blob()
      const blobUrl = URL.createObjectURL(blob)
      window.open(blobUrl, '_blank', 'noopener,noreferrer')
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000)
    } catch (err) {
      console.error(err)
      alert(err?.message || 'Unable to open resume.')
    } finally {
      setResumeLoading(false)
    }
  }

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

  if (error || !candidate) {
    return (
      <PanelShell>
        <div className="org-error-banner mb-4">{error || 'Candidate not found'}</div>
        <button type="button" onClick={() => navigate(`${basePath}/candidates`)} className="org-back-link !mb-0">
          <FiArrowLeft className="w-4 h-4" /> Back to Candidates
        </button>
      </PanelShell>
    )
  }

  const sectionClass = 'org-section'
  const labelClass = 'org-section-label'
  const valueClass = 'org-section-value'

  return (
    <PanelShell>
      <div className="max-w-3xl mx-auto">
        <button type="button" onClick={() => navigate(`${basePath}/candidates`)} className="org-back-link">
          <FiArrowLeft className="w-4 h-4" /> Back to Candidates
        </button>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-white/[0.06] flex items-center justify-center border border-white/[0.08]">
              <FiUser className="w-6 h-6 text-[var(--ei-text-muted)]" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[var(--ei-text-primary)]">
                {candidate.fullName || candidate.email || 'Candidate'}
              </h1>
              <p className="text-sm text-[var(--ei-text-muted)] font-mono">{candidate.candidate_id}</p>
            </div>
          </div>
          {candidate.hasResume && (
            <button
              type="button"
              onClick={handleViewResume}
              disabled={resumeLoading}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 transition-colors"
            >
              <FiFileText className="w-4 h-4" />
              {resumeLoading ? 'Opening…' : 'View Resume'}
            </button>
          )}
        </div>

        <div className={`${sectionClass} mb-4`}>
          <h2 className={labelClass}>Applications ({applications.length})</h2>
          {applications.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--ei-text-muted)]">No applications on file.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {applications.map((app) => {
                const jdid = app.job_id || app.jobId
                return (
                  <li key={app.id}>
                    <button
                      type="button"
                      onClick={() =>
                        navigate(
                          `${basePath}/jobs/${encodeURIComponent(jdid)}/candidates/${encodeURIComponent(cid)}`,
                        )
                      }
                      className="w-full text-left rounded-xl border border-white/[0.08] bg-white/[0.03] hover:bg-white/[0.06] px-4 py-3 transition-colors flex items-center justify-between gap-3"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-[var(--ei-text-primary)] truncate">
                          {app.job_title || jdid || 'Job'}
                        </p>
                        <p className="text-xs text-[var(--ei-text-muted)] mt-0.5">
                          {app.job_company || '—'} · {formatDate(app.applied_at)} · {app.status || 'Applied'}
                          {(() => {
                            const { score } = getApplicationDisplayMatch(app)
                            return score != null ? ` · Score ${score}` : ''
                          })()}
                        </p>
                      </div>
                      <FiArrowRight className="w-4 h-4 shrink-0 text-[#55B9FF]" />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        <div className="space-y-4">
          <div className={sectionClass}>
            <h2 className={labelClass}>Contact</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
              <div>
                <p className="text-[var(--ei-text-muted)] text-xs flex items-center gap-1.5">
                  <FiMail className="w-3.5 h-3.5" /> Email
                </p>
                <p className={valueClass}>{candidate.email || '—'}</p>
              </div>
              <div>
                <p className="text-[var(--ei-text-muted)] text-xs flex items-center gap-1.5">
                  <FiPhone className="w-3.5 h-3.5" /> Phone
                </p>
                <p className={valueClass}>{candidate.phone || '—'}</p>
              </div>
              <div className="sm:col-span-2">
                <p className="text-[var(--ei-text-muted)] text-xs flex items-center gap-1.5">
                  <FiMapPin className="w-3.5 h-3.5" /> Location
                </p>
                <p className={valueClass}>
                  {candidate.currentLocation || candidate.preferredLocation || '—'}
                </p>
              </div>
            </div>
          </div>

          <div className={sectionClass}>
            <h2 className={labelClass}>Professional</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
              <div>
                <p className="text-[var(--ei-text-muted)] text-xs">Experience level</p>
                <p className={valueClass}>{candidate.experienceLevel || '—'}</p>
              </div>
              <div>
                <p className="text-[var(--ei-text-muted)] text-xs">Notice period</p>
                <p className={valueClass}>{candidate.noticePeriod || candidate.servingNotice || '—'}</p>
              </div>
            </div>
          </div>

          {Array.isArray(candidate.experiences) && candidate.experiences.length > 0 && (
            <div className={sectionClass}>
              <h2 className={`${labelClass} flex items-center gap-2`}>
                <FiBriefcase className="w-4 h-4" /> Experience
              </h2>
              <ul className="mt-3 space-y-3">
                {candidate.experiences.map((exp, i) => (
                  <li key={i} className="text-sm text-[var(--ei-text-secondary)] pl-2 border-l-2 border-white/[0.1]">
                    <span className="font-medium text-[var(--ei-text-primary)]">{exp.role || '—'}</span>
                    {exp.company && <span> at {exp.company}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {Array.isArray(candidate.education) && candidate.education.length > 0 && (
            <div className={sectionClass}>
              <h2 className={`${labelClass} flex items-center gap-2`}>
                <FiBook className="w-4 h-4" /> Education
              </h2>
              <ul className="mt-3 space-y-3">
                {candidate.education.map((edu, i) => (
                  <li key={i} className="text-sm text-[var(--ei-text-secondary)] pl-2 border-l-2 border-white/[0.1]">
                    <span className="font-medium text-[var(--ei-text-primary)]">{edu.degree || '—'}</span>
                    {edu.institution && <span>, {edu.institution}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {Array.isArray(candidate.certifications) && candidate.certifications.length > 0 && (
            <div className={sectionClass}>
              <h2 className={`${labelClass} flex items-center gap-2`}>
                <FiAward className="w-4 h-4" /> Certifications
              </h2>
              <ul className="mt-3 space-y-2">
                {candidate.certifications.map((cert, i) => (
                  <li key={i} className="text-sm text-[var(--ei-text-secondary)]">
                    <span className="font-medium text-[var(--ei-text-primary)]">{cert.certification || '—'}</span>
                    {cert.issuer && <span> ({cert.issuer})</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </PanelShell>
  )
}
