// Token service abstracts token storage and retrieval
// SECURITY NOTE: For production, prefer secure HttpOnly cookies set by the backend
// (SameSite=Lax, Secure) and do NOT persist JWTs in JS-accessible storage. This
// implementation uses localStorage to stay backward compatible with current logic.
// When migrating to cookies, disable persistence here and rely on fetch credentials.

const STORAGE_KEY = 'jwtToken'
const REFRESH_STORAGE_KEY = 'refreshToken'
let inMemoryToken = ''
let inMemoryRefreshToken = ''

function readFromStorage(key, fallback = '') {
  if (typeof window === 'undefined') return fallback
  try {
    return window.localStorage.getItem(key) || fallback
  } catch {
    return fallback
  }
}

function writeToStorage(key, value) {
  if (typeof window === 'undefined') return
  try {
    if (value) window.localStorage.setItem(key, value)
    else window.localStorage.removeItem(key)
  } catch {}
}

function syncFromStorage() {
  inMemoryToken = readFromStorage(STORAGE_KEY, '')
  inMemoryRefreshToken = readFromStorage(REFRESH_STORAGE_KEY, '')
}

// Initialize cache from storage on first import/use
syncFromStorage()

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.storageArea !== window.localStorage) return
    if (event.key === STORAGE_KEY || event.key === REFRESH_STORAGE_KEY || event.key === null) {
      syncFromStorage()
    }
  })
}

export const tokenService = {
  getToken() {
    if (typeof window !== 'undefined' && !inMemoryToken) {
      inMemoryToken = readFromStorage(STORAGE_KEY, '')
    }
    return inMemoryToken
  },
  setToken(token) {
    inMemoryToken = token || ''
    writeToStorage(STORAGE_KEY, inMemoryToken)
  },
  getRefreshToken() {
    if (typeof window !== 'undefined' && !inMemoryRefreshToken) {
      inMemoryRefreshToken = readFromStorage(REFRESH_STORAGE_KEY, '')
    }
    return inMemoryRefreshToken
  },
  setRefreshToken(token) {
    inMemoryRefreshToken = token || ''
    writeToStorage(REFRESH_STORAGE_KEY, inMemoryRefreshToken)
  },
  clear() {
    inMemoryToken = ''
    inMemoryRefreshToken = ''
    writeToStorage(STORAGE_KEY, '')
    writeToStorage(REFRESH_STORAGE_KEY, '')
  },
  syncFromStorage,
}
