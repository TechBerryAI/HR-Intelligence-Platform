import React, { Suspense, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { AppProvider, useApp } from '@/core/context/AppContext.jsx'
import { useTheme } from '@/core/context/ThemeContext.jsx'
import { isDarkOnlyPath } from '@/core/theme/themeConfig.js'
import Navbar from '@/shared/components/Navbar.jsx'
import ErrorBoundary from '@/shared/components/ErrorBoundary.jsx'
import { ToastProvider, useToast } from '@/shared/components/Toast.jsx'
import ConnectionStatus from '@/shared/components/ConnectionStatus.jsx'
import AppRoutes from '@/routes/index.jsx'

function isEnterpriseAppPath(pathname) {
  return (
    pathname.startsWith('/jobs') ||
    pathname.startsWith('/dashboard') ||
    pathname.startsWith('/candidates') ||
    pathname.startsWith('/admin') ||
    pathname.startsWith('/settings') ||
    pathname.startsWith('/integrations')
  )
}

function AppShell({ children }) {
  const location = useLocation()
  const { isDark } = useTheme()
  const isHeadHrRoute = location.pathname.startsWith('/head-hr')
  const isCeoRoute = location.pathname.startsWith('/ceo')
  const isLandingRoute = location.pathname === '/'
  const isAuthRoute =
    location.pathname.startsWith('/login') ||
    location.pathname.startsWith('/signup') ||
    location.pathname.startsWith('/forgot-password')
  const isStaffAppRoute = isEnterpriseAppPath(location.pathname)
  const hideChrome = isHeadHrRoute || isCeoRoute || isLandingRoute
  const hideFooter = hideChrome || isAuthRoute || isStaffAppRoute

  let shellClass = 'bg-slate-50 text-slate-900'
  if (hideChrome && (isHeadHrRoute || isCeoRoute)) {
    shellClass = isDark
      ? 'bg-[var(--ei-bg-primary)] text-[var(--ei-text-primary)] h-[100dvh] max-h-[100dvh] overflow-hidden'
      : 'bg-[var(--ei-bg-primary)] text-[var(--ei-text-primary)] h-[100dvh] max-h-[100dvh] overflow-hidden'
  } else if (isLandingRoute || isDarkOnlyPath(location.pathname)) {
    // Dark-only routes (see themeConfig.DARK_ONLY_*) — ignore global light preference
    shellClass = 'bg-[#050a14] text-white landing-shell'
  } else if (isAuthRoute) {
    shellClass = isDark
      ? 'bg-[#050a14] text-[var(--ei-text-primary)]'
      : 'bg-slate-100 text-slate-900'
  } else if (isStaffAppRoute) {
    shellClass = 'org-shell text-[var(--ei-text-primary)] min-h-screen'
  } else {
    shellClass = isDark
      ? 'org-shell text-[var(--ei-text-primary)] min-h-screen'
      : 'bg-slate-50 text-slate-900'
  }

  return (
    <div className={`min-h-screen flex flex-col ${shellClass}`} data-app-theme={isDark ? 'dark' : 'light'}>
      {!hideChrome && <Navbar />}
      <ErrorToasts />
      <main
        className={
          isHeadHrRoute || isCeoRoute
            ? 'flex-1 flex flex-col min-h-0 overflow-hidden'
            : 'flex-1'
        }
      >
        {children}
      </main>
      {!hideFooter && (
        <footer
          className={
            isDark
              ? 'py-8 text-center text-sm text-[var(--ei-text-muted)] border-t border-[var(--ei-border-primary)]'
              : 'py-8 text-center text-sm text-slate-500 border-t border-slate-200'
          }
        >
          © {new Date().getFullYear()} HR Intelligence
        </footer>
      )}
    </div>
  )
}

export default function App() {
  const location = useLocation()
  const isHeadHrRoute = location.pathname.startsWith('/head-hr')
  const isCeoRoute = location.pathname.startsWith('/ceo')
  const isAuthRoute =
    location.pathname.startsWith('/login') ||
    location.pathname.startsWith('/signup') ||
    location.pathname.startsWith('/forgot-password')
  const isStaffAppRoute = isEnterpriseAppPath(location.pathname)
  const hideChrome =
    isHeadHrRoute || isCeoRoute || location.pathname === '/'

  return (
    <AppProvider>
      <ToastProvider>
        <ErrorBoundary>
          <ConnectionStatus />
          <AppShell>
            <Suspense
              fallback={
                <div className="max-w-7xl mx-auto px-6 py-10">
                  <div
                    className={`h-10 w-48 rounded-xl animate-pulse ${
                      hideChrome || isAuthRoute || isStaffAppRoute
                        ? 'bg-white/10 dark:bg-white/10 bg-slate-200'
                        : 'bg-slate-200'
                    }`}
                  />
                </div>
              }
            >
              <AppRoutes />
            </Suspense>
          </AppShell>
        </ErrorBoundary>
      </ToastProvider>
    </AppProvider>
  )
}

function ErrorToasts() {
  const { authError } = useApp()
  const toast = useToast()
  useEffect(() => {
    if (authError) toast.push(authError, { type: 'error' })
  }, [authError])
  return null
}
