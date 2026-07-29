import React from 'react'

export default function ChipGroup({ title, items, variant = 'strength', id }) {
  if (!items || items.length === 0) return null

  const isStrength = variant === 'strength'
  const chipClass = isStrength
    ? 'bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/40'
    : 'bg-red-50 dark:bg-red-500/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-500/40'

  return (
    <div>
      <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2" id={id}>
        {title}
      </h3>
      <ul className="flex flex-wrap gap-2 list-none p-0 m-0" aria-labelledby={id}>
        {items.map((item, i) => (
          <li key={i}>
            <span className={`inline-block px-3 py-1.5 rounded-xl text-sm font-medium ${chipClass}`}>
              {item}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
