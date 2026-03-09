import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext.jsx'
import { apiRequest } from '../../utils/api.js'
import { tokenService } from '../../utils/tokenService.js'
import SuperAdminLayout from './SuperAdminLayout.jsx'
import { FiUsers, FiUser, FiBriefcase, FiFileText, FiCheckCircle, FiTrendingUp, FiDownload } from 'react-icons/fi'
import {
  generateAdminsPdf, generateCandidatesPdf, generateJobsPdf,
  generateApplicationsPdf, generateFullSystemPdf,
} from '../../utils/pdfReportUtils.js'

function StatCard({ icon: Icon, label, value, accent, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`group text-left w-full rounded-2xl border bg-zinc-900/60 p-5 hover:bg-zinc-800/60 transition-all duration-200 ${
        accent === 'purple'
          ? 'border-purple-500/20 hover:border-purple-500/40'
          : 'border-zinc-800 hover:border-zinc-700'
      }`}
    >
      <div className="flex items-start justify-between">
        <div
          className={`w-10 h-10 rounded-xl grid place-items-center ${
            accent === 'purple'
              ? 'bg-purple-500/15 text-purple-400'
              : accent === 'blue'
              ? 'bg-blue-500/15 text-blue-400'
              : accent === 'green'
              ? 'bg-green-500/15 text-green-400'
              : accent === 'rose'
              ? 'bg-rose-500/15 text-rose-400'
              : 'bg-zinc-700/50 text-zinc-400'
          }`}
        >
          <Icon className="w-5 h-5" />
        </div>
        <FiTrendingUp className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
      </div>
      <p className="mt-4 text-3xl font-bold text-white tabular-nums">{value ?? '—'}</p>
      <p className="mt-1 text-sm text-zinc-400">{label}</p>
    </button>
  )
}

