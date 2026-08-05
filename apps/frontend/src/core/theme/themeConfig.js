/**
 * Centralized UI theme config (HCIP).
 *
 * Single source of truth for Dark/Light mode. Anyone pulling this branch
 * should use these helpers + ThemeProvider — do not hardcode theme keys,
 * landing exceptions, or surfaceTheme mapping elsewhere.
 *
 * CSS tokens: `apps/frontend/src/styles/index.css` (`:root` + `html[data-theme="light"]`).
 * Runtime: `ThemeProvider` / `useTheme` in `ThemeContext.jsx`.
 * FOUC script: `apps/frontend/public/theme-init.js` (STORAGE_KEY must match).
 */

/** @typedef {'dark' | 'light'} ThemeMode */
/** @typedef {'enterprise' | 'default'} SurfaceTheme */

export const THEME_STORAGE_KEY = 'hcip-theme'

/** Default when nothing is stored (product default = dark enterprise). */
export const DEFAULT_THEME = /** @type {ThemeMode} */ ('dark')

export const THEME_MODES = /** @type {const} */ (['dark', 'light'])

/**
 * Paths that always render dark cinematic chrome and must NOT show the theme toggle.
 * Preference may still be light globally; these routes ignore it for presentation.
 */
export const DARK_ONLY_PATH_PREFIXES = []

export const DARK_ONLY_EXACT_PATHS = ['/']

/**
 * Map global mode → component `theme` prop (JobCard, FilterBar, Settings, match UI).
 * dark → enterprise glass; light → default/light surfaces.
 */
export function resolveSurfaceTheme(theme) {
  return theme === 'light' ? 'default' : 'enterprise'
}

export function isThemeMode(value) {
  return value === 'dark' || value === 'light'
}

export function readStoredTheme() {
  if (typeof window === 'undefined') return DEFAULT_THEME
  try {
    const raw = window.localStorage.getItem(THEME_STORAGE_KEY)
    if (isThemeMode(raw)) return raw
  } catch {
    /* ignore */
  }
  return DEFAULT_THEME
}

export function persistTheme(theme) {
  if (!isThemeMode(theme) || typeof window === 'undefined') return
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    /* ignore */
  }
}

/** Apply mode to <html> for CSS (`data-theme`) and Tailwind (`dark` class). */
export function applyThemeToDocument(theme) {
  if (typeof document === 'undefined' || !isThemeMode(theme)) return
  const root = document.documentElement
  root.setAttribute('data-theme', theme)
  root.classList.toggle('dark', theme === 'dark')
  root.classList.toggle('light', theme === 'light')
}

export function isDarkOnlyPath(pathname) {
  if (!pathname) return false
  if (DARK_ONLY_EXACT_PATHS.includes(pathname)) return true
  return DARK_ONLY_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )
}

/** Navbar / chrome may show ThemeToggle except on dark-only routes. */
export function showThemeToggleOnPath(pathname) {
  return !isDarkOnlyPath(pathname)
}

export function oppositeTheme(theme) {
  return theme === 'dark' ? 'light' : 'dark'
}
