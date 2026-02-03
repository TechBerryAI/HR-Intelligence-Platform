import React from 'react'

/**
 * Bar color by score: red 0–30%, yellow 31–70%, green 71–100%.
 */
function getBarColorClass(pct) {
  const n = Number(pct)
  if (n <= 30) return 'bg-red-500'
  if (n <= 70) return 'bg-amber-500'
  return 'bg-emerald-500'
}

/**
 * Single factor card: name, score %, weight %, horizontal progress bar.
 */
export default function ScoreCard({ factorName, scorePct, weightPct }) {
  const score = Math.round(Number(scorePct) || 0)
  const weight = Math.round(Number(weightPct) || 0)
  const barColor = getBarColorClass(score)

  return (
    <div
      className="bg-zinc-800/50 rounded-xl p-4 ring-1 ring-zinc-700/50"
      role="article"
      aria-label={`${factorName}: ${score}% score, weight ${weight}%`}
    >
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <span className="text-sm font-medium text-white truncate">{factorName}</span>
        <span className="flex-shrink-0 text-lg font-bold tabular-nums text-white">{score}%</span>
      </div>
      <div className="flex items-center gap-2 text-xs text-zinc-400 mb-2">
        <span>Weight</span>
        <span className="font-medium text-zinc-300">{weight}%</span>
      </div>
      <div className="h-2 rounded-full bg-zinc-700 overflow-hidden" role="progressbar" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100}>
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
    </div>
  )
}
