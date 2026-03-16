import React, { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { FiFilter, FiRefreshCw, FiMessageSquare, FiChevronDown } from 'react-icons/fi'
import { useToast } from '../../components/Toast.jsx'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000'

const FEEDBACK_TYPES = ['Bug Report', 'Feature Request', 'General Feedback', 'Appreciation']
const MODULES = ['Leave Management', 'Payroll', 'Attendance', 'Dashboard', 'Other']
const SEVERITIES = ['Low', 'Medium', 'High', 'Critical']
const STATUSES = ['open', 'reviewed', 'resolved']

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
      const url = `${API_BASE_URL}/api/feedback/list${params.toString() ? `?${params}` : ''}`
      const res = await fetch(url)
      const data = await res.json()
      if (res.ok && data.success) {
        setFeedback(data.feedback || [])
      } else {
        toast.error(data.error || 'Failed to load feedback')
      }
    } catch (err) {
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
      const dt = new Date(d)
      return dt.toLocaleString()
    } catch {
      return d
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-600/20 flex items-center justify-center">
              <FiMessageSquare className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">HRMS Feedback (Admin)</h1>
              <p className="text-sm text-zinc-400">Review internal testing feedback</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setFilterOpen((o) => !o)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-white/10 bg-white/5 text-zinc-300 hover:bg-white/10 transition"
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
            exit={{ opacity: 0, height: 0 }}
            className="mb-6 p-4 rounded-xl border border-white/10 bg-zinc-900/50 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4"
          >
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Type</label>
              <select
                value={filters.feedback_type}
                onChange={(e) => updateFilter('feedback_type', e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-white/10 text-zinc-200 text-sm"
              >
                <option value="">All</option>
                {FEEDBACK_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Module</label>
              <select
                value={filters.module}
                onChange={(e) => updateFilter('module', e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-white/10 text-zinc-200 text-sm"
              >
                <option value="">All</option>
                {MODULES.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Severity</label>
              <select
                value={filters.severity}
                onChange={(e) => updateFilter('severity', e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-white/10 text-zinc-200 text-sm"
              >
                <option value="">All</option>
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Status</label>
              <select
                value={filters.status}
                onChange={(e) => updateFilter('status', e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-white/10 text-zinc-200 text-sm"
              >
                <option value="">All</option>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">From date</label>
              <input
                type="date"
                value={filters.date_from}
                onChange={(e) => updateFilter('date_from', e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-white/10 text-zinc-200 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">To date</label>
              <input
                type="date"
                value={filters.date_to}
                onChange={(e) => updateFilter('date_to', e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-white/10 text-zinc-200 text-sm"
              />
            </div>
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="rounded-xl border border-white/10 bg-zinc-900/30 overflow-hidden"
        >
          {loading ? (
            <div className="py-16 text-center text-zinc-400">Loading...</div>
          ) : feedback.length === 0 ? (
            <div className="py-16 text-center text-zinc-400">No feedback found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-white/10 bg-white/5">
                    <th className="px-4 py-3 text-zinc-400 font-medium">ID</th>
                    <th className="px-4 py-3 text-zinc-400 font-medium">Employee</th>
                    <th className="px-4 py-3 text-zinc-400 font-medium">Type</th>
                    <th className="px-4 py-3 text-zinc-400 font-medium">Module</th>
                    <th className="px-4 py-3 text-zinc-400 font-medium">Severity</th>
                    <th className="px-4 py-3 text-zinc-400 font-medium">Status</th>
                    <th className="px-4 py-3 text-zinc-400 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {feedback.map((row) => (
                    <tr key={row.id} className="border-b border-white/5 hover:bg-white/5">
                      <td className="px-4 py-3 text-zinc-300 font-mono">#{row.id}</td>
                      <td className="px-4 py-3">
                        <span className="text-white">{row.employee_name || '—'}</span>
                        {row.employee_id && (
                          <span className="block text-xs text-zinc-500">{row.employee_id}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-zinc-300">{row.feedback_type || '—'}</td>
                      <td className="px-4 py-3 text-zinc-300">{row.module || '—'}</td>
                      <td className="px-4 py-3 text-zinc-300">{row.severity || '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          row.status === 'resolved' ? 'bg-emerald-500/20 text-emerald-400' :
                          row.status === 'reviewed' ? 'bg-amber-500/20 text-amber-400' :
                          'bg-zinc-500/20 text-zinc-400'
                        }`}>
                          {row.status || 'open'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-zinc-500 text-xs">{formatDate(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </motion.div>

        {feedback.length > 0 && (
          <div className="mt-4 text-sm text-zinc-500">
            Showing {feedback.length} feedback entr{feedback.length === 1 ? 'y' : 'ies'}.
          </div>
        )}
      </div>
    </div>
  )
}
