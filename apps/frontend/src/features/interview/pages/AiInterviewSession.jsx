import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Bot, Loader2, Send, Sparkles } from 'lucide-react'
import {
  completePublicSession,
  getPublicSession,
  startPublicSession,
  submitPublicAnswer,
} from '@/features/interview/services/interviewService.js'

export default function AiInterviewSession() {
  const { token } = useParams()
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [answer, setAnswer] = useState('')
  const [lastFeedback, setLastFeedback] = useState('')
  const [started, setStarted] = useState(false)
  const [result, setResult] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await getPublicSession(token)
        if (cancelled) return
        setSession(data)
        if (data.status === 'Completed') {
          setResult({
            overall_score: data.overall_score,
            score_summary: data.score_summary,
          })
        }
        if (data.status === 'InProgress') setStarted(true)
      } catch (err) {
        if (!cancelled) setError(err?.data?.error || err?.message || 'Interview not found')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [token])

  const handleStart = async () => {
    setBusy(true)
    setError('')
    try {
      const data = await startPublicSession(token)
      setStarted(true)
      setSession((prev) => ({ ...prev, ...data }))
    } catch (err) {
      setError(err?.data?.error || err?.message || 'Could not start interview')
    } finally {
      setBusy(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!answer.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      const data = await submitPublicAnswer(token, answer.trim())
      setAnswer('')
      setLastFeedback(data.last_feedback || '')
      setSession((prev) => ({
        ...prev,
        answered_count: data.answered_count,
        question_count: data.question_count,
        current_question: data.current_question,
        done: data.done,
      }))
      if (data.done) {
        const finished = await completePublicSession(token)
        setResult(finished)
        setSession((prev) => ({ ...prev, status: 'Completed' }))
      }
    } catch (err) {
      setError(err?.data?.error || err?.message || 'Failed to submit answer')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B1118] text-[#F5F7FA] flex items-center justify-center p-6">
        <Loader2 className="w-6 h-6 animate-spin text-[#00A6FF]" />
      </div>
    )
  }

  if (error && !session) {
    return (
      <div className="min-h-screen bg-[#0B1118] text-[#F5F7FA] flex items-center justify-center p-6">
        <div className="max-w-md w-full rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-sm text-red-300">
          {error}
        </div>
      </div>
    )
  }

  const progress =
    session?.question_count > 0
      ? Math.round(((session.answered_count || 0) / session.question_count) * 100)
      : 0

  return (
    <div className="min-h-screen bg-[#0B1118] text-[#F5F7FA]">
      <div
        className="pointer-events-none fixed inset-0"
        style={{
          backgroundImage:
            'radial-gradient(circle at top right, rgba(0,153,255,0.12), transparent 35%), radial-gradient(circle at bottom left, rgba(92,69,255,0.08), transparent 40%)',
        }}
      />
      <div className="relative max-w-2xl mx-auto px-5 py-10 sm:py-14">
        <div className="flex items-center gap-3 mb-8">
          <span className="w-11 h-11 rounded-xl grid place-items-center bg-[rgba(0,166,255,0.12)] border border-[rgba(0,166,255,0.25)]">
            <Bot size={24} className="text-[#00A6FF]" />
          </span>
          <div>
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#83909C] font-semibold">AI interviewer</p>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight">
              {session?.job_title || 'Interview'}
            </h1>
            <p className="text-sm text-[#8E9BA8]">
              {session?.job_company || 'HR Intelligence'}
              {session?.candidate_name ? ` · ${session.candidate_name}` : ''}
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        {result || session?.status === 'Completed' ? (
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-6 space-y-3">
            <div className="flex items-center gap-2 text-[#36D6A0]">
              <Sparkles className="w-5 h-5" />
              <h2 className="text-lg font-semibold text-[#F5F7FA]">Interview complete</h2>
            </div>
            <p className="text-3xl font-bold tabular-nums text-[#00A6FF]">
              {result?.overall_score ?? session?.overall_score ?? '—'}
              <span className="text-base font-medium text-[#8E9BA8]"> / 100</span>
            </p>
            <p className="text-sm text-[#A0ABB6] whitespace-pre-wrap">
              {result?.score_summary || session?.score_summary || 'Thank you for completing the AI interview. The hiring team will review your responses.'}
            </p>
          </div>
        ) : !started ? (
          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-6 space-y-4">
            <p className="text-sm text-[#A0ABB6] leading-relaxed">
              This interview is conducted entirely by an AI interviewer. No human will join the session.
              You will answer {session?.question_count || 'several'} questions one at a time. Take about{' '}
              {session?.duration_minutes || 30} minutes in a quiet place.
            </p>
            <button
              type="button"
              onClick={handleStart}
              disabled={busy || session?.status === 'Cancelled'}
              className="inline-flex items-center justify-center gap-2 min-h-[46px] px-5 rounded-xl font-semibold text-white bg-gradient-to-br from-[#00A6FF] to-[#276DFF] disabled:opacity-50"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bot className="w-4 h-4" />}
              Start AI interview
            </button>
          </div>
        ) : (
          <div className="space-y-5">
            <div>
              <div className="flex justify-between text-xs text-[#8E9BA8] mb-1.5">
                <span>
                  Question {(session?.answered_count || 0) + (session?.done ? 0 : 1)} of {session?.question_count}
                </span>
                <span>{progress}%</span>
              </div>
              <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#00A6FF] to-[#276DFF] transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {lastFeedback && (
              <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] px-3.5 py-2.5 text-xs text-[#A0ABB6]">
                <span className="text-[#7DD3FF] font-medium">AI note: </span>
                {lastFeedback}
              </div>
            )}

            {session?.current_question && (
              <div className="rounded-2xl border border-[rgba(0,166,255,0.25)] bg-[rgba(0,166,255,0.06)] p-5">
                {session.current_question.category && (
                  <p className="text-[11px] uppercase tracking-wide text-[#7DD3FF] mb-2">
                    {session.current_question.category}
                  </p>
                )}
                <p className="text-base sm:text-lg font-medium leading-relaxed">
                  {session.current_question.question}
                </p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-3">
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={6}
                placeholder="Type your answer here…"
                className="w-full rounded-xl bg-white/[0.04] border border-white/10 px-4 py-3 text-sm text-[#F5F7FA] placeholder:text-[#6f7d89] focus:outline-none focus:border-[#3aa9ff]"
                disabled={busy || session?.done}
              />
              <button
                type="submit"
                disabled={busy || !answer.trim() || session?.done}
                className="inline-flex items-center justify-center gap-2 min-h-[46px] px-5 rounded-xl font-semibold text-white bg-gradient-to-br from-[#00A6FF] to-[#276DFF] disabled:opacity-45"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                {busy ? 'Evaluating…' : 'Submit answer'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}
