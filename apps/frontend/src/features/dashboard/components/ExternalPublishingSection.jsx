import React, { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FiRefreshCw, FiExternalLink } from 'react-icons/fi'
import { fetchIntegrationStatus } from '@/features/settings/services/integrationsApi.js'
import ProviderBrandIcon from '@/features/integrations/components/ProviderBrandIcon.jsx'

/**
 * Compact External Publishing status strip for recruiter / org dashboards.
 */
export default function ExternalPublishingSection({ className = '', detailsTo = '/integrations' }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetchIntegrationStatus()
      setData(res)
    } catch (e) {
      setError(e.message || 'Unable to load publishing status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const providers = data?.providers || []

  return (
    <section className={`org-glass-panel p-5 sm:p-6 mb-8 ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h3 className="text-lg font-semibold text-[var(--ei-text-primary)]">External Publishing</h3>
          <p className="text-sm text-[var(--ei-text-secondary)] mt-0.5">
            Distribution status across connected job boards for your company.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            className="org-btn-ghost inline-flex items-center gap-2 text-sm"
            disabled={loading}
          >
            <FiRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <Link
            to={detailsTo}
            className="org-btn-ghost inline-flex items-center gap-2 text-sm"
          >
            <FiExternalLink className="w-4 h-4" />
            Details
          </Link>
        </div>
      </div>

      {error && <p className="text-sm text-[#FF7B8E] mb-3">{error}</p>}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {providers.map((p) => (
          <div
            key={p.provider}
            className="rounded-xl bg-[var(--ei-surface-hover)] ring-1 ring-[var(--ei-border-primary)] p-4"
          >
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2 min-w-0">
                <ProviderBrandIcon provider={p.provider} className="w-5 h-5 shrink-0" />
                <p className="font-medium text-[var(--ei-text-primary)] truncate">{p.name}</p>
              </div>
              <span
                className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                  p.enabled
                    ? 'bg-[rgba(54,214,160,0.15)] text-[#36D6A0]'
                    : 'bg-[var(--ei-surface)] text-[var(--ei-text-muted)]'
                }`}
              >
                {p.enabled ? 'Enabled' : 'Off'}
              </span>
            </div>
            <dl className="grid grid-cols-3 gap-2 text-center">
              <div>
                <dt className="text-[10px] uppercase tracking-wide text-[var(--ei-text-muted)]">Published</dt>
                <dd className="text-lg font-semibold tabular-nums text-[var(--ei-text-primary)]">{p.published ?? 0}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wide text-[var(--ei-text-muted)]">Pending</dt>
                <dd className="text-lg font-semibold tabular-nums text-[var(--ei-text-primary)]">{p.pending ?? 0}</dd>
              </div>
              <div>
                <dt className="text-[10px] uppercase tracking-wide text-[var(--ei-text-muted)]">Failed</dt>
                <dd className="text-lg font-semibold tabular-nums text-[#FF7B8E]">{p.failed ?? 0}</dd>
              </div>
            </dl>
          </div>
        ))}
        {!loading && providers.length === 0 && !error && (
          <p className="text-sm text-[var(--ei-text-muted)] col-span-full">
            No provider status yet. Configure integrations under Settings.
          </p>
        )}
      </div>
      {typeof data?.pendingQueue === 'number' && (
        <p className="mt-3 text-xs text-[var(--ei-text-muted)]">
          Queue depth: {data.pendingQueue}
        </p>
      )}
    </section>
  )
}
