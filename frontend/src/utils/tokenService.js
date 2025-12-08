// Token service abstracts token storage and retrieval
// SECURITY NOTE: For production, prefer secure HttpOnly cookies set by the backend
// (SameSite=Lax, Secure) and do NOT persist JWTs in JS-accessible storage. This
// implementation uses localStorage to stay backward compatible with current logic.
// When migrating to cookies, disable persistence here and rely on fetch credentials.

const STORAGE_KEY = 'jwtToken'
let inMemoryToken = ''

function readFromStorage() {
  if (typeof window === 'undefined') return ''
  try {
    return window.localStorage.getItem(STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

function writeToStorage(value) {
  if (typeof window === 'undefined') return
  try {
    if (value) window.localStorage.setItem(STORAGE_KEY, value)
    else window.localStorage.removeItem(STORAGE_KEY)
  } catch {}
}

// Initialize cache from storage on first import/use
inMemoryToken = readFromStorage()

export const tokenService = {
  getToken() {
    // Prioritize in-memory for performance; sync from storage if empty
    if (!inMemoryToken) inMemoryToken = readFromStorage()
    return inMemoryToken
  },
  setToken(token) {
    inMemoryToken = token || ''
    writeToStorage(inMemoryToken)
  },
  clear() {
    inMemoryToken = ''
    writeToStorage('')
  }
}
