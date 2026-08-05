import React from 'react'

/**
 * @param {'default' | 'enterprise'} theme
 */
export default function ChipGroup({ title, items, variant = 'strength', id, theme = 'default' }) {
  if (!items || items.length === 0) return null

  const isStrength = variant === 'strength'
  const enterprise = theme === 'enterprise'

  const chipClass = enterprise
    ? isStrength
      ? 'bg-[rgba(55,214,160,0.08)] border border-[rgba(55,214,160,0.18)] text-[#67DFB4]'
      : 'bg-[rgba(255,93,115,0.07)] border border-[rgba(255,93,115,0.18)] text-[#FF788B]'
    : isStrength
      ? 'bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/40'
      : 'bg-red-50 dark:bg-red-500/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-500/40'

  return (
    <div>
      <h3
        className={`text-xs font-semibold uppercase tracking-[0.08em] mb-2 ${
          enterprise ? 'text-[#83909C]' : 'text-slate-500 dark:text-slate-400'
        }`}
        id={id}
      >
        {title}
      </h3>
      <ul className="flex flex-wrap gap-2 list-none p-0 m-0" aria-labelledby={id}>
        {items.map((item, i) => (
          <li key={i}>
            <span className={`inline-block px-3 py-1.5 rounded-full text-sm font-medium ${chipClass}`}>
              {item}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
