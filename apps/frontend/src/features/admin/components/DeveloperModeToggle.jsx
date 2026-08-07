import React from 'react'
import { FiActivity } from 'react-icons/fi'
import { useDeveloperMode } from '@/features/admin/hooks/useDeveloperMode.js'

/**
 * Admin (HEAD_HR) only — toggles Developer Mode UI visibility.
 * Backend still requires DEVELOPER_MODE=true for timing collection / APIs.
 */
export default function DeveloperModeToggle({ enterprise = false }) {
  const {
    isAdmin,
    preference,
    backendAvailable,
    loading,
    setToggle,
  } = useDeveloperMode()

  if (!isAdmin) return null

  const cardClass = enterprise
    ? 'org-card overflow-hidden'
    : 'rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 shadow-premium overflow-hidden'

  const headerClass = enterprise
    ? 'px-6 py-4 border-b border-white/[0.08] bg-[var(--ei-surface-hover)] flex items-center gap-3'
    : 'px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex items-center gap-3'

  const titleClass = enterprise
    ? 'text-lg font-semibold text-[var(--ei-text-primary)]'
    : 'text-lg font-semibold text-slate-900 dark:text-white'

  const bodyText = enterprise
    ? 'text-sm text-[var(--ei-text-secondary)] leading-relaxed'
    : 'text-sm text-slate-500 dark:text-slate-400'

  const labelClass = enterprise
    ? 'text-sm font-medium text-[var(--ei-text-primary)]'
    : 'text-sm font-medium text-slate-900 dark:text-white'

  const mutedClass = enterprise
    ? 'text-xs text-[var(--ei-text-muted)]'
    : 'text-xs text-slate-500 dark:text-slate-400'

  const disabled = loading || !backendAvailable

  return (
    <section className={cardClass}>
      <div className={headerClass}>
        <FiActivity className={`w-5 h-5 ${enterprise ? 'text-[#00A6FF]' : 'text-primary'}`} />
        <h2 className={titleClass}>Developer Mode</h2>
      </div>
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className={labelClass}>Show Performance Dashboard</p>
            <p className={`${bodyText} mt-1`}>
              When on, a <strong className="font-semibold">Developer Mode</strong> item appears in the
              sidebar with the performance timing dashboard. Admin only.
            </p>
            {!loading && !backendAvailable ? (
              <p className={`${mutedClass} mt-3`}>
                Backend flag is off. Set <code className="font-mono">DEVELOPER_MODE=true</code> in{' '}
                <code className="font-mono">apps/backend/.env</code> and restart the API, then use this
                toggle.
              </p>
            ) : (
              <p className={`${mutedClass} mt-3`}>
                Timing collection is active on the server when Developer Mode is enabled in env.
              </p>
            )}
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={preference}
            aria-label="Developer Mode"
            disabled={disabled}
            onClick={() => setToggle(!preference)}
            className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/50 disabled:opacity-40 disabled:cursor-not-allowed ${
              preference && backendAvailable
                ? 'bg-[var(--ei-btn-primary-from)]'
                : enterprise
                  ? 'bg-[var(--ei-surface-hover)] ring-1 ring-[var(--ei-border-primary)]'
                  : 'bg-slate-300 dark:bg-slate-600'
            }`}
          >
            <span
              className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${
                preference && backendAvailable ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>
    </section>
  )
}
