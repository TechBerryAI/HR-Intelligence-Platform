import React from 'react'

/**
 * @param {'default' | 'enterprise'} theme
 */
export default function ChipGroup({ title, items, variant = 'strength', id, theme = 'default' }) {
  if (!items || items.length === 0) return null

  const isStrength = variant === 'strength'
  const enterprise = theme === 'enterprise'

  const chipStyle = enterprise
    ? isStrength
      ? {
          background: 'var(--ei-tone-success-bg)',
          borderColor: 'var(--ei-tone-success-border)',
          color: 'var(--ei-tone-success)',
        }
      : {
          background: 'var(--ei-tone-danger-bg)',
          borderColor: 'var(--ei-tone-danger-border)',
          color: 'var(--ei-tone-danger)',
        }
    : undefined

  const chipClass = enterprise
    ? 'border'
    : isStrength
      ? 'bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/40'
      : 'bg-red-50 dark:bg-red-500/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-500/40'

  return (
    <div>
      <h3
        className={`text-xs font-semibold uppercase tracking-[0.08em] mb-2 ${
          enterprise ? 'text-[var(--ei-text-muted)]' : 'text-slate-500 dark:text-slate-400'
        }`}
        id={id}
      >
        {title}
      </h3>
      <ul className="flex flex-wrap gap-2 list-none p-0 m-0" aria-labelledby={id}>
        {items.map((item, i) => (
          <li key={i}>
            <span className={`inline-block px-3 py-1.5 rounded-full text-sm font-medium ${chipClass}`} style={chipStyle}>
              {item}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
