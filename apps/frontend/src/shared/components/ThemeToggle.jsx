import React from 'react'
import { FiMoon, FiSun } from 'react-icons/fi'
import { useTheme } from '@/core/context/ThemeContext.jsx'

/**
 * Global dark / light toggle. Works in Navbar, LandingNav, and org panels.
 * @param {{ className?: string, compact?: boolean }} props
 */
export default function ThemeToggle({ className = '', compact = false }) {
  const { theme, toggleTheme, isDark } = useTheme()

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Light mode' : 'Dark mode'}
      className={[
        'inline-flex items-center justify-center gap-1.5 rounded-full transition-colors',
        compact ? 'h-9 w-9' : 'h-9 px-2.5 sm:px-3',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {isDark ? <FiSun className="h-4 w-4" /> : <FiMoon className="h-4 w-4" />}
      {!compact && (
        <span className="hidden sm:inline text-xs font-medium tracking-wide">
          {theme === 'dark' ? 'Light' : 'Dark'}
        </span>
      )}
    </button>
  )
}
