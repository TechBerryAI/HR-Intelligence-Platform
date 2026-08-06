import React from 'react'

function durationTone(ms) {
  if (ms == null || Number.isNaN(ms)) return 'muted'
  if (ms < 500) return 'green'
  if (ms <= 2000) return 'yellow'
  return 'red'
}

/** Duration chip: green &lt;500ms, yellow 500–2000, red &gt;2000. */
export function DurationBadge({ ms, className = '' }) {
  const tone = durationTone(ms)
  const colors = {
    green: 'text-emerald-400 bg-emerald-500/10 ring-emerald-500/25',
    yellow: 'text-amber-300 bg-amber-500/10 ring-amber-500/25',
    red: 'text-rose-300 bg-rose-500/10 ring-rose-500/25',
    muted: 'text-[var(--ei-text-muted)] bg-[var(--ei-surface-hover)] ring-[var(--ei-border-primary)]',
  }
  const label = ms == null || Number.isNaN(Number(ms)) ? '—' : `${Math.round(Number(ms))} ms`
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold ring-1 tabular-nums ${colors[tone]} ${className}`}
    >
      {label}
    </span>
  )
}
