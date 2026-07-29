import React, { createContext, useContext, useCallback, useState, useMemo } from 'react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const remove = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])
  const push = useCallback((message, { type = 'info', duration = 3000 } = {}) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t, { id, message, type }])
    if (duration > 0) setTimeout(() => remove(id), duration)
    return id
  }, [remove])

  const success = useCallback((message, opts) => push(message, { ...opts, type: 'success' }), [push])
  const error = useCallback((message, opts) => push(message, { ...opts, type: 'error' }), [push])

  const value = useMemo(() => ({ push, remove, success, error }), [push, remove, success, error])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed z-50 bottom-4 right-4 space-y-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-4 py-3 rounded-xl shadow-md border text-sm font-medium ${
              t.type === 'error'
                ? 'bg-red-50 border-red-200 text-red-800'
                : t.type === 'success'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-white border-slate-200 text-slate-900'
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
