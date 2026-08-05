/**
 * Theme system barrel — import from here in app code.
 * @example
 * import { useTheme, ThemeProvider, showThemeToggleOnPath } from '@/core/theme'
 */
export {
  THEME_STORAGE_KEY,
  DEFAULT_THEME,
  THEME_MODES,
  DARK_ONLY_EXACT_PATHS,
  DARK_ONLY_PATH_PREFIXES,
  resolveSurfaceTheme,
  isThemeMode,
  readStoredTheme,
  persistTheme,
  applyThemeToDocument,
  isDarkOnlyPath,
  showThemeToggleOnPath,
  oppositeTheme,
} from './themeConfig.js'

export { ThemeProvider, useTheme } from '@/core/context/ThemeContext.jsx'
