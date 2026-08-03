import React, { useEffect, useState } from 'react'
import { Bot, CalendarClock, Copy, Check, Link2 } from 'lucide-react'
import {
  cancelInterview,
  listApplicationInterviews,
  scheduleInterview,
} from '@/features/interview/services/interviewService.js'

function formatWhen(ts) {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return String(ts)
  }
}

export default function ScheduleInterviewPanel({ applicationId, candidateName, jobTitle, readOnly = false }) {
  const [interviews, setInterviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [scheduling, setScheduling] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [copiedId, setCopiedId] = useState('')
  const [interviewerType, setInterviewerType] = useState('ai')
  const [scheduledAt, setScheduledAt] = useState('')
  const [duration, setDuration] = useState(30)
  const [notes, setNotes] = useState('')

  const load = async () => {
    if (!applicationId) return
    setLoading(true)
    setError('')
    try {
      const res = await listApplicationInterviews(applicationId)
      setInterviews(res?.interviews || [])
    } catch (err) {
      setError(err?.message || 'Failed to load interviews')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [applicationId])

  const handleSchedule = async (e) => {
    e.preventDefault()
    if (!applicationId || scheduling || readOnly) return
    setScheduling(true)
    setError('')
    setMessage('')
    try {
      const created = await scheduleInterview({
        application_id: applicationId,
        interviewer_type: interviewerType,
        scheduled_at: scheduledAt || undefined,
        duration_minutes: Number(duration) || 30,
        notes,
      })
      setMessage(
        interviewerType === 'ai'
          ? 'AI interview scheduled. Share the candidate link below.'
          : 'Interview scheduled.',
      )
      setNotes('')
      await load()
      if (created?.candidate_link) {
        try {
          await navigator.clipboard.writeText(created.candidate_link)
          setCopiedId(created.id)
          setTimeout(() => setCopiedId(''), 2000)
        } catch {
          /* ignore clipboard errors */
        }
      }
    } catch (err) {
      setError(err?.data?.error || err?.message || 'Failed to schedule')
    } finally {
      setScheduling(false)
    }
  }

  const copyLink = async (interview) => {
    if (!interview?.candidate_link) return
    try {
      await navigator.clipboard.writeText(interview.candidate_link)
      setCopiedId(interview.id)
      setTimeout(() => setCopiedId(''), 2000)
    } catch {
      setError('Could not copy link')
    }
  }

  const handleCancel = async (id) => {
    if (readOnly) return
    try {
      await cancelInterview(id)
      await load()
    } catch (err) {
      setError(err?.data?.error || err?.message || 'Cancel failed')
    }
  }

  if (!applicationId) return null

  return (
    <section className="org-glass-card hover:transform-none p-5 sm:p-6 mt-5">
      <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-3">
          <span className="w-10 h-10 rounded-xl grid place-items-center bg-[rgba(0,166,255,0.12)] border border-[rgba(0,166,255,0.22)]">
            <Bot size={22} className="text-[var(--ei-accent-blue)]" />
          </span>
          <div>
            <h2 className="text-base font-semibold text-[#F5F7FA]">Interview scheduling</h2>
            <p className="text-xs text-[#8E9BA8] mt-0.5">
              {candidateName || 'Candidate'} · {jobTitle || 'Role'}
            </p>
          </div>
        </div>
      </div>

      {error && <div className="org-error-banner mb-3">{error}</div>}
      {message && (
        <div className="mb-3 rounded-xl border border-[rgba(54,214,160,0.3)] bg-[rgba(54,214,160,0.1)] px-3 py-2 text-sm text-[#67DFB4]">
          {message}
        </div>
      )}

      {!readOnly && (
        <form onSubmit={handleSchedule} className="space-y-4 mb-5 pb-5 border-b border-white/[0.08]">
          <div className="flex flex-wrap gap-2">
            {[
              { id: 'ai', label: 'AI interviewer', hint: 'No human joins — candidate answers AI questions' },
              { id: 'human', label: 'Human interviewer', hint: 'Schedule with a person' },
            ].map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setInterviewerType(opt.id)}
                className={`px-3 py-2 rounded-xl text-xs font-medium border transition-colors text-left ${
                  interviewerType === opt.id
                    ? 'bg-[rgba(0,166,255,0.16)] border-[rgba(0,166,255,0.35)] text-[#7DD3FF]'
                    : 'bg-white/[0.03] border-white/10 text-[#9CA8B5] hover:border-white/20'
                }`}
              >
                <span className="block font-semibold">{opt.label}</span>
                <span className="block opacity-80 mt-0.5 font-normal">{opt.hint}</span>
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="block text-xs text-[#8E9BA8]">
              Schedule time (optional)
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="mt-1.5 w-full org-select-input"
              />
            </label>
            <label className="block text-xs text-[#8E9BA8]">
              Duration (minutes)
              <input
                type="number"
                min={10}
                max={180}
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                className="mt-1.5 w-full org-select-input"
              />
            </label>
          </div>

          <label className="block text-xs text-[#8E9BA8]">
            Notes
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Optional notes for the hiring team"
              className="mt-1.5 w-full org-select-input min-h-[70px]"
            />
          </label>

          <button type="submit" disabled={scheduling} className="org-btn-primary disabled:opacity-50">
            <CalendarClock className="w-4 h-4" />
            {scheduling
              ? 'Scheduling…'
              : interviewerType === 'ai'
                ? 'Schedule AI interview'
                : 'Schedule interview'}
          </button>
        </form>
      )}

      <div>
        <h3 className="text-sm font-medium text-[#DCE3EA] mb-3">Scheduled sessions</h3>
        {loading ? (
          <div className="space-y-2">
            <div className="org-skeleton" />
            <div className="org-skeleton" />
          </div>
        ) : interviews.length === 0 ? (
          <p className="text-sm text-[#8E9BA8]">No interviews scheduled yet.</p>
        ) : (
          <ul className="space-y-2.5">
            {interviews.map((iv) => (
              <li
                key={iv.id}
                className="rounded-xl border border-white/[0.08] bg-white/[0.02] px-3.5 py-3"
              >
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-[#F5F7FA]">
                        {iv.interviewer_type === 'ai' ? 'AI interviewer' : 'Human interviewer'}
                      </span>
                      <span className="text-[11px] px-2 py-0.5 rounded-md bg-white/[0.06] text-[#A0ABB6]">
                        {iv.status}
                      </span>
                      {iv.overall_score != null && (
                        <span className="text-[11px] px-2 py-0.5 rounded-md bg-[rgba(0,166,255,0.12)] text-[#7DD3FF]">
                          Score {iv.overall_score}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[#8E9BA8] mt-1">{formatWhen(iv.scheduled_at)} · {iv.duration_minutes} min</p>
                    {iv.candidate_link && iv.status !== 'Cancelled' && (
                      <p className="text-xs text-[#71808E] mt-1 truncate flex items-center gap-1">
                        <Link2 className="w-3 h-3 shrink-0" />
                        {iv.candidate_link}
                      </p>
                    )}
                    {iv.score_summary && (
                      <pre className="mt-2 text-[11px] text-[#A0ABB6] whitespace-pre-wrap font-sans max-h-24 overflow-auto">
                        {iv.score_summary}
                      </pre>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {iv.candidate_link && iv.status !== 'Cancelled' && (
                      <button type="button" onClick={() => copyLink(iv)} className="org-btn-ghost !min-h-0 !py-1.5 !px-2.5 text-xs">
                        {copiedId === iv.id ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                        {copiedId === iv.id ? 'Copied' : 'Copy link'}
                      </button>
                    )}
                    {!readOnly && ['Scheduled', 'InProgress'].includes(iv.status) && (
                      <button
                        type="button"
                        onClick={() => handleCancel(iv.id)}
                        className="text-xs text-[#FF8FA3] hover:text-[#FFB0BC] px-2 py-1.5"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
