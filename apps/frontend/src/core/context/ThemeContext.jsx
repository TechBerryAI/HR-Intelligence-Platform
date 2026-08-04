import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  applyThemeToDocument,
  oppositeTheme,
  persistTheme,
  readStoredTheme,
  resolveSurfaceTheme,
  isThemeMode,
} from '@/core/theme/themeConfig.js'

const ThemeContext = createContext(null)

/**
 * App-wide theme. Mount once in `main.jsx`.
 * Consumers: `useTheme()` — do not add parallel theme state.
 */
export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => readStoredTheme())

  useEffect(() => {
    applyThemeToDocument(theme)
    persistTheme(theme)
  }, [theme])

  const setTheme = useCallback((next) => {
    if (!isThemeMode(next)) return
    setThemeState(next)
  }, [])

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => oppositeTheme(prev))
  }, [])

  const value = useMemo(
    () => ({
      theme,
      isDark: theme === 'dark',
      setTheme,
      toggleTheme,
      /** JobCard / FilterBar / Settings / match panels */
      surfaceTheme: resolveSurfaceTheme(theme),
    }),
    [theme, setTheme, toggleTheme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
