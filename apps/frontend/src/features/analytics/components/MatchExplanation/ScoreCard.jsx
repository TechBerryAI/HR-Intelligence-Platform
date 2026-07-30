import React from 'react'

/** Existing UI score-band colors for progress bars (presentation only). */
function getBarColor(pct) {
  const n = Number(pct)
  if (n <= 30) return '#FF5D73'
  if (n <= 70) return '#F5B94C'
  return '#37D6A0'
}

function getBarColorClass(pct) {
  const n = Number(pct)
  if (n <= 30) return 'bg-red-500'
  if (n <= 70) return 'bg-amber-500'
  return 'bg-emerald-500'
}

/**
 * @param {'default' | 'enterprise'} variant
 * @param {string} [badge] optional pill e.g. MANDATORY
 */
export default function ScoreCard({ factorName, scorePct, weightPct, variant = 'default', badge }) {
  const score = Math.round(Number(scorePct) || 0)
  const weight = Math.round(Number(weightPct) || 0)
  const enterprise = variant === 'enterprise'
  const barColor = getBarColor(score)
  const barColorClass = getBarColorClass(score)

  if (enterprise) {
    return (
      <div
        className="rounded-[14px] border border-white/[0.07] bg-white/[0.03] p-[18px] transition-all duration-[180ms] hover:bg-white/[0.045] hover:-translate-y-px"
        role="article"
        aria-label={`${factorName}: ${score}% score, weight ${weight}%`}
      >
        <div className="flex items-baseline justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm font-medium text-[#DCE3EA] truncate">{factorName}</span>
            {badge && (
              <span className="flex-shrink-0 text-[9px] font-semibold uppercase tracking-[0.08em] px-1.5 py-0.5 rounded-full bg-[rgba(255,93,115,0.1)] border border-[rgba(255,93,115,0.22)] text-[#FF788B]">
                {badge}
              </span>
            )}
          </div>
          <span className="flex-shrink-0 text-[22px] font-bold tabular-nums text-[#F7FAFC] leading-none">{score}%</span>
        </div>
        <p className="text-xs text-[#758596] mb-3">Weight {weight}%</p>
        <div
          className="h-1.5 rounded-full bg-white/[0.08] overflow-hidden"
          role="progressbar"
          aria-valuenow={score}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{ width: `${Math.min(100, Math.max(0, score))}%`, backgroundColor: barColor }}
          />
        </div>
      </div>
    )
  }

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
          className={`h-full rounded-full transition-all duration-300 ${barColorClass}`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
    </div>
  )
}
