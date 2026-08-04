import React from 'react'
import { FiMoon, FiSun } from 'react-icons/fi'
import { useLocation } from 'react-router-dom'
import { useTheme } from '@/core/context/ThemeContext.jsx'
import { showThemeToggleOnPath } from '@/core/theme/themeConfig.js'

/**
 * Global dark / light toggle. Hidden on dark-only routes (see themeConfig).
 *
 * @param {{ className?: string, compact?: boolean, variant?: 'default' | 'org' | 'chrome' }} props
 * - org: Head HR Home / Refresh (`org-btn-ghost`)
 * - chrome: Navbar bordered control (same visual language as org ghost buttons)
 */
export default function ThemeToggle({ className = '', compact = false, variant = 'default' }) {
  const { theme, toggleTheme, isDark } = useTheme()
  const { pathname } = useLocation()

  if (!showThemeToggleOnPath(pathname)) return null

  const orgStyle = variant === 'org'
  const chromeStyle = variant === 'chrome' || (variant === 'default' && !compact)

  let baseClass = ''
  if (orgStyle) {
    baseClass = 'org-btn-ghost'
  } else if (chromeStyle) {
    baseClass = 'inline-flex items-center justify-center gap-2 h-9 px-3 rounded-xl text-sm font-medium border transition-colors'
  } else {
    baseClass = 'inline-flex items-center justify-center h-9 w-9 rounded-xl border transition-colors'
  }

  const showLabel = !compact

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Light mode' : 'Dark mode'}
      className={[baseClass, className].filter(Boolean).join(' ')}
    >
      {isDark ? <FiSun className="w-4 h-4 shrink-0" /> : <FiMoon className="w-4 h-4 shrink-0" />}
      {showLabel && (
        <span className="text-sm font-medium tracking-wide">
          {theme === 'dark' ? 'Light' : 'Dark'}
        </span>
      )}
    </button>
  )
}
