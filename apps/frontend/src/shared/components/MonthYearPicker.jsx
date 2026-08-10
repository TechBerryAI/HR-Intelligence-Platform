import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

export default function MonthYearPicker({
  value,
  onChange,
  placeholder = 'Select month',
  minYear = 1000,
  maxYear = new Date().getFullYear() + 10,
  className = '',
}) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  // Normalize value to YYYY-MM (year-only e.g. "2025" -> "2025-01" so month is never undefined)
  const normalizedValue = (() => {
    if (!value || typeof value !== 'string') return value || ''
    const v = value.trim()
    if (/^\d{4}-\d{2}$/.test(v)) return v
    if (/^\d{4}$/.test(v)) return `${v}-01`
    return v
  })()

  const [year, setYear] = useState(() => {
    if (normalizedValue && /^\d{4}-\d{2}$/.test(normalizedValue)) return parseInt(normalizedValue.slice(0, 4), 10)
    return new Date().getFullYear()
  })
  const [month, setMonth] = useState(() => {
    if (normalizedValue && /^\d{4}-\d{2}$/.test(normalizedValue)) return parseInt(normalizedValue.slice(5, 7), 10)
    return new Date().getMonth() + 1
  })

  const containerRef = useRef(null)
  const dropdownRef = useRef(null)

  // Position dropdown below trigger (viewport coords for position: fixed)
  useEffect(() => {
    if (!open || !containerRef.current) return
    const el = containerRef.current
    const rect = el.getBoundingClientRect()
    setPosition({ top: rect.bottom + 4, left: rect.left })
  }, [open])

  useEffect(() => {
    if (!open) return
    const onScrollOrResize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        setPosition({ top: rect.bottom + 4, left: rect.left })
      }
    }
    window.addEventListener('scroll', onScrollOrResize, true)
    window.addEventListener('resize', onScrollOrResize)
    return () => {
      window.removeEventListener('scroll', onScrollOrResize, true)
      window.removeEventListener('resize', onScrollOrResize)
    }
  }, [open])

  useEffect(() => {
    const onClick = (e) => {
      if (!containerRef.current || !dropdownRef.current) return
      if (!containerRef.current.contains(e.target) && !dropdownRef.current.contains(e.target)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  useEffect(() => {
    if (normalizedValue && /^\d{4}-\d{2}$/.test(normalizedValue)) {
      const vYear = parseInt(normalizedValue.slice(0, 4), 10)
      const vMonth = parseInt(normalizedValue.slice(5, 7), 10)
      if (vYear !== year) setYear(vYear)
      if (vMonth !== month) setMonth(vMonth)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, normalizedValue])

  const display = useMemo(() => {
    if (!normalizedValue) return ''
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    const mm = parseInt(normalizedValue.slice(5, 7), 10)
    const yy = normalizedValue.slice(0, 4)
    if (Number.isNaN(mm) || mm < 1 || mm > 12) return yy || ''
    return `${months[mm - 1]} ${yy}`
  }, [normalizedValue])

  const years = useMemo(() => {
    const list = []
    for (let y = maxYear; y >= minYear; y--) list.push(y)
    return list
  }, [minYear, maxYear])

  const commit = (y, m) => {
    const mm = String(m).padStart(2, '0')
    const next = `${y}-${mm}`
    onChange?.(next)
    setOpen(false)
  }

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        type="button"
        className="premium-input w-full text-left flex items-center justify-between gap-2 cursor-pointer"
        onClick={() => setOpen((o) => !o)}
      >
        <span className={display ? 'text-[var(--ei-text-primary)]' : 'text-[var(--ei-text-placeholder)]'}>{display || placeholder}</span>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-[var(--ei-text-muted)] shrink-0">
          <path d="M6.75 3A.75.75 0 0 1 7.5 2.25h.75V3.75a.75.75 0 0 1-1.5 0V2.25H6.75zM15 2.25h.75V3.75a.75.75 0 0 1-1.5 0V2.25H15z" />
          <path fillRule="evenodd" d="M4.5 6.75A2.25 2.25 0 0 1 6.75 4.5h10.5A2.25 2.25 0 0 1 19.5 6.75v10.5A2.25 2.25 0 0 1 17.25 19.5H6.75A2.25 2.25 0 0 1 4.5 17.25V6.75zm2.25.75a.75.75 0 0 0-.75.75v8.25c0 .414.336.75.75.75h10.5a.75.75 0 0 0 .75-.75V8.25a.75.75 0 0 0-.75-.75H6.75z" clipRule="evenodd" />
        </svg>
      </button>

      {open &&
        typeof document !== 'undefined' &&
        createPortal(
          <div
            ref={dropdownRef}
            className="fixed w-72 rounded-xl border border-[var(--ei-border-primary)] bg-[var(--ei-bg-secondary)] p-3 shadow-xl z-[9999]"
            style={{ top: position.top, left: position.left }}
          >
            <div className="flex items-center justify-between gap-2 mb-3">
              <button
                type="button"
                className="px-2 py-1 text-sm rounded-lg border border-[var(--ei-border-primary)] bg-[var(--ei-surface-input)] text-[var(--ei-text-primary)] hover:bg-[var(--ei-surface-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => setYear((y) => Math.max(minYear, y - 1))}
                disabled={year <= minYear}
              >
                ◀
              </button>
              <select
                className="bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] rounded-lg px-2 py-1 text-sm text-[var(--ei-text-primary)]"
                value={year}
                onChange={(e) => {
                  const newYear = parseInt(e.target.value, 10)
                  if (newYear >= minYear && newYear <= maxYear) {
                    setYear(newYear)
                  }
                }}
              >
                {years.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              <button
                type="button"
                className="px-2 py-1 text-sm rounded-lg border border-[var(--ei-border-primary)] bg-[var(--ei-surface-input)] text-[var(--ei-text-primary)] hover:bg-[var(--ei-surface-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => setYear((y) => Math.min(maxYear, y + 1))}
                disabled={year >= maxYear}
              >
                ▶
              </button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {[1,2,3,4,5,6,7,8,9,10,11,12].map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => commit(year, m)}
                  className={`px-3 py-2 rounded-lg border text-sm ${m === month && year === parseInt((normalizedValue||'').slice(0,4)||'0',10) ? 'border-[var(--ei-border-focus)] bg-[var(--ei-tone-info-bg)] text-[var(--ei-text-primary)] font-medium' : 'border-[var(--ei-border-primary)] bg-[var(--ei-surface-input)] text-[var(--ei-text-secondary)] hover:bg-[var(--ei-surface-hover)]'}`}
                >
                  {new Date(2000, m - 1).toLocaleString('en-US', { month: 'short' })}
                </button>
              ))}
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <button type="button" className="text-xs text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)]" onClick={() => { onChange?.(''); setOpen(false) }}>Clear</button>
              <button type="button" className="text-xs text-[var(--ei-btn-primary-text)] bg-[var(--ei-btn-primary-from)] hover:brightness-105 rounded-lg px-2.5 py-1" onClick={() => setOpen(false)}>Done</button>
            </div>
          </div>,
          document.body
        )}
    </div>
  )
}
