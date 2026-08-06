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
 * @param {string} [badge] optional pill e.g. GATE FAIL
 * @param {string} [reason] plain-English why this score (preferred over weight display)
 */
export default function ScoreCard({ factorName, scorePct, weightPct, variant = 'default', badge, reason }) {
  const score = Math.round(Number(scorePct) || 0)
  const weight = Math.round(Number(weightPct) || 0)
  const enterprise = variant === 'enterprise'
  const barColor = getBarColor(score)
  const barColorClass = getBarColorClass(score)
  const subtitle = reason || (weight ? `How much this area matters in the overall fit` : '')

  if (enterprise) {
    return (
      <div
        className="rounded-[14px] border border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)] p-[18px] transition-all duration-[180ms] hover:border-[var(--ei-border-hover)] hover:-translate-y-px"
        role="article"
        aria-label={`${factorName}: ${score}%`}
      >
        <div className="flex items-baseline justify-between gap-2 mb-1.5">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm font-medium text-[var(--ei-text-primary)] truncate">{factorName}</span>
            {badge && (
              <span
                className="flex-shrink-0 text-[9px] font-semibold uppercase tracking-[0.08em] px-1.5 py-0.5 rounded-full border"
                style={{
                  background: 'var(--ei-tone-danger-bg)',
                  borderColor: 'var(--ei-tone-danger-border)',
                  color: 'var(--ei-tone-danger)',
                }}
              >
                {badge}
              </span>
            )}
          </div>
          <span className="flex-shrink-0 text-[22px] font-bold tabular-nums text-[var(--ei-text-primary)] leading-none">{score}%</span>
        </div>
        {subtitle && (
          <p className="text-xs text-[var(--ei-text-muted)] mb-3 line-clamp-2">{subtitle}</p>
        )}
        <div
          className="h-1.5 rounded-full overflow-hidden"
          style={{ background: 'var(--ei-border-primary)' }}
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
      aria-label={`${factorName}: ${score}%`}
    >
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <span className="text-sm font-medium text-slate-900 dark:text-white truncate">{factorName}</span>
        <span className="flex-shrink-0 text-lg font-bold tabular-nums text-slate-900 dark:text-white">{score}%</span>
      </div>
      {subtitle && (
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-2 line-clamp-2">{subtitle}</p>
      )}
      <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden" role="progressbar" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100}>
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColorClass}`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
    </div>
  )
}
