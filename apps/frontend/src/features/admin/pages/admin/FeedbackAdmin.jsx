import React, { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { FiFilter, FiRefreshCw, FiMessageSquare, FiChevronDown } from 'react-icons/fi'
import { useToast } from '@/shared/components/Toast.jsx'
import { BASE_URL } from '@/core/api/api.js'

const FEEDBACK_TYPES = ['Bug Report', 'Feature Request', 'General Feedback', 'Appreciation']
const MODULES = ['Leave Management', 'Payroll', 'Attendance', 'Dashboard', 'Other']
const SEVERITIES = ['Low', 'Medium', 'High', 'Critical']
const STATUSES = ['open', 'reviewed', 'resolved']

const fieldClass =
  'w-full px-3 py-2 rounded-lg bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] text-[var(--ei-text-primary)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-400/40'

export default function FeedbackAdmin() {
  const toast = useToast()
  const [feedback, setFeedback] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    feedback_type: '',
    module: '',
    severity: '',
    status: '',
    date_from: '',
    date_to: '',
  })
  const [filterOpen, setFilterOpen] = useState(false)

  const fetchFeedback = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      Object.entries(filters).forEach(([k, v]) => {
        if (v && v.trim()) params.set(k, v.trim())
      })
      const url = `${BASE_URL}/api/feedback/list${params.toString() ? `?${params}` : ''}`
      const res = await fetch(url)
      const data = await res.json()
      if (res.ok && data.success) {
        setFeedback(data.feedback || [])
      } else {
        toast.error(data.error || 'Failed to load feedback')
      }
    } catch {
      toast.error('Failed to load feedback')
    } finally {
      setLoading(false)
    }
  }, [filters, toast])

  useEffect(() => {
    fetchFeedback()
  }, [fetchFeedback])

  const updateFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const formatDate = (d) => {
    if (!d) return '—'
    try {
      return new Date(d).toLocaleString()
    } catch {
      return d
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[rgba(54,214,160,0.14)] flex items-center justify-center ring-1 ring-[rgba(54,214,160,0.25)]">
              <FiMessageSquare className="w-5 h-5 text-[#36D6A0]" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--ei-text-muted)]">
                Recruiter workspace
              </p>
              <h1 className="text-2xl font-bold text-[var(--ei-text-primary)]">HRMS Feedback (Admin)</h1>
              <p className="text-sm text-[var(--ei-text-secondary)]">Review internal testing feedback</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setFilterOpen((o) => !o)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)] text-[var(--ei-text-secondary)] hover:text-[var(--ei-text-primary)] transition"
            >
              <FiFilter className="w-4 h-4" />
              Filters
              <FiChevronDown className={`w-4 h-4 transition ${filterOpen ? 'rotate-180' : ''}`} />
            </button>
            <button
              type="button"
              onClick={fetchFeedback}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition"
            >
              <FiRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </motion.div>

        {filterOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mb-6 p-4 org-glass-card hover:transform-none grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4"
          >
            {[
              ['feedback_type', 'Type', FEEDBACK_TYPES],
              ['module', 'Module', MODULES],
              ['severity', 'Severity', SEVERITIES],
              ['status', 'Status', STATUSES],
            ].map(([key, label, options]) => (
              <div key={key}>
                <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">{label}</label>
                <select
                  value={filters[key]}
                  onChange={(e) => updateFilter(key, e.target.value)}
                  className={fieldClass}
                >
                  <option value="">All</option>
                  {options.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            ))}
            <div>
              <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">From date</label>
              <input
                type="date"
                value={filters.date_from}
                onChange={(e) => updateFilter('date_from', e.target.value)}
                className={fieldClass}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">To date</label>
              <input
                type="date"
                value={filters.date_to}
                onChange={(e) => updateFilter('date_to', e.target.value)}
                className={fieldClass}
              />
            </div>
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="org-glass-card hover:transform-none overflow-hidden"
        >
          {loading ? (
            <div className="py-16 text-center text-[var(--ei-text-muted)]">Loading...</div>
          ) : feedback.length === 0 ? (
            <div className="py-16 text-center text-[var(--ei-text-muted)]">No feedback found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--ei-border-primary)] bg-[var(--ei-surface-hover)]">
                    {['ID', 'Employee', 'Type', 'Module', 'Severity', 'Status', 'Date'].map((h) => (
                      <th key={h} className="px-4 py-3 text-[var(--ei-text-muted)] font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {feedback.map((row) => (
                    <tr key={row.id} className="border-b border-[var(--ei-border-primary)] hover:bg-[var(--ei-surface-hover)]">
                      <td className="px-4 py-3 text-[var(--ei-text-secondary)] font-mono">#{row.id}</td>
                      <td className="px-4 py-3">
                        <span className="text-[var(--ei-text-primary)]">{row.employee_name || '—'}</span>
                        {row.employee_id && (
                          <span className="block text-xs text-[var(--ei-text-muted)]">{row.employee_id}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-[var(--ei-text-secondary)]">{row.feedback_type || '—'}</td>
                      <td className="px-4 py-3 text-[var(--ei-text-secondary)]">{row.module || '—'}</td>
                      <td className="px-4 py-3 text-[var(--ei-text-secondary)]">{row.severity || '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          row.status === 'resolved' ? 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-400' :
                          row.status === 'reviewed' ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400' :
                          'bg-[var(--ei-surface-hover)] text-[var(--ei-text-muted)]'
                        }`}>
                          {row.status || 'open'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[var(--ei-text-muted)] text-xs">{formatDate(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </motion.div>

        {feedback.length > 0 && (
          <div className="mt-4 text-sm text-[var(--ei-text-muted)]">
            Showing {feedback.length} feedback entr{feedback.length === 1 ? 'y' : 'ies'}.
          </div>
        )}
      </div>
    </div>
  )
}
