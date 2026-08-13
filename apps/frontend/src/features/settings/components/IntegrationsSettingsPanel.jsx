import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  FiCheck,
  FiAlertCircle,
  FiLink,
  FiRefreshCw,
  FiSave,
  FiPlus,
  FiX,
  FiTrash2,
} from 'react-icons/fi'
import PremiumInput from '@/shared/components/PremiumInput.jsx'
import PremiumButton from '@/shared/components/PremiumButton.jsx'
import { isHeadHr } from '@/core/permissions/rbac.js'
import { useApp } from '@/core/context/AppContext.jsx'
import ProviderBrandIcon from '@/features/integrations/components/ProviderBrandIcon.jsx'
import GoogleCalendarConnectCard from '@/features/interview/components/GoogleCalendarConnectCard.jsx'
import {
  fetchIntegrationProviders,
  saveProviderConfig,
  createProviderConfig,
  testProviderConnection,
  connectProvider,
  deleteProviderConfig,
} from '@/features/settings/services/integrationsApi.js'

function Toggle({ checked, onChange, disabled, enterprise, label }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={`relative h-6 w-11 rounded-full transition-colors ${
          checked
            ? enterprise
              ? 'bg-[var(--ei-btn-primary-from)]'
              : 'bg-primary'
            : enterprise
              ? 'bg-[var(--ei-surface-hover)] ring-1 ring-[var(--ei-border-primary)]'
              : 'bg-slate-300 dark:bg-slate-600'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
            checked ? 'translate-x-5' : ''
          }`}
        />
      </button>
      <span
        className={
          enterprise
            ? 'text-sm text-[var(--ei-text-label)]'
            : 'text-sm text-slate-700 dark:text-slate-300'
        }
      >
        {label}
      </span>
    </label>
  )
}

function hasLocalCredentials(clientId, clientSecret, accessToken, cfg) {
  const idOk = (clientId || '').trim().length > 0
  const secretOk = (clientSecret || '').trim().length > 0 || !!cfg.clientSecretConfigured
  const tokenOk = (accessToken || '').trim().length > 0 || !!cfg.accessTokenConfigured
  return (idOk && secretOk) || tokenOk
}

