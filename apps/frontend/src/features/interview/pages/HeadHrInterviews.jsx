import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import HeadHrLayout from '@/features/organization/pages/head-hr/HeadHrLayout.jsx'
import { listInterviews } from '@/features/interview/services/interviewService.js'
import { Bot, CalendarClock, Copy, Check } from 'lucide-react'
import { useAsyncAction } from '@/shared/hooks/useAsyncAction.js'
import { FiRefreshCw } from 'react-icons/fi'

const Spinner = () => (
  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
)

function formatWhen(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export default function HeadHrInterviews() {
  const navigate = useNavigate()
  const [interviews, setInterviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copiedId, setCopiedId] = useState('')
  const { run: runRefresh, loading: refreshLoading } = useAsyncAction()

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await listInterviews()
      setInterviews(res?.interviews || [])
    } catch (err) {
      setError(err?.message || 'Failed to load interviews')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const copyLink = async (iv) => {
    if (!iv?.candidate_link) return
    try {
      await navigator.clipboard.writeText(iv.candidate_link)
      setCopiedId(iv.id)
      setTimeout(() => setCopiedId(''), 2000)
    } catch {
      setError('Could not copy link')
    }
  }

  return (
    <HeadHrLayout>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="org-page-title flex items-center gap-2.5">
            <CalendarClock size={32} className="org-page-icon" />
            Interviews
          </h1>
          <p className="org-page-subtitle">
            {interviews.length} scheduled session{interviews.length !== 1 ? 's' : ''} · AI & human interviewers
          </p>
        </div>
        <button
          type="button"
          onClick={() => runRefresh(load)}
          disabled={refreshLoading}
          className="org-btn-secondary"
        >
          {refreshLoading ? <Spinner /> : <FiRefreshCw className="w-4 h-4" />}
          {refreshLoading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && <div className="org-error-banner mb-4">{error}</div>}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="org-skeleton" />
          ))}
        </div>
      ) : interviews.length === 0 ? (
        <div className="org-empty-state">
          No interviews yet. Open a candidate application and schedule an AI interview.
        </div>
      ) : (
        <div className="org-table-wrap">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="org-table-head">
                  <th className="org-th">Candidate</th>
                  <th className="org-th">Job</th>
                  <th className="org-th">Type</th>
                  <th className="org-th">Status</th>
                  <th className="org-th">Scheduled</th>
                  <th className="org-th">Score</th>
                  <th className="org-th text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {interviews.map((iv) => (
                  <tr key={iv.id} className="org-table-row">
                    <td className="org-td-primary">
                      <div className="font-medium">{iv.candidate_name || '—'}</div>
                      <div className="text-xs text-[#8E9BA8]">{iv.candidate_email || ''}</div>
                    </td>
                    <td className="org-td-secondary">{iv.job_title || '—'}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1.5 text-xs text-[#A0ABB6]">
                        {iv.interviewer_type === 'ai' ? <Bot className="w-3.5 h-3.5 text-[#00A6FF]" /> : null}
                        {iv.interviewer_type === 'ai' ? 'AI' : 'Human'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-2 py-0.5 rounded-md bg-white/[0.06] text-[#A0ABB6]">
                        {iv.status}
                      </span>
                    </td>
                    <td className="org-td-muted text-xs">{formatWhen(iv.scheduled_at)}</td>
                    <td className="org-td-secondary tabular-nums">
                      {iv.overall_score != null ? iv.overall_score : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-2 justify-end">
                        {iv.candidate_link && iv.status !== 'Cancelled' && (
                          <button type="button" onClick={() => copyLink(iv)} className="org-btn-ghost !py-1.5 !px-2.5 text-xs">
                            {copiedId === iv.id ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                            Link
                          </button>
                        )}
                        {iv.application_id && iv.job_title && (
                          <button
                            type="button"
                            className="text-xs text-[#7DD3FF] hover:underline"
                            onClick={() => navigate('/head-hr/jobs')}
                          >
                            Jobs
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </HeadHrLayout>
  )
}
