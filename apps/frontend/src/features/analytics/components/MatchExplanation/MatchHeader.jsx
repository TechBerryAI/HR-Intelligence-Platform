import React from 'react'
import { FiX, FiCheck, FiSlash } from 'react-icons/fi'

function ScoreRing({ score, size = 100, isMatch }) {
  const pct = Math.min(100, Math.max(0, Number(score) || 0))
  const stroke = 7
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const offset = c - (pct / 100) * c
  const color = isMatch ? '#37D6A0' : pct <= 30 ? '#FF5D73' : pct <= 70 ? '#F5B94C' : '#37D6A0'

  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }} aria-label={`Match score ${pct} percent`}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 400ms ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[22px] font-bold tabular-nums text-[#F7FAFC] leading-none">{pct}%</span>
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8796A5] mt-1">Match</span>
      </div>
    </div>
  )
}

/**
 * @param {'default' | 'enterprise'} variant
 */
export default function MatchHeader({ score, candidateName, candidateEmail, verdict, onClose, variant = 'default' }) {
  const isMatch = verdict && !/not a match|ats failed/i.test(verdict)
  const verdictLabel = verdict ? verdict.replace(/_/g, ' ') : '—'
  const enterprise = variant === 'enterprise'

  if (enterprise) {
    return (
      <div className="px-5 sm:px-6 py-5 sm:py-6 border-b border-white/[0.08] bg-[rgba(16,23,30,0.5)]">
        <div className="flex flex-col sm:flex-row sm:items-center gap-5">
          <ScoreRing score={score} isMatch={!!isMatch} size={104} />

          <div className="min-w-0 flex-1">
            <h2 className="text-[20px] sm:text-[22px] font-bold text-[#F5F7FA] tracking-tight truncate" id="match-modal-title">
              {candidateName || 'Candidate'}
            </h2>
            {candidateEmail && (
              <p className="text-[13px] sm:text-sm text-[#8796A5] truncate mt-1">{candidateEmail}</p>
            )}
            <p className="text-xs text-[#738394] mt-2">Overall candidate-job compatibility</p>
          </div>

          <div
            className={`flex-shrink-0 inline-flex items-center gap-2 px-3 py-2 rounded-full text-xs font-semibold uppercase tracking-wide border ${
              isMatch
                ? 'bg-[rgba(55,214,160,0.08)] border-[rgba(55,214,160,0.28)] text-[#67DFB4]'
                : 'bg-[rgba(255,82,105,0.08)] border-[rgba(255,82,105,0.28)] text-[#FF758A]'
            }`}
            aria-label={`Verdict: ${verdictLabel}`}
          >
            {isMatch ? <FiCheck className="w-3.5 h-3.5" /> : <FiSlash className="w-3.5 h-3.5" />}
            <span>{verdictLabel}</span>
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="flex-shrink-0 self-start sm:self-center p-2 rounded-[10px] text-[#8796A5] hover:text-white hover:bg-white/[0.05] transition-all duration-[180ms] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3AA9FF]/40"
              aria-label="Close modal"
            >
              <FiX className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="sticky top-0 z-10 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700 px-6 py-4 flex flex-wrap items-center gap-4">
      <div className="flex items-center gap-4 flex-wrap flex-1 min-w-0">
        <div
          className="flex-shrink-0 flex items-center justify-center min-w-[7rem] px-4 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700"
          aria-label={`Match score ${score} percent`}
        >
          <span className="text-2xl font-bold tabular-nums text-slate-900 dark:text-white">{score}%</span>
          <span className="ml-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Match</span>
        </div>

        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-bold text-slate-900 dark:text-white truncate" id="match-modal-title">
            {candidateName || 'Candidate'}
          </h2>
          {candidateEmail && (
            <p className="text-sm text-slate-500 dark:text-slate-400 truncate mt-0.5">{candidateEmail}</p>
          )}
        </div>

        <div
          className={`flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-semibold text-sm border ${
            isMatch
              ? 'bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/40'
              : 'bg-red-50 dark:bg-red-500/20 text-red-700 dark:text-red-300 border-red-200 dark:border-red-500/40'
          }`}
          aria-label={`Verdict: ${verdictLabel}`}
        >
          {isMatch ? <><span aria-hidden>✅</span><span>Match</span></> : <><span aria-hidden>❌</span><span>Not a Match</span></>}
        </div>
      </div>

      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="flex-shrink-0 p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus:outline-none focus:ring-2 focus:ring-accent-blue/30"
          aria-label="Close modal"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  )
}
