import React, { useState } from 'react'
import { FiChevronDown } from 'react-icons/fi'

/**
 * @param {'default' | 'enterprise'} variant
 */
export default function CollapsibleSection({ label = 'Detailed Analysis', children, variant = 'default', defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const enterprise = variant === 'enterprise'

  if (enterprise) {
    return (
      <div className="border border-white/[0.08] rounded-[14px] overflow-hidden bg-white/[0.025]">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="w-full flex items-center justify-between gap-2 px-4 py-3 text-left hover:bg-white/[0.04] transition-all duration-[180ms] focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#3AA9FF]/35"
          aria-expanded={open}
          aria-controls="collapsible-detailed-analysis"
          id="collapsible-detailed-analysis-toggle"
        >
          <span className="flex items-center gap-2 text-sm font-medium text-[#DCE3EA]">
            <FiChevronDown
              className={`w-4 h-4 text-[#8796A5] transition-transform duration-[180ms] ${open ? 'rotate-0' : '-rotate-90'}`}
              aria-hidden
            />
            {label}
          </span>
          <span className="text-[#738394] text-xs">
            {open ? 'Collapse' : 'Expand'}
          </span>
        </button>
        {open && (
          <div
            id="collapsible-detailed-analysis"
            role="region"
            aria-labelledby="collapsible-detailed-analysis-toggle"
            className="px-4 py-3 border-t border-white/[0.08] text-[#A0ABB6]"
          >
            {children}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden bg-white dark:bg-slate-800/50">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 px-4 py-3 text-left bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-accent-blue/30 rounded-t-xl"
        aria-expanded={open}
        aria-controls="collapsible-detailed-analysis"
        id="collapsible-detailed-analysis-toggle"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
          <span className="w-4 text-center" aria-hidden>{open ? '▼' : '▶'}</span>
          {label}
        </span>
        <span className="text-slate-500 dark:text-slate-400 text-xs">
          {open ? 'Collapse' : 'Expand'}
        </span>
      </button>
      {open && (
        <div
          id="collapsible-detailed-analysis"
          role="region"
          aria-labelledby="collapsible-detailed-analysis-toggle"
          className="px-4 py-3 border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/30"
        >
          {children}
        </div>
      )}
    </div>
  )
}
