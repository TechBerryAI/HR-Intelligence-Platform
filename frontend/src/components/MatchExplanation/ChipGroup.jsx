import React from 'react'

/**
 * Renders a list of items as tag chips. variant: 'strength' (green) | 'gap' (red).
 */
export default function ChipGroup({ title, items, variant = 'strength', id }) {
  if (!items || items.length === 0) return null

  const isStrength = variant === 'strength'
  const chipClass = isStrength
    ? 'bg-emerald-900/30 text-emerald-300 ring-1 ring-emerald-700/50'
    : 'bg-red-900/30 text-red-300 ring-1 ring-red-700/50'

  return (
    <div>
      <h3
        className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2"
        id={id}
      >
        {title}
      </h3>
      <ul
        className="flex flex-wrap gap-2 list-none p-0 m-0"
        aria-labelledby={id}
      >
        {items.map((item, i) => (
          <li key={i}>
            <span
              className={`inline-block px-3 py-1.5 rounded-lg text-sm font-medium ${chipClass}`}
            >
              {item}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
