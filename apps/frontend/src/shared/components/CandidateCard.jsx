import React, { useMemo } from 'react'
import { getAvatarGradient } from '@/shared/utils/avatarColor.js'

const getScoreInfo = (score) => {
  if (score >= 80) return { color: 'text-emerald-500 dark:text-emerald-400', bgColor: 'bg-emerald-500/15', borderColor: 'border-emerald-500/40', label: 'Excellent Match' }
  if (score >= 70) return { color: 'text-emerald-500 dark:text-emerald-400', bgColor: 'bg-emerald-500/12', borderColor: 'border-emerald-500/30', label: 'Great Match' }
  if (score >= 60) return { color: 'text-blue-500 dark:text-blue-400', bgColor: 'bg-blue-500/15', borderColor: 'border-blue-500/40', label: 'Good Match' }
  if (score >= 50) return { color: 'text-cyan-600 dark:text-cyan-400', bgColor: 'bg-cyan-500/15', borderColor: 'border-cyan-500/40', label: 'Fair Match' }
  if (score >= 40) return { color: 'text-amber-600 dark:text-amber-400', bgColor: 'bg-amber-500/15', borderColor: 'border-amber-500/40', label: 'Moderate Match' }
  if (score >= 30) return { color: 'text-orange-600 dark:text-orange-400', bgColor: 'bg-orange-500/15', borderColor: 'border-orange-500/40', label: 'Low Match' }
  return { color: 'text-red-600 dark:text-red-400', bgColor: 'bg-red-500/15', borderColor: 'border-red-500/40', label: 'Poor Match' }
}

const formatDate = (dateString) => {
  if (!dateString) return 'N/A'
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return dateString
  }
}

export default function CandidateCard({ candidate, onViewDetails, onViewReason }) {
  const rawScore = candidate.matchScore || candidate.score || 0
  const score = Math.round(Number(rawScore))
  const scoreInfo = getScoreInfo(score)
  const avatarGradient = useMemo(() => {
    const key = candidate.email || candidate.fullName || candidate.name || candidate.candidateId || candidate.id || ''
    return getAvatarGradient(key)
  }, [candidate])

  const name = candidate.fullName || candidate.name || 'Unknown Candidate'
  const email = candidate.email || ''
  const location = candidate.currentLocation || null
  const experience = candidate.experienceLevel ? candidate.experienceLevel.replace(/_/g, ' ') : null
  const appliedAt = candidate.appliedAt ? formatDate(candidate.appliedAt) : null
  const educationLine = candidate.education?.[0]
    ? [candidate.education[0].degree, candidate.education[0].institution].filter(Boolean).join(' · ')
    : null

  const metaParts = [location, experience, appliedAt && `Applied ${appliedAt}`].filter(Boolean)

  return (
    <article className="group relative org-glass-card p-5">
      {/* Top row: Avatar + Name + Match badge */}
      <div className="flex items-start gap-3">
        <div
          className="flex-shrink-0 w-11 h-11 rounded-full flex items-center justify-center text-white font-semibold text-base ring-2 ring-[var(--ei-border-primary)]"
          style={{ backgroundImage: avatarGradient }}
        >
          {name.charAt(0).toUpperCase() || 'C'}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold text-[var(--ei-text-primary)] truncate pr-2">{name}</h3>
          {email && (
            <p className="text-sm text-[var(--ei-text-muted)] truncate mt-0.5" title={email}>{email}</p>
          )}
        </div>
        {/* Single consolidated match badge */}
        <div
          className={`flex-shrink-0 flex flex-col items-center justify-center min-w-[4rem] px-3 py-2 rounded-lg ${scoreInfo.bgColor} border ${scoreInfo.borderColor}`}
          aria-label={`Match score ${score}%, ${scoreInfo.label}`}
        >
          <span className={`text-xl font-bold tabular-nums leading-tight ${scoreInfo.color}`}>{score}%</span>
          <span className={`text-[10px] font-medium uppercase tracking-wider mt-0.5 ${scoreInfo.color} opacity-90`}>
            {scoreInfo.label.replace(/\s+Match\s*$/, '').trim() || 'Match'}
          </span>
        </div>
      </div>

      {/* One-line meta: Location · Experience · Applied */}
      {metaParts.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-[var(--ei-text-muted)]">
          {metaParts.map((part, i) => (
            <span key={i} className="truncate">
              {part}
              {i < metaParts.length - 1 && <span className="text-[var(--ei-text-muted)] mx-1 opacity-50">·</span>}
            </span>
          ))}
        </div>
      )}

      {/* Education as compact chip or line */}
      {educationLine && (
        <div className="mt-2">
          <span className="inline-block max-w-full px-2.5 py-1 rounded-md bg-[var(--ei-surface-hover)] text-xs text-[var(--ei-text-secondary)] truncate" title={educationLine}>
            {educationLine.length > 48 ? `${educationLine.slice(0, 48)}…` : educationLine}
          </span>
        </div>
      )}

      {candidate.phone && (
        <p className="mt-1.5 text-xs text-[var(--ei-text-muted)] truncate" title={candidate.phone}>{candidate.phone}</p>
      )}

      {/* Actions */}
      <div className="mt-4 pt-4 border-t border-[var(--ei-border-primary)] flex gap-2">
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onViewReason?.(candidate)
          }}
          className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-violet-500/20 hover:bg-violet-500/30 text-violet-700 dark:text-violet-200 font-medium text-sm transition-colors ring-1 ring-violet-500/30"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 shrink-0">
            <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm8.706-1.442c1.146-.573 2.437.463 2.126 1.706l-.709 2.836.042-.02a.75.75 0 0 1 .67 1.34l-.04.022c-1.147.573-2.438-.463-2.127-1.706l.71-2.836-.042.02a.75.75 0 1 1-.671-1.34l.041-.022ZM12 9a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Z" clipRule="evenodd" />
          </svg>
          <span>View Reason</span>
        </button>
        <button
          type="button"
          onClick={() => onViewDetails?.(candidate)}
          className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[var(--ei-surface-hover)] hover:bg-[var(--ei-border-hover)] text-[var(--ei-text-primary)] font-medium text-sm transition-colors ring-1 ring-[var(--ei-border-primary)]"
        >
          <span>Profile</span>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 shrink-0 transition-transform group-hover:translate-x-0.5">
            <path fillRule="evenodd" d="M16.28 11.47a.75.75 0 0 1 0 1.06l-7.5 7.5a.75.75 0 0 1-1.06-1.06L14.69 12 7.72 5.03a.75.75 0 0 1 1.06-1.06l7.5 7.5Z" clipRule="evenodd" />
          </svg>
        </button>
      </div>
    </article>
  )
}
