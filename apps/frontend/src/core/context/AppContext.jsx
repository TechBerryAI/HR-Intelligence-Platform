import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { apiRequest, setUnauthorizedHandler, setOnTokensRefreshed } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import { checkBackendHealth } from '@/core/api/healthCheck.js'
import { isStaffRecruiter } from '@/core/permissions/rbac.js'

// App state: jobs and auth via backend
const AppContext = createContext(null)

const STORAGE_KEYS = {
  auth: 'authState',
  applicantSavedJobs: 'applicantSavedJobsState',
  jobs: 'jobsState',
  user: 'authUser',
}

// Helper functions for localStorage
const readJson = (key, fallback) => {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch (err) {
    console.warn('Failed to parse storage key', key, err)
    return fallback
  }
}

const writeJson = (key, value) => {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch (err) {
    console.warn('Failed to persist storage key', key, err)
  }
}

function decodeJwtRole(token) {
  if (!token) return null
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
    return payload.role || null
  } catch {
    return null
  }
}

export function AppProvider({ children }) {
  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(false)
  const [jobsError, setJobsError] = useState('')
  // Bumped after create/enable/disable/delete so public /jobs refetches
  const [jobsBoardRevision, setJobsBoardRevision] = useState(0)
  const bumpJobsBoard = () => setJobsBoardRevision((n) => n + 1)

  const defaultAuth = { isLoggedIn: false, role: null, email: '' }

  const [auth, setAuth] = useState(() => readJson(STORAGE_KEYS.auth, defaultAuth))
  const [token, setToken] = useState(() => tokenService.getToken())
  const [user, setUser] = useState(() => readJson(STORAGE_KEYS.user, null))
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState('')
  const [applicantSavedJobs, setApplicantSavedJobs] = useState(() => readJson(STORAGE_KEYS.applicantSavedJobs, {})) // jobId -> true
  const [backendHealthy, setBackendHealthy] = useState(true) // Backend health status - default to true
  const [healthCheckAttempts, setHealthCheckAttempts] = useState(0)
  const logoutRef = useRef(() => {})

  // No-op for candidate; clears HR session when another staff login takes over
  const clearOtherSessions = (activeType) => {
    if (activeType !== 'hr') {
      setAuth(defaultAuth)
      writeJson(STORAGE_KEYS.auth, defaultAuth)
    }
  }

  useEffect(() => {
    setUnauthorizedHandler(() => logoutRef.current())
    setOnTokensRefreshed((newAccess) => { setToken(newAccess) })
    
    // Wait 2 seconds before first health check to allow backend startup
    const initialCheckTimer = setTimeout(() => {
      checkBackendHealth().then(isHealthy => {
        setBackendHealthy(isHealthy)
        setHealthCheckAttempts(1)
      })
    }, 2000)
    
    // Periodic health check every 30 seconds
    const healthCheckInterval = setInterval(() => {
      checkBackendHealth().then(isHealthy => {
        setBackendHealthy(isHealthy)
        if (!isHealthy) {
          setHealthCheckAttempts(prev => prev + 1)
        } else {
          setHealthCheckAttempts(0)
        }
      })
    }, 30000)
    
    return () => {
      clearTimeout(initialCheckTimer)
      clearInterval(healthCheckInterval)
    }
    
    // If migrating to HttpOnly cookies in production:
    // - Have the backend set a SameSite=Lax, Secure HttpOnly cookie on login
    // - Remove Authorization header usage and token persistence here
    // - Rely on credentials: 'include' already set in api.js
    // - Ensure CORS allows credentials and your frontend domain
    // Note: keep tokenService empty or disabled when using HttpOnly cookies.
  }, [])

  useEffect(() => {
    if (token) tokenService.setToken(token)
  }, [token])

  useEffect(() => {
    if (typeof window === 'undefined') return
    writeJson(STORAGE_KEYS.auth, auth)
  }, [auth])

  useEffect(() => {
    if (typeof window === 'undefined') return
    writeJson(STORAGE_KEYS.applicantSavedJobs, applicantSavedJobs)
  }, [applicantSavedJobs])

  // Do not persist jobs; source of truth is backend

  // Persist user only (token is kept in-memory for security)
  useEffect(() => {
    if (typeof window === 'undefined') return
    if (user) writeJson(STORAGE_KEYS.user, user)
    else window.localStorage.removeItem(STORAGE_KEYS.user)
  }, [user])

  useEffect(() => {
    if (typeof window === 'undefined') return

    const hydrateFromStorage = () => {
      setAuth((prev) => {
        const stored = readJson(STORAGE_KEYS.auth, defaultAuth)
        return JSON.stringify(prev) === JSON.stringify(stored) ? prev : stored
      })
      // Do not hydrate token from storage
      setUser(() => readJson(STORAGE_KEYS.user, null))
    }

    hydrateFromStorage()

    const onStorage = (event) => {
      if (event.storageArea !== window.localStorage) return
      if (!event.key || Object.values(STORAGE_KEYS).includes(event.key)) {
        hydrateFromStorage()
      }
    }

    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const loginHR = async (email, password) => {
    setAuthError('')
    setAuthLoading(true)
    try {
      const data = await apiRequest('/api/login', {
        method: 'POST',
        body: { email, password },
      })
      if (data && data.token && data.user) {
        clearOtherSessions('hr')
        setToken(data.token)
        tokenService.setToken(data.token)
        if (data.refresh_token) tokenService.setRefreshToken(data.refresh_token)
        setUser(data.user)
        const role = data.user.role || 'RECRUITER'
        const nextAuth = { isLoggedIn: true, role, email: data.user.email || email, fullName: data.user.fullName, company: data.user.company }
        setAuth(nextAuth)
        writeJson(STORAGE_KEYS.auth, nextAuth)
        return { ok: true, user: data.user }
      }
      return { ok: false, message: 'Invalid response from server' }
    } catch (err) {
      setAuthError(err?.message || 'Login failed')
      return { ok: false, message: err?.message || 'Login failed' }
    } finally {
      setAuthLoading(false)
    }
  }

  const requestHrPasswordReset = async (email) => {
    if (!email) return { ok: false, message: 'Email is required' }
    try {
      const data = await apiRequest('/api/forgot-password', {
        method: 'POST',
        body: { email },
      })
      return { ok: true, data }
    } catch (err) {
      return { ok: false, message: err?.message || 'Failed to send OTP' }
    }
  }

  const verifyHrPasswordOtp = async ({ email, otp }) => {
    try {
      const data = await apiRequest('/api/forgot-password/verify-otp', {
        method: 'POST',
        body: { email, otp },
      })
      return { ok: true, data }
    } catch (err) {
      return { ok: false, message: err?.message || 'OTP verification failed' }
    }
  }

  const resetHrPassword = async ({ email, otp, newPassword, confirmPassword }) => {
    try {
      const data = await apiRequest('/api/reset-password', {
        method: 'POST',
        body: { email, otp, newPassword, confirmPassword },
      })
      return { ok: true, data }
    } catch (err) {
      return { ok: false, message: err?.message || 'Failed to reset password' }
    }
  }

  const changePasswordHr = async ({ currentPassword, newPassword }) => {
    const authToken = token || tokenService.getToken()
    if (!authToken) return { ok: false, message: 'Not logged in' }
    try {
      await apiRequest('/api/change-password', {
        method: 'POST',
        token: authToken,
        body: { currentPassword, newPassword },
      })
      return { ok: true }
    } catch (err) {
      return { ok: false, message: err?.message || 'Failed to change password' }
    }
  }

  const signupHR = async ({ fullName, email, password, company }) => {
    setAuthError('')
    setAuthLoading(true)
    try {
      const data = await apiRequest('/api/signup', {
        method: 'POST',
        body: { fullName, email, password, company },
      })
      return { ok: true, data }
    } catch (err) {
      setAuthError(err?.message || 'Signup failed')
      return { ok: false, message: err?.message || 'Signup failed' }
    } finally {
      setAuthLoading(false)
    }
  }

  const verifyHROTP = async ({ email, otp }) => {
    setAuthError('')
    setAuthLoading(true)
    try {
      const data = await apiRequest('/api/verify-otp', {
        method: 'POST',
        body: { email, otp },
      })
      // If verification successful and token provided, store auth
      if (data && data.token && data.user) {
        clearOtherSessions('hr')
        setToken(data.token)
        tokenService.setToken(data.token)
        if (data.refresh_token) tokenService.setRefreshToken(data.refresh_token)
        setUser(data.user)
        const role = data.user.role || 'RECRUITER'
        const nextAuth = { isLoggedIn: true, role, email: data.user.email || email }
        setAuth(nextAuth)
        writeJson(STORAGE_KEYS.auth, nextAuth)
      }
      return { ok: true, data }
    } catch (err) {
      setAuthError(err?.message || 'OTP verification failed')
      return { ok: false, message: err?.message || 'OTP verification failed' }
    } finally {
      setAuthLoading(false)
    }
  }

  const resendHROTP = async ({ email }) => {
    setAuthError('')
    setAuthLoading(true)
    try {
      const data = await apiRequest('/api/resend-otp', {
        method: 'POST',
        body: { email },
      })
      return { ok: true, data }
    } catch (err) {
      const errorMessage = err?.message || err?.error || 'Failed to resend OTP'
      setAuthError(errorMessage)
      return { ok: false, message: errorMessage }
    } finally {
      setAuthLoading(false)
    }
  }

  const toggleSaveJob = (jobId) => {
    setApplicantSavedJobs((prev) => {
      const next = { ...prev }
      const key = String(jobId)
      if (next[key] || next[jobId]) {
        // Unsave
        delete next[key]
        delete next[jobId]
      } else {
        // Save
        next[jobId] = true
        next[key] = true
      }
      return next
    })
  }

  const logout = () => {
    setAuth(defaultAuth)
    setToken('')
    tokenService.clear()
    setUser(null)
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(STORAGE_KEYS.auth)
      window.localStorage.removeItem(STORAGE_KEYS.user)
      // Keep applicantSavedJobs as anonymous localStorage bookmarks
    }
  }

  logoutRef.current = logout

  useEffect(() => {
    const storedToken = tokenService.getToken()
    const role = decodeJwtRole(storedToken)

    if (!storedToken) {
      const hrAuth = readJson(STORAGE_KEYS.auth, defaultAuth)
      if (hrAuth.isLoggedIn) {
        logoutRef.current()
      }
      return
    }

    if (role === 'CANDIDATE') {
      // Candidate tokens are no longer supported; clear session
      logoutRef.current()
    } else if (role === 'RECRUITER' || role === 'HEAD_HR' || role === 'CEO') {
      clearOtherSessions('hr')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const getToken = () => token

  // Fetch applications for a specific job (HR only)
  const fetchApplicationsForJob = async (jobId) => {
    if (!auth.isLoggedIn || (auth.role !== 'RECRUITER' && auth.role !== 'HEAD_HR')) {
      return { ok: false, message: 'Unauthorized' }
    }
    try {
      const data = await apiRequest(`/api/jobs/${jobId}/applications`, {
        method: 'GET',
        token
      })
      return { ok: true, data: data.applications || data || [] }
    } catch (err) {
      // 404 = job not found or no access: show empty candidates instead of error
      if (err?.status === 404) {
        return { ok: true, data: [] }
      }
      if (import.meta.env?.DEV) {
        console.error('Fetch applications error:', err)
      }
      return { ok: false, message: err?.message || 'Failed to fetch applications' }
    }
  }

  // Fetch all applications grouped by job (HR only)
  const fetchAllApplications = async () => {
    if (!auth.isLoggedIn || (auth.role !== 'RECRUITER' && auth.role !== 'HEAD_HR')) {
      return { ok: false, message: 'Unauthorized' }
    }
    try {
      const data = await apiRequest('/api/applications/all', {
        method: 'GET',
        token
      })
      return { ok: true, data: data.applications || data || [] }
    } catch (err) {
      console.error('Fetch all applications error:', err)
      return { ok: false, message: err?.message || 'Failed to fetch applications' }
    }
  }

  // Public board: GET /api/jobs (enabled jobs). Staff dashboard: GET /api/jobs/all (company / org scope).
  const fetchJobs = async () => {
    setJobsLoading(true)
    setJobsError('')
    try {
      const authToken = token || tokenService.getToken()
      const staff = Boolean(authToken) && isStaffRecruiter(auth)
      const path = staff ? '/api/jobs/all' : '/api/jobs'
      const data = await apiRequest(path, {
        method: 'GET',
        ...(staff ? { token: authToken } : {}),
      })
      if (Array.isArray(data)) setJobs(data)
      else if (data && Array.isArray(data.jobs)) setJobs(data.jobs)
      else setJobs([])
    } catch (err) {
      setJobsError(err?.message || 'Failed to load jobs')
    } finally {
      setJobsLoading(false)
    }
  }

  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(STORAGE_KEYS.jobs)
      }
    } catch {}
  }, [])

  useEffect(() => {
    fetchJobs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isLoggedIn, token])

  // Admin: add a job (best-effort). If backend supports it, create and refresh list.
  const addJob = async (job) => {
    try {
      if (!token) {
        console.error('No token available - user may not be logged in')
        return { success: false, error: 'You must be logged in to create a job. Please log in and try again.' }
      }
      
      const result = await apiRequest('/api/jobs', { method: 'POST', body: job, token })
      await fetchJobs()
      bumpJobsBoard()
      return { success: true, data: result }
    } catch (err) {
      let errorMessage = 'Failed to create job'
      if (err?.status === 401 || err?.status === 403) {
        errorMessage = 'Authentication failed. Please log in again.'
      } else if (err?.status === 400) {
        errorMessage = err?.data?.error || err?.message || 'Invalid job data. Please check all fields.'
      } else if (err?.message === 'Network error' || err?.cause) {
        errorMessage = 'Cannot connect to server. Please check if the backend is running.'
      } else {
        errorMessage = err?.data?.error || err?.message || 'Failed to create job. Please try again.'
      }
      
      return { success: false, error: errorMessage }
    }
  }

  const setJobEnabled = async (jobId, isEnabled) => {
    if (!token) {
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, enabled: isEnabled } : j)))
      bumpJobsBoard()
      return { success: true }
    }
    try {
      await apiRequest(`/api/jobs/${jobId}/enabled`, {
        method: 'PATCH',
        body: { enabled: isEnabled },
        token
      })
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, enabled: isEnabled } : j)))
      bumpJobsBoard()
      return { success: true }
    } catch (err) {
      console.error('Set job enabled error:', err)
      return { success: false, error: err?.data?.error || err?.message || 'Failed to update job status' }
    }
  }

  const deleteJob = async (jobId) => {
    if (!token) {
      return { success: false, error: 'You must be logged in to delete a job.' }
    }
    try {
      await apiRequest(`/api/jobs/${encodeURIComponent(jobId)}`, {
        method: 'DELETE',
        token,
      })
      setJobs((prev) => prev.filter((j) => j.id !== jobId && j.jdid !== jobId))
      bumpJobsBoard()
      return { success: true }
    } catch (err) {
      console.error('Delete job error:', err)
      return { success: false, error: err?.data?.error || err?.message || 'Failed to delete job' }
    }
  }

  const updateJob = async (jobId, updates) => {
    if (!token) {
      // Fallback to local update
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, ...updates } : j)))
      bumpJobsBoard()
      return
    }
    try {
      const updated = await apiRequest(`/api/jobs/${jobId}`, {
        method: 'PUT',
        body: updates,
        token
      })
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...updated } : j)))
      await fetchJobs() // Refresh to get latest data
      bumpJobsBoard()
    } catch (err) {
      console.error('Update job error:', err)
      // Fallback to local update
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, ...updates } : j)))
    }
  }

  const value = useMemo(() => ({
    jobs,
    jobsLoading,
    jobsError,
    jobsBoardRevision,
    fetchJobs,
    addJob,
    setJobEnabled,
    deleteJob,
    updateJob,
    auth,
    authLoading,
    authError,
    loginHR,
    applicantSavedJobs,
    signupHR,
    verifyHROTP,
    resendHROTP,
    requestHrPasswordReset,
    verifyHrPasswordOtp,
    resetHrPassword,
    changePasswordHr,
    toggleSaveJob,
    getToken,
    logout,
    user,
    fetchApplicationsForJob,
    fetchAllApplications,
    backendHealthy,
  }), [jobs, jobsLoading, jobsError, jobsBoardRevision, auth, authLoading, authError, applicantSavedJobs, user, token, backendHealthy])

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
