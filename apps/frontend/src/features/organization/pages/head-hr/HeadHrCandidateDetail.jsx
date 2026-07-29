import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import { BASE_URL } from '@/core/api/api.js'
import PanelShell, { usePanelBasePath } from '@/features/organization/pages/org/PanelShell.jsx'
import { FiArrowLeft, FiUser, FiMail, FiPhone, FiMapPin, FiBriefcase, FiBook, FiAward, FiFileText } from 'react-icons/fi'

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function HeadHrCandidateDetail() {
  const { cid } = useParams()
  const navigate = useNavigate()
  const basePath = usePanelBasePath()
  const [candidate, setCandidate] = useState(null)
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
        const data = await apiRequest(`/api/head-hr/candidates/${encodeURIComponent(cid)}`, { method: 'GET', token })
        if (!cancelled) setCandidate(data)
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
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error || 'Candidate not found'}
        </div>
        <button
          type="button"
          onClick={() => navigate(`${basePath}/candidates`)}
          className="org-back-link !mb-0"
        >
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
        <button
          type="button"
          onClick={() => navigate(`${basePath}/candidates`)}
          className="org-back-link"
        >
          <FiArrowLeft className="w-4 h-4" /> Back to Candidates
        </button>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
              <FiUser className="w-6 h-6 text-slate-500 dark:text-slate-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white">{candidate.fullName || candidate.email || 'Candidate'}</h1>
              <p className="text-sm text-slate-500 font-mono">{candidate.candidate_id}</p>
            </div>
          </div>
          {candidate.hasResume && (
            <button
              type="button"
              onClick={handleViewResume}
              disabled={resumeLoading}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <FiFileText className="w-4 h-4" />
              {resumeLoading ? 'Opening…' : 'View Resume'}
            </button>
          )}
        </div>

        {!candidate.hasResume && (
          <p className="text-sm text-slate-500 mb-4">This candidate has not uploaded a resume.</p>
        )}

        <div className="space-y-4">
          <div className={sectionClass}>
            <h2 className={labelClass}>Contact</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
              <div>
                <p className="text-slate-500 text-xs flex items-center gap-1.5"><FiMail className="w-3.5 h-3.5" /> Email</p>
                <p className={valueClass}>{candidate.email || '—'}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs flex items-center gap-1.5"><FiPhone className="w-3.5 h-3.5" /> Phone</p>
                <p className={valueClass}>{candidate.phone || '—'}</p>
              </div>
              <div className="sm:col-span-2">
                <p className="text-slate-500 text-xs flex items-center gap-1.5"><FiMapPin className="w-3.5 h-3.5" /> Location</p>
                <p className={valueClass}>{candidate.currentLocation || candidate.preferredLocation || '—'}</p>
                {(candidate.currentLocation || candidate.preferredLocation) && candidate.preferredLocation && candidate.currentLocation !== candidate.preferredLocation && (
                  <p className="text-slate-500 text-xs mt-1">Preferred: {candidate.preferredLocation}</p>
                )}
              </div>
            </div>
          </div>

          <div className={sectionClass}>
            <h2 className={labelClass}>Professional</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
              <div>
                <p className="text-slate-500 text-xs">Experience level</p>
                <p className={valueClass}>{candidate.experienceLevel || '—'}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs">Notice period</p>
                <p className={valueClass}>{candidate.noticePeriod || candidate.servingNotice || '—'}</p>
              </div>
              {candidate.lastWorkingDay && (
                <div>
                  <p className="text-slate-500 text-xs">Last working day</p>
                  <p className={valueClass}>{candidate.lastWorkingDay}</p>
                </div>
              )}
              {candidate.linkedinUrl && (
                <div className="sm:col-span-2">
                  <p className="text-slate-500 text-xs">LinkedIn</p>
                  <a href={candidate.linkedinUrl} target="_blank" rel="noopener noreferrer" className={`${valueClass} text-blue-400 hover:underline block truncate`}>
                    {candidate.linkedinUrl}
                  </a>
                </div>
              )}
              {candidate.portfolioUrl && (
                <div className="sm:col-span-2">
                  <p className="text-slate-500 text-xs">Portfolio</p>
                  <a href={candidate.portfolioUrl} target="_blank" rel="noopener noreferrer" className={`${valueClass} text-blue-400 hover:underline block truncate`}>
                    {candidate.portfolioUrl}
                  </a>
                </div>
              )}
            </div>
          </div>

          {Array.isArray(candidate.experiences) && candidate.experiences.length > 0 && (
            <div className={sectionClass}>
              <h2 className={`${labelClass} flex items-center gap-2`}><FiBriefcase className="w-4 h-4" /> Experience</h2>
              <ul className="mt-3 space-y-3">
                {candidate.experiences.map((exp, i) => (
                  <li key={i} className="text-sm text-slate-700 dark:text-slate-300 pl-2 border-l-2 border-slate-200 dark:border-slate-700">
                    <span className="font-medium text-slate-900 dark:text-slate-100">{exp.role || '—'}</span>
                    {exp.company && <span className="text-slate-500"> at {exp.company}</span>}
                    {(exp.startMonth || exp.endMonth) && (
                      <p className="text-slate-500 text-xs mt-0.5">
                        {exp.startMonth || '—'} – {exp.isCurrent ? 'Present' : (exp.endMonth || '—')}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {Array.isArray(candidate.education) && candidate.education.length > 0 && (
            <div className={sectionClass}>
              <h2 className={`${labelClass} flex items-center gap-2`}><FiBook className="w-4 h-4" /> Education</h2>
              <ul className="mt-3 space-y-3">
                {candidate.education.map((edu, i) => (
                  <li key={i} className="text-sm text-slate-700 dark:text-slate-300 pl-2 border-l-2 border-slate-200 dark:border-slate-700">
                    <span className="font-medium text-slate-900 dark:text-slate-100">{edu.degree || '—'}</span>
                    {edu.institution && <span className="text-slate-500">, {edu.institution}</span>}
                    {(edu.cgpa || edu.startMonth || edu.endMonth) && (
                      <p className="text-slate-500 text-xs mt-0.5">
                        {[edu.cgpa, [edu.startMonth, edu.endMonth].filter(Boolean).join(' – ')].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {Array.isArray(candidate.certifications) && candidate.certifications.length > 0 && (
            <div className={sectionClass}>
              <h2 className={`${labelClass} flex items-center gap-2`}><FiAward className="w-4 h-4" /> Certifications</h2>
              <ul className="mt-3 space-y-2">
                {candidate.certifications.map((cert, i) => (
                  <li key={i} className="text-sm text-slate-700 dark:text-slate-300">
                    <span className="font-medium text-slate-900 dark:text-slate-100">{cert.certification || '—'}</span>
                    {cert.issuer && <span className="text-slate-500"> ({cert.issuer})</span>}
                    {cert.endMonth && <span className="text-slate-500 text-xs"> · {cert.endMonth}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {candidate.joinedAt && (
            <div className={`${sectionClass} text-sm text-slate-500`}>
              Joined {formatDate(candidate.joinedAt)}
            </div>
          )}
        </div>
      </div>
    </PanelShell>
  )
}
