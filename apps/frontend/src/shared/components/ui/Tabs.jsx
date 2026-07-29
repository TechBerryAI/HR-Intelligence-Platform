import React from 'react'

export function Tabs({ tabs, activeTab, onChange, className = '' }) {
  return (
    <div className={`border-b border-slate-200 dark:border-slate-700 ${className}`}>
      <nav className="flex gap-1 -mb-px" aria-label="Tabs">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onChange(tab.id)}
              className={`
                px-4 py-3 text-sm font-medium rounded-t-xl transition-colors
                ${isActive
                  ? 'text-accent-blue border-b-2 border-accent-blue bg-slate-50 dark:bg-slate-800/50 text-accent-blue'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 border-b-2 border-transparent hover:border-slate-300 dark:hover:border-slate-600'
                }
              `}
            >
              {tab.label}
            </button>
          )
        })}
      </nav>
    </div>
  )
}

export function TabPanel({ children, active, id, ...props }) {
  if (!active) return null
  return (
    <div role="tabpanel" id={id} aria-labelledby={`tab-${id}`} {...props}>
      {children}
    </div>
  )
}
