import React, { useState } from 'react'
import { BASE_URL } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import { formatLocation } from '@/shared/utils/formatLocation.js'
import { FiUser, FiMail, FiPhone, FiMapPin, FiBriefcase, FiBook, FiAward, FiFileText } from 'react-icons/fi'

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function CandidateProfilePanel({ candidate, cid }) {
  const [resumeLoading, setResumeLoading] = useState(false)
  if (!candidate) return null

  const sectionClass = 'rounded-[14px] bg-[var(--ei-surface-hover)] border border-[var(--ei-border-primary)] p-4'
  const labelClass = 'text-xs font-semibold text-[var(--ei-text-muted)] uppercase tracking-[0.08em]'
  const valueClass = 'text-sm font-medium text-[var(--ei-text-primary)] mt-0.5'
  const metaClass = 'text-[var(--ei-text-muted)] text-xs'
  const candidateId = cid || candidate.candidate_id || candidate.cid

  const handleViewResume = async () => {
    if (!candidate?.hasResume || resumeLoading || !candidateId) return
    setResumeLoading(true)
    try {
      const token = tokenService.getToken()
      const url = `${BASE_URL || ''}/api/head-hr/candidates/${encodeURIComponent(candidateId)}/resume`
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
      alert(err?.message || 'Unable to open resume.')
    } finally {
      setResumeLoading(false)
    }
  }

  const currentLoc = formatLocation(candidate.currentLocation)
  const preferredLoc = formatLocation(candidate.preferredLocation)

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#00A6FF]/20 to-[#7957FF]/15 border border-[var(--ei-border-primary)] flex items-center justify-center">
            <FiUser className="w-6 h-6 text-[var(--ei-text-secondary)]" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-[var(--ei-text-primary)]">
              {candidate.fullName || candidate.email || 'Candidate'}
            </h2>
            <p className="text-sm text-[var(--ei-text-muted)] font-mono">{candidateId}</p>
          </div>
        </div>
        {candidate.hasResume && (
          <button
            type="button"
            onClick={handleViewResume}
            disabled={resumeLoading}
            className="org-btn-primary text-sm !min-h-[42px]"
          >
            <FiFileText className="w-4 h-4" />
            {resumeLoading ? 'Opening…' : 'View Resume'}
          </button>
        )}
      </div>

      {!candidate.hasResume && (
        <p className="text-sm text-[var(--ei-text-muted)]">This candidate has not uploaded a resume.</p>
      )}

      <div className={sectionClass}>
        <h3 className={labelClass}>Contact</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
          <div>
            <p className={`${metaClass} flex items-center gap-1.5`}><FiMail className="w-3.5 h-3.5" /> Email</p>
            <p className={valueClass}>{candidate.email || '—'}</p>
          </div>
          <div>
            <p className={`${metaClass} flex items-center gap-1.5`}><FiPhone className="w-3.5 h-3.5" /> Phone</p>
            <p className={valueClass}>{candidate.phone || '—'}</p>
          </div>
          <div className="sm:col-span-2">
            <p className={`${metaClass} flex items-center gap-1.5`}><FiMapPin className="w-3.5 h-3.5" /> Location</p>
            <p className={valueClass}>{currentLoc}</p>
            {preferredLoc !== '—' && preferredLoc !== currentLoc && (
              <p className={`${metaClass} mt-1`}>Preferred: {preferredLoc}</p>
            )}
          </div>
        </div>
      </div>

      <div className={sectionClass}>
        <h3 className={labelClass}>Professional</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
          <div>
            <p className={metaClass}>Experience level</p>
            <p className={valueClass}>{candidate.experienceLevel || '—'}</p>
          </div>
          <div>
            <p className={metaClass}>Notice period</p>
            <p className={valueClass}>{candidate.noticePeriod || candidate.servingNotice || '—'}</p>
          </div>
        </div>
      </div>

      {Array.isArray(candidate.experiences) && candidate.experiences.length > 0 && (
        <div className={sectionClass}>
          <h3 className={`${labelClass} flex items-center gap-2`}><FiBriefcase className="w-4 h-4" /> Experience</h3>
          <ul className="mt-3 space-y-3">
            {candidate.experiences.map((exp, i) => (
              <li key={i} className="text-sm text-[var(--ei-text-secondary)] pl-2 border-l-2 border-[var(--ei-border-primary)]">
                <span className="font-medium text-[var(--ei-text-primary)]">{exp.role || '—'}</span>
                {exp.company && <span className="text-[var(--ei-text-muted)]"> at {exp.company}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {Array.isArray(candidate.education) && candidate.education.length > 0 && (
        <div className={sectionClass}>
          <h3 className={`${labelClass} flex items-center gap-2`}><FiBook className="w-4 h-4" /> Education</h3>
          <ul className="mt-3 space-y-3">
            {candidate.education.map((edu, i) => (
              <li key={i} className="text-sm text-[var(--ei-text-secondary)] pl-2 border-l-2 border-[var(--ei-border-primary)]">
                <span className="font-medium text-[var(--ei-text-primary)]">{edu.degree || '—'}</span>
                {edu.institution && <span className="text-[var(--ei-text-muted)]">, {edu.institution}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {Array.isArray(candidate.certifications) && candidate.certifications.length > 0 && (
        <div className={sectionClass}>
          <h3 className={`${labelClass} flex items-center gap-2`}><FiAward className="w-4 h-4" /> Certifications</h3>
          <ul className="mt-3 space-y-2">
            {candidate.certifications.map((cert, i) => (
              <li key={i} className="text-sm text-[var(--ei-text-secondary)]">
                <span className="font-medium text-[var(--ei-text-primary)]">{cert.certification || '—'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {candidate.joinedAt && (
        <p className="text-sm text-[var(--ei-text-muted)]">Joined {formatDate(candidate.joinedAt)}</p>
      )}
    </div>
  )
}
