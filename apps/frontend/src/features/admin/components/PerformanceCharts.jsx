import React from 'react'

function durationTone(ms) {
  if (ms == null || Number.isNaN(ms)) return 'muted'
  if (ms < 500) return 'green'
  if (ms <= 2000) return 'yellow'
  return 'red'
}

/** Format wall time: ms under 1s, sec at 1s+. */
export function formatDuration(ms) {
  if (ms == null || Number.isNaN(Number(ms))) return '—'
  const n = Number(ms)
  if (n >= 1000) {
    const sec = n / 1000
    const rounded = sec >= 10 ? sec.toFixed(1) : sec.toFixed(2)
    return `${rounded} sec`
  }
  if (n < 1) return '<1 ms'
}

/** Duration chip: green &lt;500ms, yellow 500–2000, red &gt;2000. Shows ms or sec. */
export function DurationBadge({ ms, className = '' }) {
  const tone = durationTone(ms)
  const colors = {
    green: 'text-emerald-400 bg-emerald-500/10 ring-emerald-500/25',
    yellow: 'text-amber-300 bg-amber-500/10 ring-amber-500/25',
    red: 'text-rose-300 bg-rose-500/10 ring-rose-500/25',
    muted: 'text-[var(--ei-text-muted)] bg-[var(--ei-surface-hover)] ring-[var(--ei-border-primary)]',
  }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold ring-1 tabular-nums ${colors[tone]} ${className}`}
    >
      {formatDuration(ms)}
    </span>
  )
}
