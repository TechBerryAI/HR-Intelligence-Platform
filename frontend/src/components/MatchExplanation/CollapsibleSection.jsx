import React, { useState } from 'react'

/**
 * Collapsed-by-default section with label "▶ Detailed Analysis".
 * Content: overall score, primary reason (1–2 lines), no repetition of chips.
 */
export default function CollapsibleSection({ label = 'Detailed Analysis', children }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="border border-zinc-700/50 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 px-4 py-3 text-left bg-zinc-800/40 hover:bg-zinc-800/60 transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white/20"
        aria-expanded={open}
        aria-controls="collapsible-detailed-analysis"
        id="collapsible-detailed-analysis-toggle"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-zinc-300">
          <span className="w-4 text-center" aria-hidden>{open ? '▼' : '▶'}</span>
          {label}
        </span>
        <span className="text-zinc-500 text-xs">
          {open ? 'Collapse' : 'Expand'}
        </span>
      </button>
      {open && (
        <div
          id="collapsible-detailed-analysis"
          role="region"
          aria-labelledby="collapsible-detailed-analysis-toggle"
          className="px-4 py-3 bg-zinc-800/30 border-t border-zinc-700/50"
        >
          {children}
        </div>
      )}
    </div>
  )
}
