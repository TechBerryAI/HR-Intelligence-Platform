import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { apiRequest, setUnauthorizedHandler, setOnTokensRefreshed } from '../utils/api'
import { tokenService } from '../utils/tokenService'
import { checkBackendHealth } from '../utils/healthCheck'

// App state: jobs and auth via backend
const AppContext = createContext(null)

const STORAGE_KEYS = {
  auth: 'authState',
  applicantAuth: 'applicantAuthState',
  applicantProfile: 'applicantProfileState',
  applicantApplications: 'applicantApplicationsState',
  applicantSavedJobs: 'applicantSavedJobsState',
  jobs: 'jobsState',
  user: 'authUser',
}

// Helper function to format date as YYYY-MM-DD
const formatDate = (date) => {
  if (typeof date === 'string') return date
  const d = date || new Date()
  return d.toISOString().split('T')[0]
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

  const defaultAuth = { isLoggedIn: false, role: null, email: '' }
  const defaultApplicantAuth = { isLoggedIn: false, email: '' }
  const defaultApplicantProfile = {
    experienceLevel: '',
    servingNotice: '',
    fullName: '',
    email: '',
    phone: '',
    noticePeriod: '',
    lastWorkingDay: '',
    linkedinUrl: '',
    portfolioUrl: '',
    currentLocation: '',
    preferredLocation: '',
    resumeFileName: '',
    education: [], // [{ degree, institution, year }]
    certifications: [], // [{ name, issuer, year }]
    experiences: [], // [{ company, role, years }]
    completed: false,
  }

  const [auth, setAuth] = useState(() => readJson(STORAGE_KEYS.auth, defaultAuth))
  const [applicantAuth, setApplicantAuth] = useState(() => readJson(STORAGE_KEYS.applicantAuth, defaultApplicantAuth))
  const [token, setToken] = useState(() => tokenService.getToken())
  const [user, setUser] = useState(() => readJson(STORAGE_KEYS.user, null))
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState('')
  const [applicantProfile, setApplicantProfile] = useState(() => readJson(STORAGE_KEYS.applicantProfile, defaultApplicantProfile))
  const [applicantApplications, setApplicantApplications] = useState(() => readJson(STORAGE_KEYS.applicantApplications, {})) // jobId -> true
  const [applicantSavedJobs, setApplicantSavedJobs] = useState(() => readJson(STORAGE_KEYS.applicantSavedJobs, {})) // jobId -> true
  const [backendHealthy, setBackendHealthy] = useState(true) // Backend health status - default to true
  const [healthCheckAttempts, setHealthCheckAttempts] = useState(0)
  const logoutRef = useRef(() => {})
  const fetchInFlightRef = useRef(null)

  const clearOtherSessions = (activeType) => {
    if (activeType !== 'hr') {
      setAuth(defaultAuth)
      writeJson(STORAGE_KEYS.auth, defaultAuth)
    }
    if (activeType !== 'candidate') {
      setApplicantAuth(defaultApplicantAuth)
      writeJson(STORAGE_KEYS.applicantAuth, defaultApplicantAuth)
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
    writeJson(STORAGE_KEYS.applicantAuth, applicantAuth)
  }, [applicantAuth])

  useEffect(() => {
    if (typeof window === 'undefined') return
    writeJson(STORAGE_KEYS.applicantProfile, applicantProfile)
  }, [applicantProfile])

  useEffect(() => {
    if (typeof window === 'undefined') return
    writeJson(STORAGE_KEYS.applicantApplications, applicantApplications)
  }, [applicantApplications])

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
      setApplicantAuth((prev) => {
        const stored = readJson(STORAGE_KEYS.applicantAuth, defaultApplicantAuth)
        return JSON.stringify(prev) === JSON.stringify(stored) ? prev : stored
      })
      setApplicantProfile((prev) => {
        const stored = readJson(STORAGE_KEYS.applicantProfile, defaultApplicantProfile)
        return JSON.stringify(prev) === JSON.stringify(stored) ? prev : stored
      })
      setApplicantApplications((prev) => {
        const stored = readJson(STORAGE_KEYS.applicantApplications, {})
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

  const changePasswordApplicant = async ({ currentPassword, newPassword }) => {
    const authToken = token || tokenService.getToken()
    if (!authToken) return { ok: false, message: 'Not logged in' }
    try {
      await apiRequest('/api/candidate/change-password', {
        method: 'POST',
        token: authToken,
        body: { currentPassword, newPassword },
      })
      return { ok: true }
    } catch (err) {
      return { ok: false, message: err?.message || 'Failed to change password' }
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

  // Fetch applications, saved jobs, and profile from backend (single source of truth for profile).
  // Memoized so consumers (e.g. ApplicationStatus) don't re-run their useEffects on every state
  // update from this fetch (which would cause an infinite request loop).
  const fetchApplicantData = useCallback(async () => {
    const authToken = token || tokenService.getToken()
    if (!applicantAuth.isLoggedIn || !authToken) return
    if (decodeJwtRole(authToken) !== 'CANDIDATE') return

    if (fetchInFlightRef.current) {
      return fetchInFlightRef.current
    }

    const promise = (async () => {
      try {
        const profileRes = await apiRequest('/api/candidate/profile', {
          method: 'GET',
          token: authToken,
          skipAuthHandler: true,
        }).catch(() => null)
        if (profileRes && typeof profileRes === 'object' && !profileRes.error) {
          const hasServerProfile =
            (profileRes.fullName && profileRes.fullName.trim()) ||
            (profileRes.email && profileRes.email.trim()) ||
            (profileRes.resumeFileName && profileRes.resumeFileName.trim()) ||
            (Array.isArray(profileRes.education) && profileRes.education.length > 0) ||
            (Array.isArray(profileRes.experiences) && profileRes.experiences.length > 0) ||
            (Array.isArray(profileRes.certifications) && profileRes.certifications.length > 0)
          if (hasServerProfile) {
            setApplicantProfile(profileRes)
            writeJson(STORAGE_KEYS.applicantProfile, profileRes)
          }
        }

        const applications = await apiRequest('/api/applications', {
          method: 'GET',
          token: authToken,
          skipAuthHandler: true,
        }).catch(() => [])
        const applicationsMap = {}
        if (Array.isArray(applications)) {
          applications.forEach(app => {
            const jobId = app.jobId || (app.job && app.job.id) || app.job_id
            if (jobId) {
              const status = app.status || 'applied'
              const shortlisted = !!app.shortlisted
              const entry = { status, shortlisted }
              applicationsMap[jobId] = entry
              applicationsMap[String(jobId)] = entry
            }
          })
        }
        setApplicantApplications(applicationsMap)
        writeJson(STORAGE_KEYS.applicantApplications, applicationsMap)
      } catch (err) {
        console.error('Fetch applicant data error:', err)
      } finally {
        fetchInFlightRef.current = null
      }
    })()

    fetchInFlightRef.current = promise
    return promise
  }, [token, applicantAuth.isLoggedIn])

  const loginApplicant = async (idOrEmail, password) => {
    setAuthError('')
    setAuthLoading(true)
    try {
      const data = await apiRequest('/api/candidate/login', {
        method: 'POST',
        body: { email: idOrEmail, password },
      })
      if (data && data.token && data.user) {
        clearOtherSessions('candidate')
        setToken(data.token)
        tokenService.setToken(data.token)
        if (data.refresh_token) tokenService.setRefreshToken(data.refresh_token)
        setUser(data.user)
        const nextApplicantAuth = { isLoggedIn: true, email: data.user.email || idOrEmail }
        setApplicantAuth(nextApplicantAuth)
        writeJson(STORAGE_KEYS.applicantAuth, nextApplicantAuth)

        const loginProfile = data.user.profile
        const hasFullProfile = loginProfile && (
          (loginProfile.fullName || loginProfile.email) &&
          (Array.isArray(loginProfile.education) || Array.isArray(loginProfile.experiences))
        )
        if (hasFullProfile) {
          setApplicantProfile(loginProfile)
          writeJson(STORAGE_KEYS.applicantProfile, loginProfile)
        } else {
          setApplicantProfile((p) => {
            const nextProfile = { ...p, email: data.user.email || idOrEmail }
            writeJson(STORAGE_KEYS.applicantProfile, nextProfile)
            return nextProfile
          })
        }

        return { ok: true }
      }
      return { ok: false, message: 'Invalid response from server' }
    } catch (err) {
      setAuthError(err?.message || 'Login failed')
      return { ok: false, message: err?.message || 'Login failed' }
    } finally {
      setAuthLoading(false)
    }
  }

  const requestApplicantPasswordReset = async (email) => {
    if (!email) return { ok: false, message: 'Email is required' }
    try {
      const data = await apiRequest('/api/candidate/forgot-password', {
        method: 'POST',
        body: { email },
      })
      return { ok: true, data }
    } catch (err) {
      return { ok: false, message: err?.message || 'Failed to send OTP' }
    }
  }

  const verifyApplicantPasswordOtp = async ({ email, otp }) => {
    try {
      const data = await apiRequest('/api/candidate/forgot-password/verify-otp', {
        method: 'POST',
        body: { email, otp },
      })
      return { ok: true, data }
    } catch (err) {
      return { ok: false, message: err?.message || 'OTP verification failed' }
    }
  }

  const resetApplicantPassword = async ({ email, otp, newPassword, confirmPassword }) => {
    try {
      const data = await apiRequest('/api/candidate/reset-password', {
        method: 'POST',
        body: { email, otp, newPassword, confirmPassword },
      })
      return { ok: true, data }
    } catch (err) {
      return { ok: false, message: err?.message || 'Failed to reset password' }
    }
  }

  const signupApplicant = async ({ name, email, password }) => {
    setAuthError('')
    setAuthLoading(true)
    try {
      const data = await apiRequest('/api/candidate/signup', {
        method: 'POST',
        body: { name, email, password },
      })
      return { ok: true, data }
    } catch (err) {
      setAuthError(err?.message || 'Signup failed')
      return { ok: false, message: err?.message || 'Signup failed' }
    } finally {
      setAuthLoading(false)
    }
  }

  const verifyApplicantOTP = async ({ email, otp }) => {
    setAuthError('')
    setAuthLoading(true)
    try {
      const data = await apiRequest('/api/candidate/verify-otp', {
        method: 'POST',
        body: { email, otp },
      })
      return { ok: true, data }
    } catch (err) {
      console.error('Verify applicant OTP error:', err)
      const errorMessage = err?.message || err?.error || 'OTP verification failed'
      setAuthError(errorMessage)
      return { ok: false, message: errorMessage }
    } finally {
      setAuthLoading(false)
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

  const resendApplicantOTP = async ({ email, phone }) => {
    setAuthError('')
    setAuthLoading(true)
    try {
      const data = await apiRequest('/api/candidate/resend-otp', {
        method: 'POST',
        body: { email, phone },
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

  const saveApplicantProfile = async (profile) => {
    // Always save to localStorage first as backup - this ensures data is never lost
    const profileForStorage = { ...profile }
    // Don't store file object in localStorage
    if (profileForStorage.resumeFile) {
      delete profileForStorage.resumeFile
    }
    const nextLocal = { ...applicantProfile, ...profileForStorage }
    setApplicantProfile(nextLocal)
    writeJson(STORAGE_KEYS.applicantProfile, nextLocal)

    if (!applicantAuth.isLoggedIn) {
      return { ok: true, savedLocally: true }
    }

    if (!token) {
      return { ok: true, savedLocally: true, warning: 'Not authenticated. Saved locally only.' }
    }

    try {
      const resumeFile = profile.resumeFile
      const hasFile = resumeFile && resumeFile instanceof File

      let body
      if (hasFile) {
        const formData = new FormData()
        formData.append('resume', resumeFile)
        Object.keys(profile).forEach(key => {
          if (key === 'resumeFile') return
          const value = profile[key]
          if (Array.isArray(value) || (typeof value === 'object' && value !== null)) {
            formData.append(key, JSON.stringify(value))
          } else if (value !== null && value !== undefined) {
            formData.append(key, value)
          }
        })
        body = formData
      } else {
        // Use JSON for regular updates (without file)
        body = { ...profile }
        delete body.resumeFile // Remove file object from JSON
        // Ensure arrays are included even if empty
        if (!body.experiences) body.experiences = []
        if (!body.education) body.education = []
        if (!body.certifications) body.certifications = []
      }

      const response = await apiRequest('/api/candidate/profile', {
        method: 'POST',
        body: body,
        token
      })

      try {
        const updatedProfile = await apiRequest('/api/candidate/profile', {
          method: 'GET',
          token
        })
        if (updatedProfile) {
          // Merge updated profile with current profile data
          const next = { ...applicantProfile, ...profileForStorage, ...updatedProfile }
          // Don't store file object in localStorage
          if (next.resumeFile) {
            delete next.resumeFile
          }
          setApplicantProfile(next)
          writeJson(STORAGE_KEYS.applicantProfile, next)
          return { ok: true, updatedProfile, savedLocally: true }
        }
      } catch (fetchErr) {
        console.error('Failed to fetch updated profile:', fetchErr)
        // Still return success since we saved locally
        return { ok: true, savedLocally: true, warning: 'Saved locally but could not verify on server' }
      }
      
      // If we got here, the save succeeded but fetch failed
      return { ok: true, savedLocally: true }
    } catch (err) {
      const errorMessage = err?.message || err?.error || 'Failed to save profile to server'
      // Data is already saved locally, so return partial success
      // This ensures the user knows their data is safe even if server save fails
      return { 
        ok: true, 
        savedLocally: true, 
        warning: `Saved locally. Server sync failed: ${errorMessage}. Your data is safe and will sync when you log in.`,
        error: errorMessage
      }
    }
  }

  const markApplicantProfileCompleted = async (profileOverrides = null) => {
    const sourceProfile = profileOverrides ? { ...profileOverrides } : { ...applicantProfile }
    const profileWithCompleted = { ...sourceProfile, completed: true }
    // Never send raw File objects in this flow
    if (profileWithCompleted.resumeFile) {
      delete profileWithCompleted.resumeFile
    }
    if (applicantAuth.isLoggedIn) {
      try {
        await apiRequest('/api/candidate/profile', {
          method: 'POST',
          body: profileWithCompleted,
          token
        })
      } catch (err) {
        console.error('Mark profile completed error:', err)
      }
    }
    setApplicantProfile((p) => {
      const next = { ...p, ...profileWithCompleted }
      writeJson(STORAGE_KEYS.applicantProfile, next)
      return next
    })
    return { ok: true }
  }

  const applyToJobAsApplicant = async (jobId) => {
    if (!applicantAuth.isLoggedIn) return { ok: false, reason: 'not_logged_in' }
    if (!applicantProfile.completed) return { ok: false, reason: 'profile_incomplete' }
    const hasResume = !!applicantProfile.resumeFileName
    const hasEducation = Array.isArray(applicantProfile.education) && applicantProfile.education.some(ed => ed.degree && ed.institution)
    if (!hasResume || !hasEducation) {
      return { ok: false, reason: 'profile_requirements_missing' }
    }
    // Optimistic update: show "Applied" immediately
    const newEntry = { status: 'applied', shortlisted: false }
    setApplicantApplications((prev) => {
      const next = { ...prev, [jobId]: newEntry, [String(jobId)]: newEntry }
      writeJson(STORAGE_KEYS.applicantApplications, next)
      return next
    })
    try {
      await apiRequest('/api/applications', {
        method: 'POST',
        body: { jobId },
        token
      })
      // Sync applications list in background (no delay)
      fetchApplicantData()
      return { ok: true }
    } catch (err) {
      console.error('Apply error:', err)
      // Revert optimistic update on failure
      setApplicantApplications((prev) => {
        const next = { ...prev }
        delete next[jobId]
        delete next[String(jobId)]
        writeJson(STORAGE_KEYS.applicantApplications, next)
        return next
      })
      return { ok: false, message: err?.message || 'Failed to apply' }
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
    setApplicantAuth(defaultApplicantAuth)
    setApplicantProfile(defaultApplicantProfile)
    setApplicantApplications({})
    setApplicantSavedJobs({})
    setToken('')
    tokenService.clear()
    setUser(null)
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(STORAGE_KEYS.auth)
      window.localStorage.removeItem(STORAGE_KEYS.applicantAuth)
      window.localStorage.removeItem(STORAGE_KEYS.applicantProfile)
      window.localStorage.removeItem(STORAGE_KEYS.applicantApplications)
      window.localStorage.removeItem(STORAGE_KEYS.applicantSavedJobs)
      window.localStorage.removeItem(STORAGE_KEYS.user)
    }
  }

  logoutRef.current = logout

  useEffect(() => {
    const storedToken = tokenService.getToken()
    const role = decodeJwtRole(storedToken)

    if (!storedToken) {
      const hrAuth = readJson(STORAGE_KEYS.auth, defaultAuth)
      const appAuth = readJson(STORAGE_KEYS.applicantAuth, defaultApplicantAuth)
      if (hrAuth.isLoggedIn || appAuth.isLoggedIn) {
        logoutRef.current()
      }
      return
    }

    if (role === 'CANDIDATE') {
      clearOtherSessions('candidate')
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

  // Fetch jobs from backend. Always send token when available so HR sees only their jobs (backend filters by posted_by).
  const fetchJobs = async () => {
    setJobsLoading(true)
    setJobsError('')
    try {
      const authToken = token || tokenService.getToken()
      const data = await apiRequest('/api/jobs', { method: 'GET', token: authToken })
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
    // Clear any legacy locally stored jobs to avoid showing mock data
    try {
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(STORAGE_KEYS.jobs)
      }
    } catch {}
    fetchJobs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Refetch jobs when auth state changes (to get all jobs for HR)
  useEffect(() => {
    if (auth.isLoggedIn || applicantAuth.isLoggedIn) {
      fetchJobs()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isLoggedIn, applicantAuth.isLoggedIn])

  // Fetch applicant data when logged in as candidate with matching token role
  useEffect(() => {
    const authToken = token || tokenService.getToken()
    if (applicantAuth.isLoggedIn && token && decodeJwtRole(authToken) === 'CANDIDATE') {
      fetchApplicantData()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicantAuth.isLoggedIn, token])

  // Admin: add a job (best-effort). If backend supports it, create and refresh list.
  const addJob = async (job) => {
    try {
      if (!token) {
        console.error('No token available - user may not be logged in')
        return { success: false, error: 'You must be logged in to create a job. Please log in and try again.' }
      }
      
      const result = await apiRequest('/api/jobs', { method: 'POST', body: job, token })
      await fetchJobs()
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
      // Fallback to local update
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, enabled: isEnabled } : j)))
      return
    }
    try {
      await apiRequest(`/api/jobs/${jobId}/enabled`, {
        method: 'PATCH',
        body: { enabled: isEnabled },
        token
      })
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, enabled: isEnabled } : j)))
    } catch (err) {
      console.error('Set job enabled error:', err)
      // Fallback to local update
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, enabled: isEnabled } : j)))
    }
  }

  const updateJob = async (jobId, updates) => {
    if (!token) {
      // Fallback to local update
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, ...updates } : j)))
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
    fetchJobs,
    addJob,
    setJobEnabled,
    updateJob,
    auth,
    authLoading,
    authError,
    loginHR,
    applicantAuth,
    applicantProfile,
    applicantApplications,
    applicantSavedJobs,
    loginApplicant,
    requestApplicantPasswordReset,
    verifyApplicantPasswordOtp,
    resetApplicantPassword,
    signupApplicant,
    verifyApplicantOTP,
    resendApplicantOTP,
    signupHR,
    verifyHROTP,
    resendHROTP,
    requestHrPasswordReset,
    verifyHrPasswordOtp,
    resetHrPassword,
    changePasswordApplicant,
    changePasswordHr,
    saveApplicantProfile,
    markApplicantProfileCompleted,
    applyToJobAsApplicant,
    toggleSaveJob,
    getToken,
    logout,
    user,
    fetchApplicantData,
    fetchApplicationsForJob,
    fetchAllApplications,
    backendHealthy,
  }), [jobs, jobsLoading, jobsError, auth, authLoading, authError, applicantAuth, applicantProfile, applicantApplications, applicantSavedJobs, user, token, backendHealthy])

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}


