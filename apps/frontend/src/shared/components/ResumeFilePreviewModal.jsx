import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { FiX, FiFile } from 'react-icons/fi'
import ResumePdfPages from './ResumePdfPages.jsx'

function previewKind(file) {
  const name = String(file?.name || '').toLowerCase()
  const type = String(file?.type || '').toLowerCase()
  if (type === 'application/pdf' || name.endsWith('.pdf')) return 'pdf'
  if (type.startsWith('image/') || /\.(png|jpe?g|webp|gif)$/.test(name)) return 'image'
  return 'other'
}

/**
 * Full-page overlay so a just-uploaded resume (PDF/image) can be read in place.
 * Must sit above ApplyJobModal (z-100).
 */
export default function ResumeFilePreviewModal({ open, file, fileName, onClose }) {
  const kind = previewKind(file)
  const title = fileName || file?.name || 'Resume'

  const [objectUrl, setObjectUrl] = useState('')

  useEffect(() => {
    if (!open || !file) {
      setObjectUrl('')
      return undefined
    }
    const url = URL.createObjectURL(file)
    setObjectUrl(url)
    return () => {
      URL.revokeObjectURL(url)
      setObjectUrl('')
    }
  }, [open, file])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])

  if (typeof document === 'undefined') return null

  const content = (
    <AnimatePresence>
      {open && file && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-3 sm:p-6">
          <motion.button
            type="button"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm"
            aria-label="Close resume preview"
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="resume-preview-title"
            initial={{ opacity: 0, scale: 0.97, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 12 }}
            transition={{ type: 'tween', duration: 0.18 }}
            className="relative flex h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-[var(--ei-border-primary)] bg-[var(--ei-bg-secondary)] shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-[var(--ei-border-primary)] px-4 py-3">
              <div className="flex min-w-0 items-center gap-2">
                <FiFile className="h-4 w-4 shrink-0 text-[var(--ei-text-muted)]" />
                <h2
                  id="resume-preview-title"
                  className="truncate text-sm font-semibold text-[var(--ei-text-primary)]"
                  title={title}
                >
                  {title}
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="shrink-0 rounded-lg p-2 text-[var(--ei-text-muted)] hover:bg-[var(--ei-surface-hover)] hover:text-[var(--ei-text-primary)]"
                aria-label="Close resume preview"
              >
                <FiX className="h-5 w-5" />
              </button>
            </div>
            <div className="min-h-0 flex-1 bg-slate-950/40">
              {kind === 'pdf' ? (
                <ResumePdfPages file={file} />
              ) : !objectUrl ? (
                <div className="flex h-full items-center justify-center text-sm text-[var(--ei-text-muted)]">
                  Loading preview…
                </div>
              ) : kind === 'image' ? (
                <div className="flex h-full items-center justify-center overflow-auto p-4">
                  <img
                    src={objectUrl}
                    alt={title}
                    className="max-h-full max-w-full rounded-md object-contain shadow-lg"
                  />
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
                  <p className="text-sm text-[var(--ei-text-secondary)]">
                    This file type cannot be previewed in the browser.
                  </p>
                  <a
                    href={objectUrl}
                    download={title}
                    className="rounded-xl border border-[var(--ei-border-primary)] px-4 py-2 text-sm font-medium text-[var(--ei-text-primary)] hover:bg-[var(--ei-surface-hover)]"
                  >
                    Download to view
                  </a>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )

  return createPortal(content, document.body)
}
