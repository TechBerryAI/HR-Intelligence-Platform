import React, { useCallback, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import AnimatedContainer from '@/shared/components/AnimatedContainer.jsx'
import { PageContainer } from '@/shared/components/PageContainer.jsx'
import {
  fetchIntegrationDashboard,
  testProviderConnection,
  retryExternalJob,
} from '@/features/settings/services/integrationsApi.js'
import { FiRefreshCw, FiSettings, FiZap } from 'react-icons/fi'
import ProviderBrandIcon from '@/features/integrations/components/ProviderBrandIcon.jsx'

const IST = 'Asia/Kolkata'

/** Format timestamps for display in IST (e.g. "5 Aug 2026, 5:50 pm"). */
function formatIst(ts) {
  if (!ts) return ''
  const d = ts instanceof Date ? ts : new Date(ts)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('en-IN', {
    timeZone: IST,
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

function StatusPill({ status }) {
  const s = String(status || '').toLowerCase()
  const ok = s === 'success' || s === 'connected' || s === 'published'
  const bad = s === 'failed' || s === 'error' || s === 'dead'
  const muted = s === 'disconnected' || s === 'pending'
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium capitalize ${
        ok
          ? 'bg-[rgba(54,214,160,0.12)] text-[#36D6A0]'
          : bad
            ? 'bg-[rgba(255,102,133,0.12)] text-[#FF7B8E]'
            : muted
              ? 'bg-[var(--ei-surface-hover)] text-[var(--ei-text-muted)]'
              : 'bg-[var(--ei-surface-hover)] text-[var(--ei-text-secondary)]'
      }`}
    >
      {status || '—'}
    </span>
  )
}

function operationLabel(provider, operation) {
  const op = String(operation || '').replace(/_/g, ' ')
  const name = String(provider || '').replace(/_/g, ' ')
  if (!name) return op || 'Activity'
  if (!op) return name
  return `${name} · ${op}`
}

/**
 * @param {{ embedded?: boolean }} props
 * When embedded (Head HR layout), skip PageContainer to avoid nested overflow / blank shell.
 */
export default function IntegrationsDashboard({ embedded = false }) {
  const location = useLocation()
  const isHeadHr = location.pathname.startsWith('/head-hr') || embedded
  const settingsPath = isHeadHr
    ? '/head-hr/settings?tab=integrations'
    : '/settings?tab=integrations'
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetchIntegrationDashboard()
      setData(res)
    } catch (e) {
      setError(e.message || 'Failed to load integrations dashboard')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const onTest = async (provider) => {
    setBusy(provider)
    try {
      await testProviderConnection(provider)
      await load()
    } catch (_) {
      /* surface via reload */
    } finally {
      setBusy('')
    }
  }

  const providers = data?.providers || []
  const errors = data?.recentErrors || []
  const logs = data?.recentLogs || []

  const body = (
    <AnimatedContainer animation="slideDown">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          {embedded ? (
            <>
              <h1 className="org-page-title">External Publishing</h1>
              <p className="org-page-subtitle">
                Connection health, publish queue, and recent sync activity for your company.
              </p>
            </>
          ) : (
            <>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ei-text-muted)]">
                Integrations
              </p>
              <h2 className="mt-1 text-3xl font-bold text-[var(--ei-text-primary)] tracking-tight">
                External Publishing
              </h2>
              <p className="mt-1.5 text-sm text-[var(--ei-text-secondary)]">
                Connection health, publish queue, and recent sync activity for your company.
              </p>
            </>
          )}
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={load} className="org-btn-ghost inline-flex items-center gap-2">
            <FiRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <Link to={settingsPath} className="org-btn-primary inline-flex items-center gap-2">
            <FiSettings className="w-4 h-4" />
            Settings
          </Link>
        </div>
      </div>

      {error && <p className="mb-4 text-sm text-[#FF7B8E]">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-8">
        {providers.map((p) => (
          <div key={p.provider} className="org-glass-card p-5">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="h-10 w-10 rounded-xl bg-[var(--ei-surface-hover)] ring-1 ring-[var(--ei-border-primary)] flex items-center justify-center shrink-0 overflow-hidden">
                  <ProviderBrandIcon
                    provider={p.provider}
                    className="w-5 h-5"
                    logoUrl={p.logoUrl}
                    title={p.name}
                  />
                </div>
                <h3 className="font-semibold text-[var(--ei-text-primary)] truncate">{p.name}</h3>
              </div>
              <StatusPill status={p.status} />
            </div>
            <dl className="space-y-1.5 text-sm text-[var(--ei-text-secondary)] mb-4">
              <div className="flex justify-between">
                <dt>Published</dt>
                <dd className="tabular-nums text-[var(--ei-text-primary)]">{p.published}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Pending</dt>
                <dd className="tabular-nums text-[var(--ei-text-primary)]">{p.pending}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Failed</dt>
                <dd className="tabular-nums text-[#FF7B8E]">{p.failed}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Auto publish</dt>
                <dd>{p.autoPublish ? 'On' : 'Off'}</dd>
              </div>
            </dl>
            <button
              type="button"
              disabled={busy === p.provider}
              onClick={() => onTest(p.provider)}
              className="org-btn-ghost w-full inline-flex items-center justify-center gap-2 text-sm"
            >
              <FiZap className="w-4 h-4" />
              {busy === p.provider ? 'Testing…' : 'Test Connection'}
            </button>
          </div>
        ))}
      </div>

      <div className="org-glass-panel p-5 mb-6">
        <h3 className="font-semibold text-[var(--ei-text-primary)] mb-1">Queue</h3>
        <p className="text-sm text-[var(--ei-text-secondary)]">
          Pending tasks in worker:{' '}
          <span className="tabular-nums font-medium text-[var(--ei-text-primary)]">
            {data?.pendingQueue ?? 0}
          </span>
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="org-glass-panel p-5">
          <h3 className="font-semibold text-[var(--ei-text-primary)] mb-3">Recent errors</h3>
          {errors.length === 0 ? (
            <p className="text-sm text-[var(--ei-text-muted)]">No recent errors.</p>
          ) : (
            <ul className="divide-y divide-[var(--ei-border-primary)]">
              {errors.map((e) => {
                const canRetry =
                  e.externalJobId != null && /^\d+$/.test(String(e.externalJobId))
                const when = formatIst(e.createdAt)
                return (
                  <li key={e.id} className="py-3 first:pt-0 last:pb-0">
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-medium text-[var(--ei-text-primary)] capitalize">
                        {e.provider}
                      </span>
                      {when && (
                        <time
                          dateTime={e.createdAt}
                          className="shrink-0 text-xs text-[var(--ei-text-muted)] whitespace-nowrap"
                          title={`${when} IST`}
                        >
                          {when}
                        </time>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-[#FF7B8E] leading-snug">
                      {e.errorMessage || e.status || 'Unknown error'}
                    </p>
                    {canRetry && (
                      <button
                        type="button"
                        className="mt-1.5 text-xs text-[#00A6FF] hover:underline"
                        onClick={async () => {
                          try {
                            await retryExternalJob(Number(e.externalJobId))
                            await load()
                          } catch (_) {}
                        }}
                      >
                        Retry
                      </button>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        <div className="org-glass-panel p-5">
          <h3 className="font-semibold text-[var(--ei-text-primary)] mb-3">Recent activity</h3>
          {logs.length === 0 ? (
            <p className="text-sm text-[var(--ei-text-muted)]">No sync logs yet.</p>
          ) : (
            <ul className="divide-y divide-[var(--ei-border-primary)] max-h-80 overflow-auto">
              {logs.map((l) => {
                const when = formatIst(l.createdAt)
                const meta = []
                if (l.jobId) meta.push(`Job ${l.jobId}`)
                if (l.executionTimeMs != null && l.executionTimeMs > 0) {
                  meta.push(`${l.executionTimeMs} ms`)
                }
                if (when) meta.push(when)
                return (
                  <li key={l.id} className="py-3 first:pt-0 last:pb-0">
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-medium text-[var(--ei-text-primary)] capitalize">
                        {operationLabel(l.provider, l.operation)}
                      </span>
                      <StatusPill status={l.status} />
                    </div>
                    {meta.length > 0 && (
                      <p className="mt-1 text-xs text-[var(--ei-text-muted)]">{meta.join(' · ')}</p>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </AnimatedContainer>
  )

  if (embedded) {
    return <div className="w-full">{body}</div>
  }

  return <PageContainer className="max-w-5xl">{body}</PageContainer>
}
