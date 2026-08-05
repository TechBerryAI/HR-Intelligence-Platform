import React, { useCallback, useEffect, useState } from 'react'
import { FiCheck, FiAlertCircle, FiLink, FiRefreshCw, FiSave } from 'react-icons/fi'
import { Linkedin, Briefcase, Globe } from 'lucide-react'
import PremiumInput from '@/shared/components/PremiumInput.jsx'
import PremiumButton from '@/shared/components/PremiumButton.jsx'
import { isHeadHr } from '@/core/permissions/rbac.js'
import { useApp } from '@/core/context/AppContext.jsx'
import {
  fetchIntegrationProviders,
  saveProviderConfig,
  testProviderConnection,
  connectProvider,
} from '@/features/settings/services/integrationsApi.js'

const ICONS = {
  linkedin: Linkedin,
  naukri: Briefcase,
  indeed: Globe,
}

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
              ? 'bg-[#00A6FF]'
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

function ProviderCard({ item, enterprise, canEdit, onSaved }) {
  const cfg = item.config || {}
  const Icon = ICONS[item.id] || Globe
  const [enabled, setEnabled] = useState(!!cfg.enabled)
  const [autoPublish, setAutoPublish] = useState(!!cfg.autoPublish)
  const [autoSync, setAutoSync] = useState(!!cfg.autoSync)
  const [clientId, setClientId] = useState(cfg.clientId || '')
  const [clientSecret, setClientSecret] = useState('')
  const [accessToken, setAccessToken] = useState('')
  const [refreshToken, setRefreshToken] = useState('')
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
  }, [cfg.enabled, cfg.autoPublish, cfg.autoSync, cfg.clientId, item.id])

  const statusLabel = cfg.status === 'connected' ? 'Connected' : 'Disconnected'
  const statusOk = cfg.status === 'connected'

  const handleSave = async () => {
    setBusy(true)
    setMsg({ type: '', text: '' })
    try {
      const body = {
        enabled,
        autoPublish,
        autoSync,
        clientId,
        status: enabled ? 'connected' : cfg.status || 'disconnected',
      }
      if (clientSecret.trim()) body.clientSecret = clientSecret.trim()
      if (accessToken.trim()) body.accessToken = accessToken.trim()
      if (refreshToken.trim()) body.refreshToken = refreshToken.trim()
      await saveProviderConfig(item.id, body)
      if (enabled) {
        await connectProvider(item.id, body).catch(() => null)
      }
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
      const res = await testProviderConnection(item.id)
      const ok = res?.result?.success
      setMsg({
        type: ok ? 'success' : 'error',
        text: res?.result?.message || res?.result?.error || (ok ? 'Connection OK' : 'Test failed'),
      })
    } catch (e) {
      setMsg({ type: 'error', text: e.message || 'Test failed' })
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
                ? 'h-11 w-11 rounded-xl bg-[var(--ei-surface-hover)] flex items-center justify-center text-[#00A6FF] ring-1 ring-[var(--ei-border-primary)]'
                : 'h-11 w-11 rounded-xl bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-primary'
            }
          >
            <Icon className="w-5 h-5" />
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
      </div>

      <div className="flex flex-wrap gap-4">
        <Toggle
          checked={enabled}
          onChange={setEnabled}
          disabled={!canEdit}
          enterprise={enterprise}
          label="Enabled"
        />
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
          <>
            {enterprise ? (
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
            )}
          </>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={handleTest}
          className={
            enterprise
              ? 'org-btn-ghost disabled:opacity-50 inline-flex items-center gap-2'
              : 'inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-600 text-sm disabled:opacity-50'
          }
        >
          <FiRefreshCw className="w-4 h-4" />
          Test Connection
        </button>
        <button
          type="button"
          disabled
          title="OAuth will be available when provider APIs are connected"
          className={
            enterprise
              ? 'org-btn-ghost opacity-40 cursor-not-allowed inline-flex items-center gap-2'
              : 'inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 text-sm opacity-40 cursor-not-allowed'
          }
        >
          Connect with OAuth
        </button>
      </div>
    </div>
  )
}

export default function IntegrationsSettingsPanel({ enterprise = false }) {
  const { auth } = useApp()
  const canEdit = isHeadHr(auth)
  const [providers, setProviders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetchIntegrationProviders()
      setProviders(res?.providers || [])
    } catch (e) {
      setError(e.message || 'Failed to load integrations')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="space-y-4">
      <p
        className={
          enterprise
            ? 'text-sm text-[var(--ei-text-secondary)]'
            : 'text-sm text-slate-500 dark:text-slate-400'
        }
      >
        Configure job-board providers for your company. Credentials are encrypted at rest.
        {!canEdit && ' Only Head HR can edit provider settings.'}
      </p>
      {loading && (
        <p className={enterprise ? 'text-[var(--ei-text-muted)]' : 'text-slate-500'}>Loading…</p>
      )}
      {error && (
        <p className={enterprise ? 'text-[#FF7B8E]' : 'text-red-600'}>{error}</p>
      )}
      <div className="grid gap-4">
        {providers.map((p) => (
          <ProviderCard
            key={p.id}
            item={p}
            enterprise={enterprise}
            canEdit={canEdit}
            onSaved={load}
          />
        ))}
      </div>
    </div>
  )
}
