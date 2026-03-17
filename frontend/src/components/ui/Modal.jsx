import React, { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { FiX } from 'react-icons/fi'

export default function Modal({
  open,
  onClose,
  title,
  children,
  size = 'md',
  showClose = true,
}) {
  useEffect(() => {
    if (!open) return
    const onEscape = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [open, onClose])

  const sizeClasses = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  }

  const content = (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute inset-0 bg-slate-900/50 dark:bg-black/60 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 10 }}
            transition={{ type: 'tween', duration: 0.2 }}
            role="dialog"
            aria-modal="true"
            aria-labelledby={title ? 'modal-title' : undefined}
            className={`relative w-full ${sizeClasses[size]} max-h-[90vh] flex flex-col rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-premium overflow-hidden`}
            onClick={(e) => e.stopPropagation()}
          >
            {(title || showClose) && (
              <div className="flex items-center justify-between flex-shrink-0 px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                {title && (
                  <h2 id="modal-title" className="text-lg font-semibold text-slate-900 dark:text-white">
                    {title}
                  </h2>
                )}
                {showClose && (
                  <button
                    type="button"
                    onClick={onClose}
                    className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors ml-auto"
                    aria-label="Close"
                  >
                    <FiX className="w-5 h-5" />
                  </button>
                )}
              </div>
            )}
            <div className="flex-1 overflow-y-auto px-6 py-5">
              {children}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )

  return typeof document !== 'undefined' ? createPortal(content, document.body) : null
}
