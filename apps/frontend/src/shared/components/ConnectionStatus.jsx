import React, { useState, useEffect } from 'react'
import { useApp } from '@/core/context/AppContext.jsx'

export default function ConnectionStatus() {
  const { backendHealthy } = useApp()
  const [showWarning, setShowWarning] = useState(false)
  
  useEffect(() => {
    if (!backendHealthy) {
      // Longer delay: bulk parsing can stall the probe briefly without being down
      const timer = setTimeout(() => {
        setShowWarning(true)
      }, 8000)
      
      return () => clearTimeout(timer)
    } else {
      // Hide immediately when healthy
      setShowWarning(false)
    }
  }, [backendHealthy])
  
  // Don't show anything if backend is healthy or not enough time has passed
  if (!showWarning) {
    return null
  }
  
  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-amber-600/95 backdrop-blur-sm text-white px-4 py-2 shadow-lg animate-in slide-in-from-top duration-300">
      <div className="max-w-7xl mx-auto flex items-center justify-center gap-2 text-sm">
        <svg className="animate-pulse flex-shrink-0" width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span className="font-medium">Connecting to server...</span>
        <span className="text-xs opacity-90">(Backend not responding — keep one node start.js running)</span>
      </div>
    </div>
  )
}

