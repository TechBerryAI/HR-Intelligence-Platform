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
  const hideChrome = isHeadHrRoute || isCeoRoute || isLandingRoute

  return (
    <AppProvider>
      <ToastProvider>
        <ErrorBoundary>
          <ConnectionStatus />
          <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
            {!hideChrome && <Navbar />}
            <ErrorToasts />
            <main className={hideChrome ? 'flex-1 flex flex-col min-h-screen' : 'flex-1'}>
              <Suspense fallback={<div className="max-w-7xl mx-auto px-6 py-10"><div className="h-10 w-48 rounded-xl bg-slate-200 animate-pulse" /></div>}>
                <AppRoutes />
              </Suspense>
            </main>
            {!hideChrome && (
              <footer className="py-8 text-center text-sm text-slate-500 border-t border-slate-200">
                © {new Date().getFullYear()} Job Portal
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
