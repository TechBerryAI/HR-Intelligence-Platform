import React, { useEffect, useMemo, useRef, useState } from 'react'

export default function MonthYearPicker({
  value,
  onChange,
  placeholder = 'Select month',
  minYear = 1000,
  maxYear = new Date().getFullYear() + 10,
  className = '',
}) {
  const [open, setOpen] = useState(false)
  const [year, setYear] = useState(() => {
    if (value && /^\d{4}-\d{2}$/.test(value)) return parseInt(value.slice(0, 4), 10)
    return new Date().getFullYear()
  })
  const [month, setMonth] = useState(() => {
    if (value && /^\d{4}-\d{2}$/.test(value)) return parseInt(value.slice(5, 7), 10)
    return new Date().getMonth() + 1
  })

  const containerRef = useRef(null)

  useEffect(() => {
    const onClick = (e) => {
      if (!containerRef.current) return
      if (!containerRef.current.contains(e.target)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  useEffect(() => {
    if (value && /^\d{4}-\d{2}$/.test(value)) {
      const vYear = parseInt(value.slice(0, 4), 10)
      const vMonth = parseInt(value.slice(5, 7), 10)
      if (vYear !== year) setYear(vYear)
      if (vMonth !== month) setMonth(vMonth)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  const display = useMemo(() => {
    if (!value) return ''
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    const mm = parseInt(value.slice(5, 7), 10)
    const yy = value.slice(0, 4)
    return `${months[mm - 1]} ${yy}`
  }, [value])

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
        className="w-full text-left bg-transparent border-0 border-b border-zinc-700 py-2.5 text-gray-100 focus:border-white flex items-center justify-between"
        onClick={() => setOpen((o) => !o)}
      >
        <span className={display ? '' : 'text-zinc-500'}>{display || placeholder}</span>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-zinc-400">
          <path d="M6.75 3A.75.75 0 0 1 7.5 2.25h.75V3.75a.75.75 0 0 1-1.5 0V2.25H6.75zM15 2.25h.75V3.75a.75.75 0 0 1-1.5 0V2.25H15z" />
          <path fillRule="evenodd" d="M4.5 6.75A2.25 2.25 0 0 1 6.75 4.5h10.5A2.25 2.25 0 0 1 19.5 6.75v10.5A2.25 2.25 0 0 1 17.25 19.5H6.75A2.25 2.25 0 0 1 4.5 17.25V6.75zm2.25.75a.75.75 0 0 0-.75.75v8.25c0 .414.336.75.75.75h10.5a.75.75 0 0 0 .75-.75V8.25a.75.75 0 0 0-.75-.75H6.75z" clipRule="evenodd" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-20 mt-2 w-72 rounded-lg border border-zinc-800 bg-zinc-950/95 backdrop-blur p-3 shadow-xl">
          <div className="flex items-center justify-between gap-2 mb-3">
            <button
              type="button"
              className="px-2 py-1 text-sm rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => setYear((y) => Math.max(minYear, y - 1))}
              disabled={year <= minYear}
            >
              ◀
            </button>
            <select
              className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm text-gray-100"
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
              className="px-2 py-1 text-sm rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed"
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
                className={`px-3 py-2 rounded border text-sm ${m === month && year === parseInt((value||'').slice(0,4)||'0',10) ? 'border-white/60 bg-zinc-800 text-white' : 'border-zinc-800 bg-zinc-900/60 text-zinc-300 hover:bg-zinc-800'}`}
              >
                {new Date(2000, m - 1).toLocaleString('en-US', { month: 'short' })}
              </button>
            ))}
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" className="text-xs text-zinc-400 hover:text-zinc-200" onClick={() => { onChange?.(''); setOpen(false) }}>Clear</button>
            <button type="button" className="text-xs text-white bg-zinc-800 hover:bg-zinc-700 rounded px-2 py-1" onClick={() => setOpen(false)}>Done</button>
          </div>
        </div>
      )}
    </div>
  )
}
