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

export default function IntegrationsDashboard() {
  const location = useLocation()
  const settingsPath = location.pathname.startsWith('/head-hr') ? '/head-hr/settings' : '/settings'
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
      /* toast via reload errors */
    } finally {
      setBusy('')
    }
  }

  const providers = data?.providers || []
  const errors = data?.recentErrors || []
  const logs = data?.recentLogs || []

  return (
    <PageContainer className="max-w-5xl">
      <AnimatedContainer animation="slideDown">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ei-text-muted)]">
              Integrations
            </p>
            <h2 className="mt-1 text-3xl font-bold text-[var(--ei-text-primary)] tracking-tight">
              External Publishing
            </h2>
            <p className="mt-1.5 text-sm text-[var(--ei-text-secondary)]">
              Connection health, publish queue, and recent sync activity for your company.
            </p>
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

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {providers.map((p) => (
            <div key={p.provider} className="org-glass-card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-[var(--ei-text-primary)]">{p.name}</h3>
                <span className="text-xs text-[var(--ei-text-muted)] capitalize">{p.status}</span>
              </div>
              <dl className="space-y-1 text-sm text-[var(--ei-text-secondary)] mb-4">
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
            Pending tasks in worker: <span className="tabular-nums font-medium text-[var(--ei-text-primary)]">{data?.pendingQueue ?? 0}</span>
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="org-glass-panel p-5">
            <h3 className="font-semibold text-[var(--ei-text-primary)] mb-3">Recent errors</h3>
            {errors.length === 0 ? (
              <p className="text-sm text-[var(--ei-text-muted)]">No recent errors.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {errors.map((e) => (
                  <li key={e.id} className="border-b border-white/[0.06] pb-2">
                    <div className="flex justify-between gap-2">
                      <span className="text-[var(--ei-text-primary)] capitalize">{e.provider}</span>
                      <span className="text-[var(--ei-text-muted)] text-xs">{e.createdAt}</span>
                    </div>
                    <p className="text-[#FF7B8E] mt-0.5">{e.errorMessage || e.status}</p>
                    {e.id && e.status === 'failed' && (
                      <button
                        type="button"
                        className="text-xs text-[#00A6FF] mt-1"
                        onClick={async () => {
                          try {
                            // Retry by external job requires external job id; logs may not have it
                            if (e.externalJobId && /^\d+$/.test(String(e.externalJobId))) {
                              await retryExternalJob(Number(e.externalJobId))
                              await load()
                            }
                          } catch (_) {}
                        }}
                      >
                        Retry if available
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="org-glass-panel p-5">
            <h3 className="font-semibold text-[var(--ei-text-primary)] mb-3">Recent activity</h3>
            {logs.length === 0 ? (
              <p className="text-sm text-[var(--ei-text-muted)]">No sync logs yet.</p>
            ) : (
              <ul className="space-y-2 text-sm max-h-80 overflow-auto">
                {logs.map((l) => (
                  <li key={l.id} className="border-b border-white/[0.06] pb-2">
                    <div className="flex justify-between gap-2">
                      <span className="text-[var(--ei-text-primary)]">
                        {l.provider} · {l.operation}
                      </span>
                      <span
                        className={`text-xs ${
                          l.status === 'success' ? 'text-[#36D6A0]' : 'text-[#FF7B8E]'
                        }`}
                      >
                        {l.status}
                      </span>
                    </div>
                    <p className="text-[var(--ei-text-muted)] text-xs mt-0.5">
                      {l.jobId || '—'} · {l.executionTimeMs != null ? `${l.executionTimeMs}ms` : ''} · {l.createdAt}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </AnimatedContainer>
    </PageContainer>
  )
}
