import { useCallback, useEffect, useState } from 'react'
import { useApp } from '@/core/context/AppContext.jsx'
import { isHeadHr } from '@/core/permissions/rbac.js'
import { fetchDeveloperStatus } from '@/features/admin/services/developerPerformanceService.js'

const STORAGE_KEY = 'hcip_admin_developer_mode'
const CHANGE_EVENT = 'hcip-developer-mode-change'

function readPreference() {
  if (typeof window === 'undefined') return false
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

function writePreference(on) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, on ? 'true' : 'false')
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: { on: Boolean(on) } }))
}

/**
 * Developer Mode UI — Admin (HEAD_HR) only.
 *
 * Visibility = backend DEVELOPER_MODE available + admin Settings toggle ON.
 */
export function useDeveloperMode() {
  const { auth } = useApp()
  const isAdmin = isHeadHr(auth)
  const [preference, setPreference] = useState(readPreference)
  const [backendAvailable, setBackendAvailable] = useState(false)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!auth?.isLoggedIn || !isAdmin) {
      setBackendAvailable(false)
      setLoading(false)
      return false
    }
    setLoading(true)
    try {
      const status = await fetchDeveloperStatus()
      // developer_mode = server flag; enabled from API also requires HEAD_HR
      const available = Boolean(status.developerMode || status.developer_mode)
      setBackendAvailable(available)
      return available
    } catch {
      setBackendAvailable(false)
      return false
    } finally {
      setLoading(false)
    }
  }, [auth, isAdmin])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    const sync = () => setPreference(readPreference())
    const onCustom = (e) => setPreference(Boolean(e?.detail?.on))
    window.addEventListener('storage', sync)
    window.addEventListener(CHANGE_EVENT, onCustom)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener(CHANGE_EVENT, onCustom)
    }
  }, [])

  const setToggle = useCallback(
    (on) => {
      if (!isAdmin) return
      const next = Boolean(on)
      writePreference(next)
      setPreference(next)
    },
    [isAdmin]
  )

  const enabled = Boolean(isAdmin && backendAvailable && preference)

  return {
    /** Show Developer Mode nav / dashboard */
    enabled,
    /** Admin turned the Settings toggle on */
    preference,
    /** Backend DEVELOPER_MODE=true */
    backendAvailable,
    loading,
    isAdmin,
    setToggle,
    refresh,
  }
}