function ProviderCard({ item, enterprise, canEdit, onSaved, showHttpFields }) {
  const cfg = item.config || {}
  const settings = cfg.settings || {}
  const endpoints = settings.endpoints || {}
  const [enabled, setEnabled] = useState(!!cfg.enabled)
  const [autoPublish, setAutoPublish] = useState(!!cfg.autoPublish)
  const [autoSync, setAutoSync] = useState(!!cfg.autoSync)
  const [clientId, setClientId] = useState(cfg.clientId || '')
  const [clientSecret, setClientSecret] = useState('')
  const [accessToken, setAccessToken] = useState('')
  const [refreshToken, setRefreshToken] = useState('')
  const [companyApplyUrl, setCompanyApplyUrl] = useState(settings.companyApplyUrl || '')
  const [logoUrl, setLogoUrl] = useState(settings.logoUrl || item.logoUrl || '')
  const [epTest, setEpTest] = useState(endpoints.test || 'GET /health')
  const [epPublish, setEpPublish] = useState(endpoints.publish || 'POST /jobs')
  const [epUpdate, setEpUpdate] = useState(endpoints.update || 'PUT /jobs/{externalJobId}')
  const [epClose, setEpClose] = useState(endpoints.close || 'POST /jobs/{externalJobId}/close')
  const [epApps, setEpApps] = useState(endpoints.applications || 'GET /jobs/{externalJobId}/applications')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState({ type: '', text: '' })

  useEffect(() => {
    setEnabled(!!cfg.enabled)
    setAutoPublish(!!cfg.autoPublish)
    setAutoSync(!!cfg.autoSync)
    setClientId(cfg.clientId || '')
    setClientSecret('')
    setAccessToken('')
    setRefreshToken('')
    setBaseUrl(settings.baseUrl || '')
    setCompanyApplyUrl(settings.companyApplyUrl || '')
    setLogoUrl(settings.logoUrl || item.logoUrl || '')
    setEpTest(endpoints.test || 'GET /health')
    setEpPublish(endpoints.publish || 'POST /jobs')
    setEpUpdate(endpoints.update || 'PUT /jobs/{externalJobId}')
    setEpClose(endpoints.close || 'POST /jobs/{externalJobId}/close')
    setEpApps(endpoints.applications || 'GET /jobs/{externalJobId}/applications')
  }, [item.id, item.logoUrl, cfg.enabled, cfg.autoPublish, cfg.autoSync, cfg.clientId, settings.baseUrl, settings.logoUrl])

  const accessRequired = item.accessRequired === true
  const statusOk = !accessRequired && cfg.status === 'connected'
  const statusLabel = accessRequired
    ? 'Provider access required'
    : statusOk
      ? 'Connected'
      : 'Not connected'

  const buildBody = () => {
    const body = {
      enabled,
      autoPublish,
      autoSync,
      clientId,
      status: accessRequired ? 'provider_access_required' : enabled ? 'connected' : 'disconnected',
    }
    if (clientSecret.trim()) body.clientSecret = clientSecret.trim()
    if (accessToken.trim()) body.accessToken = accessToken.trim()
    if (refreshToken.trim()) body.refreshToken = refreshToken.trim()
    if (showHttpFields) {
      body.settings = {
        adapter: 'http',
        displayName: item.name,
        baseUrl: baseUrl.trim(),
        authHeader: 'Bearer',
        endpoints: {
          test: epTest.trim(),
          publish: epPublish.trim(),
          update: epUpdate.trim(),
          close: epClose.trim(),
          applications: epApps.trim(),
        },
      }
      if (logoUrl.trim()) body.settings.logoUrl = logoUrl.trim()
      else body.settings.logoUrl = ''
      body.baseUrl = baseUrl.trim()
      body.logoUrl = logoUrl.trim()
    }
    if (item.id === 'linkedin') {
      body.settings = {
        ...(cfg.settings || {}),
        ...(body.settings || {}),
        companyApplyUrl: companyApplyUrl.trim(),
      }
    }
    return body
  }

  const handleSave = async () => {
    setBusy(true)
    setMsg({ type: '', text: '' })
    if (enabled && !hasLocalCredentials(clientId, clientSecret, accessToken, cfg)) {
      setMsg({
        type: 'error',
        text: 'Enter Client ID and Client Secret (or Access Token) before connecting.',
      })
      setBusy(false)
      return
    }
    if (showHttpFields && !baseUrl.trim()) {
      setMsg({ type: 'error', text: 'API Base URL is required.' })
      setBusy(false)
      return
    }
    try {
      const body = buildBody()
      if (!enabled) body.status = 'disconnected'
      await saveProviderConfig(item.id, body)
      if (enabled && !accessRequired) await connectProvider(item.id, body).catch(() => null)
      setMsg({ type: 'success', text: 'Configuration saved.' })
      setClientSecret('')
      setAccessToken('')
      setRefreshToken('')
      onSaved?.()
    } catch (e) {
      setMsg({ type: 'error', text: e.message || 'Save failed' })
    } finally {
      setBusy(false)
    }
  }

  const handleTest = async () => {
    setBusy(true)
    setMsg({ type: '', text: '' })
    try {
      await saveProviderConfig(item.id, buildBody())
      const res = await testProviderConnection(item.id)
      const ok = res?.result?.success
      setMsg({
        type: ok ? 'success' : 'error',
        text: res?.result?.message || res?.result?.error || (ok ? 'Connection verified' : 'Connection failed'),
      })
      if (ok) onSaved?.()
    } catch (e) {
      setMsg({ type: 'error', text: e.message || 'Test failed' })
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    if (!canEdit || item.builtin) return
    if (!window.confirm(`Remove ${item.name} integration for this company?`)) return
    setBusy(true)
    try {
      await deleteProviderConfig(item.id)
      onSaved?.()
    } catch (e) {
      setMsg({ type: 'error', text: e.message || 'Delete failed' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className={
        enterprise
          ? 'org-glass-panel p-5 space-y-4'
          : 'rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-5 space-y-4'
      }
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={
              enterprise
                ? 'h-11 w-11 rounded-xl bg-[var(--ei-surface-hover)] flex items-center justify-center ring-1 ring-[var(--ei-border-primary)] overflow-hidden'
                : 'h-11 w-11 rounded-xl bg-slate-100 dark:bg-slate-700 flex items-center justify-center overflow-hidden'
            }
          >
            <ProviderBrandIcon
              provider={item.id}
              className="w-6 h-6"
              logoUrl={settings.logoUrl || item.logoUrl}
              title={item.name}
            />
          </div>
          <div>
            <h3
              className={
                enterprise
                  ? 'font-semibold text-[var(--ei-text-primary)]'
                  : 'font-semibold text-slate-900 dark:text-white'
              }
            >
              {item.name}
              {!item.builtin && (
                <span className="ml-2 text-xs font-normal text-[var(--ei-text-muted)]">Custom</span>
              )}
            </h3>
            <p
              className={`text-xs mt-0.5 flex items-center gap-1 ${
                statusOk
                  ? enterprise
                    ? 'text-[#36D6A0]'
                    : 'text-green-600'
                  : enterprise
                    ? 'text-[var(--ei-text-muted)]'
                    : 'text-slate-500'
              }`}
            >
              <FiLink className="w-3 h-3" />
              {statusLabel}
            </p>
          </div>
        </div>
        {canEdit && !item.builtin && (
          <button
            type="button"
            onClick={handleDelete}
            className="text-[#FF7B8E] hover:opacity-80 p-1"
            title="Remove platform"
          >
            <FiTrash2 className="w-4 h-4" />
          </button>
        )}
      </div>

      {accessRequired && (
        <p
          className={
            enterprise
              ? 'text-xs text-[var(--ei-text-muted)]'
              : 'text-xs text-slate-500 dark:text-slate-400'
          }
        >
          {item.id === 'linkedin'
            ? 'LinkedIn Job Posting API requires Talent Solutions partner approval. Saving credentials does not publish jobs until LinkedIn grants API access.'
            : 'Naukri has no public job-posting API here. Remote publish needs a Naukri Amplify / partner integration.'}
        </p>
      )}
      {item.id === 'linkedin' && (
        <PremiumInput
          label="Company apply URL (required for LinkedIn API)"
          value={companyApplyUrl}
          onChange={(e) => setCompanyApplyUrl(e.target.value)}
          disabled={!canEdit}
          placeholder="https://your-careers-site.example/apply"
        />
      )}
      <div className="flex flex-wrap gap-4">
        <Toggle checked={enabled} onChange={setEnabled} disabled={!canEdit} enterprise={enterprise} label="Enabled" />
        <Toggle
          checked={autoPublish}
          onChange={setAutoPublish}
          disabled={!canEdit}
          enterprise={enterprise}
          label="Auto Publish"
        />
        <Toggle
          checked={autoSync}
          onChange={setAutoSync}
          disabled={!canEdit}
          enterprise={enterprise}
          label="Auto Sync"
        />
      </div>

      {showHttpFields && (
        <div className="grid gap-3">
          <PremiumInput
            label="API Base URL"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            disabled={!canEdit}
            placeholder="https://api.example.com"
          />
          <PremiumInput
            label="Logo URL (optional)"
            value={logoUrl}
            onChange={(e) => setLogoUrl(e.target.value)}
            disabled={!canEdit}
            placeholder="https://cdn.example.com/logo.png"
          />
          <PremiumInput
            label="Test endpoint"
            value={epTest}
            onChange={(e) => setEpTest(e.target.value)}
            disabled={!canEdit}
            placeholder="GET /health"
          />
          <PremiumInput
            label="Publish endpoint"
            value={epPublish}
            onChange={(e) => setEpPublish(e.target.value)}
            disabled={!canEdit}
            placeholder="POST /jobs"
          />
          <PremiumInput
            label="Update endpoint"
            value={epUpdate}
            onChange={(e) => setEpUpdate(e.target.value)}
            disabled={!canEdit}
            placeholder="PUT /jobs/{externalJobId}"
          />
          <PremiumInput
            label="Close endpoint"
            value={epClose}
            onChange={(e) => setEpClose(e.target.value)}
            disabled={!canEdit}
            placeholder="POST /jobs/{externalJobId}/close"
          />
          <PremiumInput
            label="Applications sync endpoint"
            value={epApps}
            onChange={(e) => setEpApps(e.target.value)}
            disabled={!canEdit}
            placeholder="GET /jobs/{externalJobId}/applications"
          />
        </div>
      )}

      <div className="grid gap-3">
        <PremiumInput
          label="Client ID"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          disabled={!canEdit}
          placeholder="Client ID"
        />
        <PremiumInput
          label="Client Secret"
          type="password"
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          disabled={!canEdit}
          placeholder={cfg.clientSecretConfigured ? '•••••••• (configured)' : 'Client secret'}
        />
        <PremiumInput
          label="Access Token"
          type="password"
          value={accessToken}
          onChange={(e) => setAccessToken(e.target.value)}
          disabled={!canEdit}
          placeholder={cfg.accessTokenConfigured ? '•••••••• (configured)' : 'Access token'}
        />
        <PremiumInput
          label="Refresh Token"
          type="password"
          value={refreshToken}
          onChange={(e) => setRefreshToken(e.target.value)}
          disabled={!canEdit}
          placeholder={cfg.refreshTokenConfigured ? '•••••••• (configured)' : 'Refresh token'}
        />
      </div>

      {msg.text && (
        <div
          className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${
            msg.type === 'success'
              ? enterprise
                ? 'bg-[rgba(54,214,160,0.1)] text-[#67DFB4]'
                : 'bg-green-50 text-green-700'
              : enterprise
                ? 'bg-[rgba(255,102,133,0.1)] text-[#FF7B8E]'
                : 'bg-red-50 text-red-700'
          }`}
        >
          {msg.type === 'success' ? <FiCheck /> : <FiAlertCircle />}
          {msg.text}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {canEdit && (
          enterprise ? (
            <button
              type="button"
              disabled={busy}
              onClick={handleSave}
              className="org-btn-primary disabled:opacity-50 inline-flex items-center gap-2"
            >
              <FiSave className="w-4 h-4" />
              {busy ? 'Saving…' : 'Save'}
            </button>
          ) : (
            <PremiumButton type="button" variant="primary" loading={busy} onClick={handleSave}>
              Save
            </PremiumButton>
          )
        )}
        <button
          type="button"
          disabled={busy}
          onClick={handleTest}
          className={
            enterprise
              ? 'org-btn-ghost disabled:opacity-50 inline-flex items-center gap-2'
              : 'inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 text-sm disabled:opacity-50'
          }
        >
          <FiRefreshCw className="w-4 h-4" />
          Test Connection
        </button>
      </div>
    </div>
  )
}

function AddPlatformForm({ enterprise, onCancel, onCreated }) {
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [logoUrl, setLogoUrl] = useState('')
  const [epTest, setEpTest] = useState('GET /health')
  const [epPublish, setEpPublish] = useState('POST /jobs')
  const [epUpdate, setEpUpdate] = useState('PUT /jobs/{externalJobId}')
  const [epClose, setEpClose] = useState('POST /jobs/{externalJobId}/close')
  const [epApps, setEpApps] = useState('GET /jobs/{externalJobId}/applications')
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [accessToken, setAccessToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const handleCreate = async (e) => {
    e.preventDefault()
    setError('')
    if (!name.trim()) {
      setError('Platform name is required')
      return
    }
    if (!baseUrl.trim()) {
      setError('API Base URL is required')
      return
    }
    if (!(accessToken.trim() || (clientId.trim() && clientSecret.trim()))) {
      setError('Provide Access Token or Client ID + Client Secret')
      return
    }
    if (baseUrl.trim() && !/^https:\/\//i.test(baseUrl.trim())) {
      setError('API Base URL must start with https://')
      return
    }
    if (logoUrl.trim() && !/^https:\/\//i.test(logoUrl.trim())) {
      setError('Logo URL must be an https:// URL')
      return
    }
    setBusy(true)
    try {
      const body = {
        name: name.trim(),
        displayName: name.trim(),
        custom: true,
        enabled: true,
        status: 'connected',
        clientId: clientId.trim(),
        baseUrl: baseUrl.trim(),
        settings: {
          adapter: 'http',
          displayName: name.trim(),
          baseUrl: baseUrl.trim(),
          authHeader: 'Bearer',
          endpoints: {
            test: epTest.trim(),
            publish: epPublish.trim(),
            update: epUpdate.trim(),
            close: epClose.trim(),
            applications: epApps.trim(),
          },
        },
      }
      if (logoUrl.trim()) {
        body.logoUrl = logoUrl.trim()
        body.settings.logoUrl = logoUrl.trim()
      }
      if (slug.trim()) body.provider = slug.trim().toLowerCase()
      if (clientSecret.trim()) body.clientSecret = clientSecret.trim()
      if (accessToken.trim()) body.accessToken = accessToken.trim()
      await createProviderConfig(body)
      onCreated?.()
    } catch (err) {
      setError(err.message || 'Failed to add platform')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      onSubmit={handleCreate}
      className={
        enterprise
          ? 'org-glass-panel p-5 space-y-3'
          : 'rounded-2xl border border-slate-200 p-5 space-y-3 bg-white'
      }
    >
      <div className="flex items-center justify-between">
        <h3 className={enterprise ? 'font-semibold text-[var(--ei-text-primary)]' : 'font-semibold'}>
          Add platform
        </h3>
        <button type="button" onClick={onCancel} className="p-1 text-[var(--ei-text-muted)]">
          <FiX className="w-4 h-4" />
        </button>
      </div>
      <p className={enterprise ? 'text-sm text-[var(--ei-text-secondary)]' : 'text-sm text-slate-500'}>
        Connect Indeed, Glassdoor, Hirist, Monster, or any board with an HTTP API.
      </p>
      <PremiumInput label="Platform name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Glassdoor" />
      <PremiumInput
        label="Slug (optional)"
        value={slug}
        onChange={(e) => setSlug(e.target.value)}
        placeholder="glassdoor"
      />
      <PremiumInput
        label="API Base URL"
        value={baseUrl}
        onChange={(e) => setBaseUrl(e.target.value)}
        placeholder="https://api.example.com"
      />
      <PremiumInput
        label="Logo URL (optional)"
        value={logoUrl}
        onChange={(e) => setLogoUrl(e.target.value)}
        placeholder="https://cdn.example.com/logo.png"
      />
      <PremiumInput label="Test endpoint" value={epTest} onChange={(e) => setEpTest(e.target.value)} />
      <PremiumInput label="Publish endpoint" value={epPublish} onChange={(e) => setEpPublish(e.target.value)} />
      <PremiumInput label="Update endpoint" value={epUpdate} onChange={(e) => setEpUpdate(e.target.value)} />
      <PremiumInput label="Close endpoint" value={epClose} onChange={(e) => setEpClose(e.target.value)} />
      <PremiumInput label="Applications endpoint" value={epApps} onChange={(e) => setEpApps(e.target.value)} />
      <PremiumInput label="Client ID" value={clientId} onChange={(e) => setClientId(e.target.value)} />
      <PremiumInput
        label="Client Secret"
        type="password"
        value={clientSecret}
        onChange={(e) => setClientSecret(e.target.value)}
      />
      <PremiumInput
        label="Access Token"
        type="password"
        value={accessToken}
        onChange={(e) => setAccessToken(e.target.value)}
      />
      {error && <p className="text-sm text-[#FF7B8E]">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="org-btn-primary disabled:opacity-50">
          {busy ? 'Adding…' : 'Add platform'}
        </button>
        <button type="button" onClick={onCancel} className="org-btn-ghost">
          Cancel
        </button>
      </div>
    </form>
  )
}

export default function IntegrationsSettingsPanel({ enterprise = false }) {
  const { auth } = useApp()
  const canEdit = isHeadHr(auth)
  const [catalog, setCatalog] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showAdd, setShowAdd] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetchIntegrationProviders()
      setCatalog(res?.providers || [])
    } catch (e) {
      setError(e.message || 'Failed to load integrations')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const builtins = useMemo(() => (catalog || []).filter((p) => p.builtin !== false && (p.id === 'linkedin' || p.id === 'naukri' || p.builtin)), [catalog])
  const customs = useMemo(() => (catalog || []).filter((p) => p.builtin === false), [catalog])

  // Ensure LinkedIn/Naukri always appear even if API omits empty configs
  const builtinCards = useMemo(() => {
    const byId = Object.fromEntries(builtins.map((p) => [p.id, p]))
    return ['linkedin', 'naukri'].map((id) => {
      if (byId[id]) return byId[id]
      return {
        id,
        name: id === 'linkedin' ? 'LinkedIn' : 'Naukri',
        builtin: true,
        accessRequired: true,
        configured: false,
        config: { status: 'provider_access_required' },
      }
    })
  }, [builtins])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p
          className={
            enterprise
              ? 'text-sm text-[var(--ei-text-secondary)]'
              : 'text-sm text-slate-500 dark:text-slate-400'
          }
        >
          LinkedIn and Naukri require partner API access before jobs can be published remotely.
          Status shows Provider access required until that access exists — not Published.
          Connect Google Calendar (your account) for interview scheduling after shortlist.
          Add any other job board with its API Base URL and endpoints.
          {!canEdit && ' Only Head HR can edit provider settings.'}
        </p>
        {canEdit && !showAdd && (
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className={
              enterprise
                ? 'org-btn-ghost inline-flex items-center gap-2 text-sm'
                : 'inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 text-sm'
            }
          >
            <FiPlus className="w-4 h-4" />
            Add platform
          </button>
        )}
      </div>

      {showAdd && canEdit && (
        <AddPlatformForm
          enterprise={enterprise}
          onCancel={() => setShowAdd(false)}
          onCreated={() => {
            setShowAdd(false)
            load()
          }}
        />
      )}

      {loading && (
        <p className={enterprise ? 'text-[var(--ei-text-muted)]' : 'text-slate-500'}>Loading…</p>
      )}
      {error && <p className={enterprise ? 'text-[#FF7B8E]' : 'text-red-600'}>{error}</p>}

      <GoogleCalendarConnectCard enterprise={enterprise} />

      <div className="grid gap-4">
        {builtinCards.map((p) => (
          <ProviderCard
            key={p.id}
            item={{ ...p, builtin: true }}
            enterprise={enterprise}
            canEdit={canEdit}
            onSaved={load}
            showHttpFields={false}
          />
        ))}
        {customs.map((p) => (
          <ProviderCard
            key={p.id}
            item={p}
            enterprise={enterprise}
            canEdit={canEdit}
            onSaved={load}
            showHttpFields
          />
        ))}
      </div>
    </div>
  )
}
