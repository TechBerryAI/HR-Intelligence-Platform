import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext.jsx'
import { apiRequest } from '../../utils/api.js'
import { tokenService } from '../../utils/tokenService.js'
import { FiUsers, FiBriefcase, FiFileText, FiCheckCircle, FiLogOut } from 'react-icons/fi'

function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/80 p-5 shadow-card">
      <div className="w-10 h-10 rounded-xl grid place-items-center bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
        <Icon className="w-5 h-5" />
      </div>
      <p className="mt-4 text-3xl font-bold text-slate-900 dark:text-white tabular-nums">{value ?? '—'}</p>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{label}</p>
    </div>
  )
}

export default function CeoDashboard() {
  const { auth, logout } = useApp()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const token = tokenService.getToken()
    apiRequest('/api/head-hr/stats', { method: 'GET', token })
      .then(setStats)
      .catch((err) => setError(err?.message || 'Failed to load analytics'))
      .finally(() => setLoading(false))
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <header className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white">Executive Dashboard</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">Read-only company analytics</p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-600 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700"
          >
            <FiLogOut className="w-4 h-4" /> Logout
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {loading && <p className="text-slate-500">Loading analytics…</p>}
        {error && <p className="text-red-600 dark:text-red-400">{error}</p>}
        {stats && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <StatCard icon={FiUsers} label="HR Team Members" value={stats.totalAdmins} />
            <StatCard icon={FiUsers} label="Total Candidates" value={stats.totalCandidates} />
            <StatCard icon={FiBriefcase} label="Total Jobs" value={stats.totalJobs} />
            <StatCard icon={FiCheckCircle} label="Active Jobs" value={stats.activeJobs} />
            <StatCard icon={FiFileText} label="Applications" value={stats.totalApplications} />
            <StatCard icon={FiCheckCircle} label="Shortlisted" value={stats.shortlistedApplications} />
          </div>
        )}
        <p className="mt-8 text-sm text-slate-500 dark:text-slate-400">
          Signed in as {auth.email} (CEO — read-only access)
        </p>
      </main>
    </div>
  )
}
