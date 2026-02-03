import React from 'react'

/**
 * Sticky header for the Candidate Match Explanation modal.
 * Decision-first: Match %, candidate name, email, verdict badge.
 */
export default function MatchHeader({ score, candidateName, candidateEmail, verdict, onClose }) {
  const isMatch = verdict && !/not a match/i.test(verdict)
  const verdictLabel = verdict ? verdict.replace(/_/g, ' ') : '—'

  return (
    <div className="sticky top-0 z-10 bg-zinc-900 border-b border-zinc-800 px-6 py-4 flex flex-wrap items-center gap-4">
      <div className="flex items-center gap-4 flex-wrap flex-1 min-w-0">
        {/* Large Match % Badge */}
        <div
          className="flex-shrink-0 flex items-center justify-center min-w-[7rem] px-4 py-2.5 rounded-lg bg-zinc-800 ring-1 ring-zinc-700"
          aria-label={`Match score ${score} percent`}
        >
          <span className="text-2xl font-bold tabular-nums text-white">{score}%</span>
          <span className="ml-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-400">Match</span>
        </div>

        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-bold text-white truncate" id="match-modal-title">
            {candidateName || 'Candidate'}
          </h2>
          {candidateEmail && (
            <p className="text-sm text-zinc-400 truncate mt-0.5">{candidateEmail}</p>
          )}
        </div>

        {/* Verdict badge */}
        <div
          className={`flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold text-sm ${
            isMatch
              ? 'bg-emerald-900/40 text-emerald-300 ring-1 ring-emerald-700/60'
              : 'bg-red-900/40 text-red-300 ring-1 ring-red-700/60'
          }`}
          aria-label={`Verdict: ${verdictLabel}`}
        >
          {isMatch ? (
            <>
              <span aria-hidden>✅</span>
              <span>Match</span>
            </>
          ) : (
            <>
              <span aria-hidden>❌</span>
              <span>Not a Match</span>
            </>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={onClose}
        className="flex-shrink-0 p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors focus:outline-none focus:ring-2 focus:ring-white/20"
        aria-label="Close modal"
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
