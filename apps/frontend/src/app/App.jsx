import React, { Suspense, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { AppProvider, useApp } from '@/core/context/AppContext.jsx'
import Navbar from '@/shared/components/Navbar.jsx'
import ErrorBoundary from '@/shared/components/ErrorBoundary.jsx'
import { ToastProvider, useToast } from '@/shared/components/Toast.jsx'
import ConnectionStatus from '@/shared/components/ConnectionStatus.jsx'
import AppRoutes from '@/routes/index.jsx'

export default function App() {
  const location = useLocation()
  const isHeadHrRoute = location.pathname.startsWith('/head-hr')
  const isCeoRoute = location.pathname.startsWith('/ceo')
  const isLandingRoute = location.pathname === '/'
  const isAuthRoute =
    location.pathname.startsWith('/login') ||
    location.pathname.startsWith('/signup') ||
    location.pathname.startsWith('/forgot-password')
  const hideChrome = isHeadHrRoute || isCeoRoute || isLandingRoute
  const hideFooter = hideChrome || isAuthRoute
  const shellClass = hideChrome && (isHeadHrRoute || isCeoRoute)
    ? 'bg-[#0B1118] text-[#F5F7FA] h-[100dvh] max-h-[100dvh] overflow-hidden'
    : isLandingRoute
      ? 'bg-[#050a14] text-white'
      : isAuthRoute
        ? 'bg-[#050a14] text-[#F5F7FA]'
        : 'bg-slate-50 text-slate-900'

  return (
    <AppProvider>
      <ToastProvider>
        <ErrorBoundary>
          <ConnectionStatus />
          <div className={`min-h-screen flex flex-col ${shellClass}`}>
            {!hideChrome && <Navbar />}
            <ErrorToasts />
            <main className={
              isHeadHrRoute || isCeoRoute
                ? 'flex-1 flex flex-col min-h-0 overflow-hidden'
                : 'flex-1'
            }>
              <Suspense fallback={<div className={`max-w-7xl mx-auto px-6 py-10 ${hideChrome && (isHeadHrRoute || isCeoRoute) || isAuthRoute ? '' : ''}`}><div className={`h-10 w-48 rounded-xl animate-pulse ${hideChrome && (isHeadHrRoute || isCeoRoute) || isAuthRoute ? 'bg-white/10' : 'bg-slate-200'}`} /></div>}>
                <AppRoutes />
              </Suspense>
            </main>
            {!hideFooter && (
              <footer className="py-8 text-center text-sm text-slate-500 border-t border-slate-200">
                © {new Date().getFullYear()} HR Intelligence
              </footer>
            )}
          </div>
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
