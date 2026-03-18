import React from 'react'

function getBarColorClass(pct) {
  const n = Number(pct)
  if (n <= 30) return 'bg-red-500'
  if (n <= 70) return 'bg-amber-500'
  return 'bg-emerald-500'
}

export default function ScoreCard({ factorName, scorePct, weightPct }) {
  const score = Math.round(Number(scorePct) || 0)
  const weight = Math.round(Number(weightPct) || 0)
  const barColor = getBarColorClass(score)

  return (
    <div
      className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/80 p-4 shadow-card"
      role="article"
      aria-label={`${factorName}: ${score}% score, weight ${weight}%`}
    >
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <span className="text-sm font-medium text-slate-900 dark:text-white truncate">{factorName}</span>
        <span className="flex-shrink-0 text-lg font-bold tabular-nums text-slate-900 dark:text-white">{score}%</span>
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 mb-2">
        <span>Weight</span>
        <span className="font-medium text-slate-600 dark:text-slate-300">{weight}%</span>
      </div>
      <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden" role="progressbar" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100}>
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
    </div>
  )
}
