import React, { useState } from 'react'
import { Check, X } from 'lucide-react'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'

const DECIDED_STATUSES = new Set([
  'shortlisted',
  'interview',
  'offer',
  'hired',
  'rejected',
  'not shortlisted',
  'withdrawn',
])

export function canManuallyDecideApplication(application) {
  if (!application) return false
  if (application.shortlisted === true || application.shortlisted === 1) return false
  const status = String(application.status || '').toLowerCase().trim()
  return !DECIDED_STATUSES.has(status)
}

export function applicationDecisionLabel(application) {
  if (!application) return ''
  const status = String(application.status || '').toLowerCase().trim()
  if (application.shortlisted === true || application.shortlisted === 1 || status === 'shortlisted') {
    return 'Shortlisted'
  }
  if (status === 'interview') return 'Interview'
  if (status === 'offer') return 'Offer'
  if (status === 'hired') return 'Hired'
  if (status === 'rejected' || status === 'not shortlisted') return 'Rejected'
  if (status === 'withdrawn') return 'Withdrawn'
  return ''
}

export async function updateApplicationStatus(jobId, candidateId, action) {
  return apiRequest(
    `/api/jobs/${encodeURIComponent(jobId)}/applications/${encodeURIComponent(candidateId)}/status`,
    {
      method: 'PATCH',
      body: { action },
      token: tokenService.getToken(),
    },
  )
}

/**
 * Manual shortlist / reject for Head HR (hidden when readOnly / CEO).
 * Same API as recruiter Applied Candidates.
 */
export default function ApplicationStatusActions({
  jobId,
  candidateId,
  application,
  readOnly = false,
  compact = false,
  onUpdated,
}) {
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState('')

  if (readOnly || !jobId || !candidateId || !application) return null

  const decided = !canManuallyDecideApplication(application)
  const label = applicationDecisionLabel(application)
  const isPositive = label && !['Rejected', 'Withdrawn'].includes(label)

  const run = async (action) => {
    if (busy) return
    setError('')
    setBusy(action)
    try {
      const res = await updateApplicationStatus(jobId, candidateId, action)
      onUpdated?.({
        action,
        profileUpdate: res?.profile_update,
        shortlisted: action === 'shortlist',
        status: action === 'shortlist' ? 'Shortlisted' : 'Rejected',
      })
    } catch (err) {
      setError(err?.data?.error || err?.message || 'Failed to update status')
    } finally {
      setBusy(null)
    }
  }

  if (decided) {
    if (compact && !label) return null
    return (
      <span
        className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${
          isPositive
            ? 'border-[var(--ei-tone-success-border)] bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)]'
            : 'border-[var(--ei-tone-danger-border)] bg-[var(--ei-tone-danger-bg)] text-[var(--ei-tone-danger)]'
        }`}
      >
        {label || 'Decided'}
      </span>
    )
  }

  const btnBase = compact
    ? 'inline-flex items-center justify-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold border transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
    : 'inline-flex items-center justify-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-semibold border transition-colors disabled:opacity-50 disabled:cursor-not-allowed'

  return (
    <div className={compact ? 'inline-flex flex-col items-end gap-1' : 'flex flex-col items-stretch sm:items-end gap-2'}>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => run('shortlist')}
          disabled={!!busy}
          className={`${btnBase} border-[var(--ei-tone-success-border)] bg-[var(--ei-tone-success-bg)] text-[var(--ei-tone-success)] hover:brightness-110`}
        >
          <Check className={compact ? 'w-3.5 h-3.5' : 'w-4 h-4'} strokeWidth={2.2} />
          {busy === 'shortlist' ? 'Updating…' : 'Shortlist'}
        </button>
        <button
          type="button"
          onClick={() => run('reject')}
          disabled={!!busy}
          className={`${btnBase} border-[var(--ei-tone-danger-border)] bg-[var(--ei-tone-danger-bg)] text-[var(--ei-tone-danger)] hover:brightness-110`}
        >
          <X className={compact ? 'w-3.5 h-3.5' : 'w-4 h-4'} strokeWidth={2.2} />
          {busy === 'reject' ? 'Updating…' : 'Reject'}
        </button>
      </div>
      {error ? <p className="text-xs text-[var(--ei-tone-danger)] max-w-[16rem] text-right">{error}</p> : null}
      {!compact && !error ? (
        <p className="text-[11px] text-[var(--ei-text-muted)] text-right max-w-[16rem]">
          Shortlist sends the invite email. Reject updates status only.
        </p>
      ) : null}
    </div>
  )
}