export default function SuperAdminDashboard() {
  const { superAdminAuth } = useApp()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reportLoading, setReportLoading] = useState({})
  const [fullPdfLoading, setFullPdfLoading] = useState(false)
  const [reportToast, setReportToast] = useState(null)

  useEffect(() => {
    const load = async () => {
      try {
        const token = tokenService.getToken()
        const data = await apiRequest('/api/super-admin/stats', { method: 'GET', token })
        setStats(data)
      } catch (err) {
        setError(err?.message || 'Failed to load stats')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const showReportToast = (msg, type = 'success') => {
    setReportToast({ msg, type })
    setTimeout(() => setReportToast(null), 3000)
  }

  const REPORT_META = {
    admins:       { url: '/api/super-admin/admins',       key: 'admins',       title: 'HR Admins Report' },
    candidates:   { url: '/api/super-admin/candidates',   key: 'candidates',   title: 'Candidates Report' },
    jobs:         { url: '/api/super-admin/jobs',         key: 'jobs',         title: 'Jobs Report' },
    applications: { url: '/api/super-admin/applications', key: 'applications', title: 'Applications Report' },
  }

  const handleDownloadReport = async (type) => {
    setReportLoading((p) => ({ ...p, [type]: true }))
    try {
      const token = tokenService.getToken()
      const { url, key, title } = REPORT_META[type]
      const data = await apiRequest(url, { method: 'GET', token })
      const rows = data[key] || []
      PDF_GENERATORS[type](rows)
      showReportToast(`${title} downloaded`)
    } catch (err) {
      showReportToast(err?.message || 'Failed to generate report', 'error')
    } finally {
      setReportLoading((p) => ({ ...p, [type]: false }))
    }
  }

  const fetchAllData = async () => {
    const token = tokenService.getToken()
    const [a, c, j, ap] = await Promise.all([
      apiRequest('/api/super-admin/admins',       { method: 'GET', token }),
      apiRequest('/api/super-admin/candidates',   { method: 'GET', token }),
      apiRequest('/api/super-admin/jobs',         { method: 'GET', token }),
      apiRequest('/api/super-admin/applications', { method: 'GET', token }),
    ])
    return {
      admins:       a.admins       || [],
      candidates:   c.candidates   || [],
      jobs:         j.jobs         || [],
      applications: ap.applications || [],
    }
  }

  const handleDownloadFullPdf = async () => {
    setFullPdfLoading(true)
    try {
      const all = await fetchAllData()
      generateFullSystemPdf(all)
      showReportToast('Full system PDF report downloaded')
    } catch (err) {
      showReportToast(err?.message || 'Failed to generate PDF', 'error')
    } finally {
      setFullPdfLoading(false)
    }
  }

  const PDF_GENERATORS = {
    admins:       (data) => generateAdminsPdf(data),
    candidates:   (data) => generateCandidatesPdf(data),
    jobs:         (data) => generateJobsPdf(data),
    applications: (data) => generateApplicationsPdf(data),
  }

  const reportCards = [
    { type: 'admins',       label: 'HR Admins Report',      desc: 'ID, name, email, company, joined date',             icon: FiUsers },
    { type: 'candidates',   label: 'Candidates Report',     desc: 'Profile, contact, experience, completion status',   icon: FiUser },
    { type: 'jobs',         label: 'Jobs Report',           desc: 'Title, company, location, status, posted by',       icon: FiBriefcase },
    { type: 'applications', label: 'Applications Report',   desc: 'Candidate, job, match score, status, applied date', icon: FiFileText },
  ]

  return (
    <SuperAdminLayout>
      {/* Report toast */}
      {reportToast && (
        <div
          className={`fixed top-20 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl text-sm font-medium transition-all ${
            reportToast.type === 'error'
              ? 'bg-red-500/20 border border-red-500/30 text-red-300'
              : 'bg-green-500/20 border border-green-500/30 text-green-300'
          }`}
        >
          {reportToast.type !== 'error' && <FiDownload className="w-4 h-4" />}
          {reportToast.msg}
        </div>
      )}

      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">System Overview</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Full-access dashboard — logged in as{' '}
          <span className="text-zinc-200 font-medium">{superAdminAuth?.email}</span>
        </p>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 animate-pulse">
              <div className="w-10 h-10 rounded-xl bg-zinc-800" />
              <div className="mt-4 h-8 w-16 rounded bg-zinc-800" />
              <div className="mt-2 h-4 w-28 rounded bg-zinc-800" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          <StatCard
            icon={FiUsers}
            label="Total HR Admins"
            value={stats?.totalAdmins}
            accent="purple"
            onClick={() => navigate('/super-admin/admins')}
          />
          <StatCard
            icon={FiUser}
            label="Total Candidates"
            value={stats?.totalCandidates}
            accent="blue"
            onClick={() => navigate('/super-admin/candidates')}
          />
          <StatCard
            icon={FiBriefcase}
            label="Total Jobs"
            value={stats?.totalJobs}
            accent="purple"
            onClick={() => navigate('/super-admin/jobs')}
          />
          <StatCard
            icon={FiBriefcase}
            label="Active Jobs"
            value={stats?.activeJobs}
            accent="green"
            onClick={() => navigate('/super-admin/jobs')}
          />
          <StatCard
            icon={FiFileText}
            label="Total Applications"
            value={stats?.totalApplications}
            accent="rose"
            onClick={() => navigate('/super-admin/applications')}
          />
          <StatCard
            icon={FiCheckCircle}
            label="Shortlisted"
            value={stats?.shortlistedApplications}
            accent="green"
            onClick={() => navigate('/super-admin/applications')}
          />
        </div>
      )}

      {/* Quick links */}
      <div className="mt-10 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          {[
            { label: 'Manage Admins', path: '/super-admin/admins' },
            { label: 'View Candidates', path: '/super-admin/candidates' },
            { label: 'View All Jobs', path: '/super-admin/jobs' },
            { label: 'View Applications', path: '/super-admin/applications' },
          ].map(({ label, path }) => (
            <button
              key={path}
              onClick={() => navigate(path)}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-all border bg-white/5 border-white/10 text-zinc-300 hover:bg-white/10 hover:text-white hover:border-white/20"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {/* Reports section */}
      <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
        <div className="flex items-start justify-between mb-4 flex-wrap gap-3">
          <div>
            <h2 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
              <FiDownload className="w-4 h-4" /> Download Reports
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              PDF reports — title, metadata, summary statistics &amp; formatted tables
            </p>
          </div>
          <button
            onClick={handleDownloadFullPdf}
            disabled={fullPdfLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            {fullPdfLoading ? <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" /></svg> : <FiDownload className="w-4 h-4" />}
            Full PDF Report
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          {reportCards.map(({ type, label, desc, icon: Icon }) => (
            <div
              key={type}
              className="flex flex-col gap-3 rounded-xl bg-zinc-900 border border-zinc-800 hover:border-zinc-700 p-4 transition-colors"
            >
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-zinc-800 grid place-items-center text-zinc-400">
                  <Icon className="w-4 h-4" />
                </div>
                <p className="text-sm font-medium text-zinc-200">{label}</p>
              </div>
              <p className="text-xs text-zinc-500 leading-relaxed flex-1">{desc}</p>
              <button
                onClick={() => handleDownloadReport(type)}
                disabled={!!reportLoading[type]}
                className="mt-auto w-full flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {reportLoading[type] ? <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" /></svg> : <FiDownload className="w-3 h-3" />}
                Download PDF
              </button>
            </div>
          ))}
        </div>
      </div>
    </SuperAdminLayout>
  )
}
