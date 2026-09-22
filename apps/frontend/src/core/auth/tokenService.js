// Token service abstracts token storage and retrieval.
//
// Web client: the access/refresh JWTs live in httpOnly cookies the backend
// sets on login/refresh/logout (see apps/backend/app/core/cookies.py) — this
// module keeps only an in-memory cache for the current tab so the many call
// sites that read tokenService.getToken() to attach a Bearer header keep
// working, but localStorage is never written, so an XSS can no longer read
// the token out of it.
//
// Electron client: its production build loads via file:// and calls the API
// cross-origin, so it can't rely on the httpOnly cookie (SameSite blocks it).
// It keeps using the Authorization header, backed by Electron's own
// safeStorage-encrypted storage (via the `window.electron.secureStorage` IPC
// bridge already exposed in apps/desktop/preload.js) instead of localStorage.

const STORAGE_KEY = 'jwtToken'
const REFRESH_STORAGE_KEY = 'refreshToken'
let inMemoryToken = ''
let inMemoryRefreshToken = ''

const isElectron = typeof window !== 'undefined' && !!window.electron?.secureStorage

// One-time migration: earlier versions of this app persisted tokens to
// localStorage. Purge any leftovers on the web path so a stale copy doesn't
// sit there defeating the point of this change.
function purgeLegacyWebStorage() {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(STORAGE_KEY)
    window.localStorage.removeItem(REFRESH_STORAGE_KEY)
  } catch {}
}

// Call once at app startup (see AppContext.jsx) before any API call fires:
// hydrates the in-memory cache from Electron's secure storage, or purges
// legacy localStorage tokens on the web.
async function initTokenService() {
  if (isElectron) {
    try {
      inMemoryToken = (await window.electron.secureStorage.get(STORAGE_KEY)) || ''
      inMemoryRefreshToken = (await window.electron.secureStorage.get(REFRESH_STORAGE_KEY)) || ''
    } catch {
      inMemoryToken = ''
      inMemoryRefreshToken = ''
    }
    return
  }
  purgeLegacyWebStorage()
}

export const tokenService = {
  getToken() {
    return inMemoryToken
  },
  setToken(token) {
    inMemoryToken = token || ''
    if (isElectron) {
      window.electron.secureStorage.set(STORAGE_KEY, inMemoryToken).catch(() => {})
    }
  },
  getRefreshToken() {
    return inMemoryRefreshToken
  },
  setRefreshToken(token) {
    inMemoryRefreshToken = token || ''
    if (isElectron) {
      window.electron.secureStorage.set(REFRESH_STORAGE_KEY, inMemoryRefreshToken).catch(() => {})
    }
  },
  clear() {
    inMemoryToken = ''
    inMemoryRefreshToken = ''
    if (isElectron) {
      window.electron.secureStorage.clear().catch(() => {})
    } else {
      purgeLegacyWebStorage()
    }
  },
  initTokenService,
}
