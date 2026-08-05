import React from 'react'
import { Moon, Sun } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { useTheme } from '@/core/context/ThemeContext.jsx'
import { showThemeToggleOnPath } from '@/core/theme/themeConfig.js'

/**
 * Global dark / light toggle. Hidden on dark-only routes (see themeConfig).
 *
 * @param {{ className?: string, compact?: boolean, variant?: 'default' | 'org' | 'chrome' }} props
 * - org: identical to Head HR Home / Refresh (`org-btn-ghost` + lucide 16px / stroke 2)
 * - chrome: Navbar bordered control
 */
export default function ThemeToggle({ className = '', compact = false, variant = 'default' }) {
  const { theme, toggleTheme, isDark } = useTheme()
  const { pathname } = useLocation()

  if (!showThemeToggleOnPath(pathname)) return null

  const label = isDark ? 'Light' : 'Dark'
  const Icon = isDark ? Sun : Moon

  if (variant === 'org') {
    return (
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        title={isDark ? 'Light mode' : 'Dark mode'}
        className={['org-btn-ghost', className].filter(Boolean).join(' ')}
      >
        <Icon className="w-4 h-4" strokeWidth={2} />
        {label}
      </button>
    )
  }

  const chromeStyle = variant === 'chrome' || (variant === 'default' && !compact)
  const baseClass = chromeStyle
    ? 'inline-flex items-center justify-center gap-2 h-9 px-3 rounded-xl text-sm font-medium border transition-colors'
    : 'inline-flex items-center justify-center h-9 w-9 rounded-xl border transition-colors'

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Light mode' : 'Dark mode'}
      className={[baseClass, className].filter(Boolean).join(' ')}
    >
      <Icon className="w-4 h-4 shrink-0" strokeWidth={2} />
      {!compact && <span>{label}</span>}
    </button>
  )
}
