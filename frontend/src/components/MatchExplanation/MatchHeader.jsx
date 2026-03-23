import React from 'react'

export default function MatchHeader({ score, candidateName, candidateEmail, verdict, onClose }) {
  const isMatch = verdict && !/not a match/i.test(verdict)
  const verdictLabel = verdict ? verdict.replace(/_/g, ' ') : '—'

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
    </div>
  )
}
