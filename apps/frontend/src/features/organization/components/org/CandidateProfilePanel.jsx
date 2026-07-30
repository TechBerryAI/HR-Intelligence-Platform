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

  const sectionClass = 'rounded-[14px] bg-white/[0.03] border border-white/[0.08] p-4'
  const labelClass = 'text-xs font-semibold text-[#83909C] uppercase tracking-[0.08em]'
  const valueClass = 'text-sm text-[#DCE3EA] mt-0.5'
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
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#00A6FF]/30 to-[#7957FF]/25 border border-white/[0.08] flex items-center justify-center">
            <FiUser className="w-6 h-6 text-[#A0ABB6]" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-[#F5F7FA]">{candidate.fullName || candidate.email || 'Candidate'}</h2>
            <p className="text-sm text-[#738394] font-mono">{candidateId}</p>
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
        <p className="text-sm text-[#8796A5]">This candidate has not uploaded a resume.</p>
      )}

      <div className={sectionClass}>
        <h3 className={labelClass}>Contact</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
          <div>
            <p className="text-[#738394] text-xs flex items-center gap-1.5"><FiMail className="w-3.5 h-3.5" /> Email</p>
            <p className={valueClass}>{candidate.email || '—'}</p>
          </div>
          <div>
            <p className="text-[#738394] text-xs flex items-center gap-1.5"><FiPhone className="w-3.5 h-3.5" /> Phone</p>
            <p className={valueClass}>{candidate.phone || '—'}</p>
          </div>
          <div className="sm:col-span-2">
            <p className="text-[#738394] text-xs flex items-center gap-1.5"><FiMapPin className="w-3.5 h-3.5" /> Location</p>
            <p className={valueClass}>{currentLoc}</p>
            {preferredLoc !== '—' && preferredLoc !== currentLoc && (
              <p className="text-[#738394] text-xs mt-1">Preferred: {preferredLoc}</p>
            )}
          </div>
        </div>
      </div>

      <div className={sectionClass}>
        <h3 className={labelClass}>Professional</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
          <div>
            <p className="text-[#738394] text-xs">Experience level</p>
            <p className={valueClass}>{candidate.experienceLevel || '—'}</p>
          </div>
          <div>
            <p className="text-[#738394] text-xs">Notice period</p>
            <p className={valueClass}>{candidate.noticePeriod || candidate.servingNotice || '—'}</p>
          </div>
        </div>
      </div>

      {Array.isArray(candidate.experiences) && candidate.experiences.length > 0 && (
        <div className={sectionClass}>
          <h3 className={`${labelClass} flex items-center gap-2`}><FiBriefcase className="w-4 h-4" /> Experience</h3>
          <ul className="mt-3 space-y-3">
            {candidate.experiences.map((exp, i) => (
              <li key={i} className="text-sm text-[#A0ABB6] pl-2 border-l-2 border-white/[0.1]">
                <span className="font-medium text-[#F2F5F8]">{exp.role || '—'}</span>
                {exp.company && <span className="text-[#738394]"> at {exp.company}</span>}
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
              <li key={i} className="text-sm text-[#A0ABB6] pl-2 border-l-2 border-white/[0.1]">
                <span className="font-medium text-[#F2F5F8]">{edu.degree || '—'}</span>
                {edu.institution && <span className="text-[#738394]">, {edu.institution}</span>}
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
              <li key={i} className="text-sm text-[#A0ABB6]">
                <span className="font-medium text-[#F2F5F8]">{cert.certification || '—'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {candidate.joinedAt && (
        <p className="text-sm text-[#738394]">Joined {formatDate(candidate.joinedAt)}</p>
      )}
    </div>
  )
}
