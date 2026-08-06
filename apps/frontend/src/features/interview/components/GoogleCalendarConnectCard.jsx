import React, { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FiCalendar, FiCheckCircle, FiLink, FiUnlink } from 'react-icons/fi'
import {
  disconnectGoogleCalendar,
  fetchGoogleCalendarStatus,
  startGoogleCalendarConnect,
} from '@/features/interview/services/calendarApi.js'

/**
 * Recruiter-scoped Google Calendar OAuth card for Settings → Integrations.
 */
export default function GoogleCalendarConnectCard({ enterprise = false }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [banner, setBanner] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetchGoogleCalendarStatus()
      setStatus(res)
    } catch (e) {
      setError(e.message || 'Failed to load calendar status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const flag = (searchParams.get('calendar') || '').toLowerCase()
    if (!flag) return
    if (flag === 'connected') {
      setBanner('Google Calendar connected.')
      load()
    } else if (flag === 'error') {
      setBanner('Google Calendar connection failed. Try again.')
    }
    const next = new URLSearchParams(searchParams)
    next.delete('calendar')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams, load])

  async function onConnect() {
    setBusy(true)
    setError('')
    try {
      const res = await startGoogleCalendarConnect()
      if (res?.authUrl) {
        window.location.href = res.authUrl
        return
      }
      setError('No OAuth URL returned')
    } catch (e) {
      setError(e.message || 'Connect failed')
    } finally {
      setBusy(false)
    }
  }

  async function onDisconnect() {
    setBusy(true)
    setError('')
    try {
      await disconnectGoogleCalendar()
      setBanner('Google Calendar disconnected.')
      await load()
    } catch (e) {
      setError(e.message || 'Disconnect failed')
    } finally {
      setBusy(false)
    }
  }

  const connected = Boolean(status?.connected)
  const configured = status?.configured !== false

  return (
    <div
      className={
        enterprise
          ? 'rounded-xl border border-[var(--ei-border)] bg-[var(--ei-surface)] p-4'
          : 'rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900'
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div
            className={
              enterprise
                ? 'rounded-lg bg-[var(--ei-surface-hover)] p-2 text-[var(--ei-text-label)]'
                : 'rounded-lg bg-slate-100 p-2 text-slate-700 dark:bg-slate-800 dark:text-slate-200'
            }
          >
            <FiCalendar className="h-5 w-5" />
          </div>
          <div>
            <h3
              className={
                enterprise
                  ? 'text-sm font-semibold text-[var(--ei-text-label)]'
                  : 'text-sm font-semibold text-slate-900 dark:text-slate-100'
              }
            >
              Google Calendar
            </h3>
            <p
              className={
                enterprise
                  ? 'mt-1 text-xs text-[var(--ei-text-secondary)]'
                  : 'mt-1 text-xs text-slate-500 dark:text-slate-400'
              }
            >
              Connect your Google account so shortlisted candidates can book interview slots on your calendar.
            </p>
          </div>
        </div>
        {connected ? (
          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-600">
            <FiCheckCircle className="h-3.5 w-3.5" />
            Connected
          </span>
        ) : (
          <span
            className={
              enterprise
                ? 'rounded-md bg-[var(--ei-surface-hover)] px-2 py-1 text-xs text-[var(--ei-text-muted)]'
                : 'rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-500'
            }
          >
            Not connected
          </span>
        )}
      </div>

      {banner && (
        <p className="mt-3 text-xs text-emerald-700 dark:text-emerald-400">{banner}</p>
      )}
      {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
      {loading && (
        <p className={enterprise ? 'mt-3 text-xs text-[var(--ei-text-muted)]' : 'mt-3 text-xs text-slate-500'}>
          Checking status…
        </p>
      )}
      {!loading && !configured && (
        <p className="mt-3 text-xs text-amber-700">
          Google OAuth is not configured on the server (GOOGLE_OAUTH_CLIENT_ID / SECRET / REDIRECT_URI).
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {!connected ? (
          <button
            type="button"
            disabled={busy || !configured}
            onClick={onConnect}
            className={
              enterprise
                ? 'org-btn-ghost inline-flex items-center gap-2 text-sm disabled:opacity-50'
                : 'inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm disabled:opacity-50'
            }
          >
            <FiLink className="h-4 w-4" />
            {busy ? 'Connecting…' : 'Connect Google Calendar'}
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={onDisconnect}
            className={
              enterprise
                ? 'org-btn-ghost inline-flex items-center gap-2 text-sm text-[#FF7B8E]'
                : 'inline-flex items-center gap-2 rounded-xl border border-red-200 px-3 py-2 text-sm text-red-600'
            }
          >
            <FiUnlink className="h-4 w-4" />
            Disconnect
          </button>
        )}
      </div>
    </div>
  )
}
