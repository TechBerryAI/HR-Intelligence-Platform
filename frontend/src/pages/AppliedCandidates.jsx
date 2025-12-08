import React, { useState, useEffect, useMemo } from 'react'
import { useApp } from '../context/AppContext.jsx'
import CandidateCard from '../components/CandidateCard.jsx'
import { BASE_URL, apiRequest } from '../utils/api'
import { tokenService } from '../utils/tokenService'
import { getAvatarGradient } from '../utils/avatarColor'

// Helper function to get score color and label (same as CandidateCard)
const getScoreInfo = (score) => {
  if (score >= 80) return { color: 'text-green-400', bgColor: 'bg-green-900/30', ringColor: 'ring-green-700', label: 'Excellent Match' }
  if (score >= 70) return { color: 'text-emerald-400', bgColor: 'bg-emerald-900/30', ringColor: 'ring-emerald-700', label: 'Great Match' }
  if (score >= 60) return { color: 'text-blue-400', bgColor: 'bg-blue-900/30', ringColor: 'ring-blue-700', label: 'Good Match' }
  if (score >= 50) return { color: 'text-cyan-400', bgColor: 'bg-cyan-900/30', ringColor: 'ring-cyan-700', label: 'Fair Match' }
  if (score >= 40) return { color: 'text-yellow-400', bgColor: 'bg-yellow-900/30', ringColor: 'ring-yellow-700', label: 'Moderate Match' }
  if (score >= 30) return { color: 'text-orange-400', bgColor: 'bg-orange-900/30', ringColor: 'ring-orange-700', label: 'Low Match' }
  return { color: 'text-red-400', bgColor: 'bg-red-900/30', ringColor: 'ring-red-700', label: 'Poor Match' }
}

// Score filter ranges
const SCORE_FILTERS = [
  { id: 'all', label: 'All Candidates', min: 0, max: 100 },
  { id: '80+', label: '> 80%', min: 80, max: 100 },
  { id: '70-80', label: '70-80%', min: 70, max: 80 },
  { id: '60-70', label: '60-70%', min: 60, max: 70 },
  { id: '50-60', label: '50-60%', min: 50, max: 60 },
  { id: '40-50', label: '40-50%', min: 40, max: 50 },
  { id: '30-40', label: '30-40%', min: 30, max: 40 },
  { id: '<30', label: '< 30%', min: 0, max: 30 },
]

export default function AppliedCandidates() {
  const { jobs, fetchApplicationsForJob, auth } = useApp()
  const [selectedJobId, setSelectedJobId] = useState(null)
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedFilter, setSelectedFilter] = useState('all')
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [viewMode, setViewMode] = useState('grid') // 'grid' or 'list'
  const [resumeAction, setResumeAction] = useState({ isLoading: false, candidateKey: null })
  const [profileLoading, setProfileLoading] = useState(false)

  const resolvedCandidateId = useMemo(() => {
    if (!selectedCandidate) return null
    return (
      selectedCandidate.candidateId ||
      selectedCandidate.candidate_id ||
      selectedCandidate.candidateID ||
      selectedCandidate.cid ||
      null
    )
  }, [selectedCandidate])

  // Filter jobs to only show those with applications (for HR)
  const jobsWithApplications = useMemo(() => {
    return jobs.filter(job => job.enabled !== false)
  }, [jobs])

  // Set initial selected job
  useEffect(() => {
    if (jobsWithApplications.length > 0 && !selectedJobId) {
      setSelectedJobId(jobsWithApplications[0].id)
    }
  }, [jobsWithApplications, selectedJobId])

  // Fetch applications when job is selected
  useEffect(() => {
    if (!selectedJobId) return

    const loadApplications = async () => {
      setLoading(true)
      setError('')
      const result = await fetchApplicationsForJob(selectedJobId)
      if (result.ok) {
        setApplications(result.data || [])
      } else {
        setError(result.message || 'Failed to load applications')
        setApplications([])
      }
      setLoading(false)
    }

    loadApplications()
  }, [selectedJobId, fetchApplicationsForJob])

  // Filter and sort candidates
  const filteredCandidates = useMemo(() => {
    const filter = SCORE_FILTERS.find(f => f.id === selectedFilter)
    if (!filter) return []

    const filtered = applications.filter(app => {
      const score = Number(app.matchScore || app.score || 0)
      
      // Handle "all" filter - include all scores
      if (filter.id === 'all') {
        return score >= filter.min && score <= filter.max
      }
      
      // Handle "> 80%" filter - include 80 to 100 (inclusive)
      if (filter.id === '80+') {
        return score >= 80 && score <= 100
      }
      
      // Handle "< 30%" filter - include 0 to 29 (exclusive of 30)
      if (filter.id === '<30') {
        return score >= 0 && score < 30
      }
      
      // Handle range filters (e.g., "70-80%") - include min to max-1 to avoid overlap
      // This means 70-79 for "70-80%", 60-69 for "60-70%", etc.
      return score >= filter.min && score < filter.max
    })

    // Sort by score descending
    return filtered.sort((a, b) => {
      const scoreA = Number(a.matchScore || a.score || 0)
      const scoreB = Number(b.matchScore || b.score || 0)
      return scoreB - scoreA
    })
  }, [applications, selectedFilter])

  const handleViewDetails = (candidate) => {
    setSelectedCandidate(candidate)
  }

  useEffect(() => {
    if (!resolvedCandidateId) return

    let cancelled = false

    const loadProfile = async () => {
      setProfileLoading(true)
      try {
        const profile = await apiRequest(`/api/candidate/profile/${encodeURIComponent(resolvedCandidateId)}`, {
          token: tokenService.getToken(),
        })
        if (!cancelled) {
          setSelectedCandidate((prev) => (prev ? { ...prev, ...profile } : prev))
        }
      } catch (err) {
        console.error('Failed to fetch candidate profile', err)
      } finally {
        if (!cancelled) setProfileLoading(false)
      }
    }

    loadProfile()

    return () => {
      cancelled = true
    }
  }, [resolvedCandidateId])

  const closeModal = () => {
    setSelectedCandidate(null)
  }

  const buildResumeUrl = (candidate) => {
    if (!candidate) return null

    const candidateId =
      candidate.candidateId ||
      candidate.candidate_id ||
      candidate.candidateID ||
      candidate.cid
    const jobId = candidate.jobId || candidate.job_id

    const derivedPath =
      !candidate.resumeUrl && candidateId && jobId
        ? `/api/jobs/${encodeURIComponent(jobId)}/applications/${encodeURIComponent(candidateId)}/resume`
        : null

    const rawUrl = candidate.resumeUrl || derivedPath
    if (!rawUrl) return null

    return rawUrl.startsWith('http')
      ? rawUrl
      : `${BASE_URL || ''}${rawUrl}`
  }

  const fetchResumeBlob = async (candidate) => {
    const url = buildResumeUrl(candidate)
    if (!url) throw new Error('Resume link not available')

    const token = tokenService.getToken()
    const response = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('Failed to load resume')
    }

    return response.blob()
  }

  const handleResumeAction = async (candidate, action = 'view') => {
    if (!candidate?.resumeUrl || resumeAction.isLoading) return
    const candidateKey = candidate.id || candidate.candidateId || candidate.email || candidate.fullName
    setResumeAction({ isLoading: true, candidateKey })
    try {
      const blob = await fetchResumeBlob(candidate)
      const blobUrl = URL.createObjectURL(blob)

      if (action === 'download') {
        const link = document.createElement('a')
        link.href = blobUrl
        const safeName = (candidate.resumeFileName || `${candidate.fullName || 'resume'}.pdf`).replace(/\s+/g, '_')
        link.download = safeName
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      } else {
        window.open(blobUrl, '_blank', 'noopener,noreferrer')
      }

      setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000)
    } catch (err) {
      console.error('Error handling resume:', err)
      alert(err?.message || 'Unable to access resume. Please try again.')
    } finally {
      setResumeAction({ isLoading: false, candidateKey: null })
    }
  }

  if (!auth.isLoggedIn || auth.role !== 'HR') {
    return (
      <section className="py-10">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center text-zinc-400">
            <p>You must be logged in as HR to view this page.</p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="py-8 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">Applied Candidates</h1>
          <p className="mt-2 text-zinc-400">Review and manage candidate applications by job posting</p>
        </div>

        {jobsWithApplications.length === 0 ? (
          <div className="text-center py-12">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-zinc-800 mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-8 h-8 text-zinc-500">
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 0 0 .75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 0 0-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0 1 12 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 0 1-.673-.38m0 0A2.18 2.18 0 0 1 3 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 0 1 3.413-.387m7.5 0V5.25A2.25 2.25 0 0 0 13.5 3h-3a2.25 2.25 0 0 0-2.25 2.25v.894m7.5 0a48.667 48.667 0 0 0-7.5 0" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-white">No Job Postings</h3>
            <p className="mt-1 text-sm text-zinc-400">Create job postings to start receiving applications</p>
          </div>
        ) : (
          <>
            {/* Job Dropdown */}
            <div className="mb-6">
              <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-zinc-500 font-semibold">Job Description</p>
                  <h2 className="text-lg font-semibold text-white mt-1">Select a job to view applicants</h2>
                </div>
                <div className="w-full sm:w-72">
                  <div className="relative rounded-xl bg-gradient-to-r from-zinc-900 via-zinc-800 to-zinc-900 border border-white/10 shadow-[0_12px_30px_rgba(0,0,0,0.45)]">
                    <select
                      value={selectedJobId || ''}
                      onChange={(e) => setSelectedJobId(e.target.value)}
                      className="w-full appearance-none bg-transparent text-sm font-semibold tracking-wide text-white px-4 py-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
                    >
                      {jobsWithApplications.map(job => (
                        <option
                          key={job.id}
                          value={job.id}
                          className="text-zinc-900 bg-white"
                          style={{ backgroundColor: '#f5f6f8', color: '#0f172a' }}
                        >
                          JD #{job.id} • {job.title}
                        </option>
                      ))}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 pr-4 flex items-center text-zinc-400">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 011.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                      </svg>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Score Filter Dropdown */}
            <div className="mb-6">
              <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-zinc-400">Filter by Match Score</span>
                </div>
                <div className="w-full sm:w-64">
                  <div className="relative rounded-xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-white/10 shadow-[0_12px_30px_rgba(0,0,0,0.45)]">
                    <select
                      value={selectedFilter}
                      onChange={(e) => setSelectedFilter(e.target.value)}
                      className="w-full appearance-none bg-transparent text-sm font-semibold tracking-wide text-white px-4 py-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:border-emerald-400"
                    >
                      {SCORE_FILTERS.map(filter => {
                        const count = applications.filter(app => {
                          const score = Number(app.matchScore || app.score || 0)
                          if (filter.id === 'all') return score >= filter.min && score <= filter.max
                          if (filter.id === '80+') return score >= 80 && score <= 100
                          if (filter.id === '<30') return score >= 0 && score < 30
                          return score >= filter.min && score < filter.max
                        }).length

                        return (
                          <option
                            key={filter.id}
                            value={filter.id}
                            className="text-zinc-900 bg-white"
                            style={{ backgroundColor: '#f5f6f8', color: '#0f172a' }}
                          >
                            {filter.label} {count > 0 ? `(${count})` : ''}
                          </option>
                        )
                      })}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 pr-4 flex items-center text-zinc-400">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 011.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                      </svg>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Loading State */}
            {loading && (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
                <p className="mt-4 text-zinc-400">Loading candidates...</p>
              </div>
            )}

            {/* Error State */}
            {error && !loading && (
              <div className="rounded-lg border border-red-600/40 bg-red-950/50 text-red-200 px-4 py-3">
                {error}
              </div>
            )}

            {/* Candidates Grid */}
            {!loading && !error && (
              <div>
                {filteredCandidates.length === 0 ? (
                  <div className="text-center py-12 bg-zinc-900/30 rounded-xl ring-1 ring-zinc-800">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-zinc-800 mb-4">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-8 h-8 text-zinc-500">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" />
                      </svg>
                    </div>
                    <h3 className="text-lg font-medium text-white">No Candidates Found</h3>
                    <p className="mt-1 text-sm text-zinc-400">
                      {selectedFilter === 'all' 
                        ? 'No applications received for this job yet' 
                        : 'No candidates match the selected score range'}
                    </p>
                  </div>
                ) : (
                  <>
                    <div className="mb-4 flex items-center justify-between">
                      <p className="text-sm text-zinc-400">
                        Showing <span className="font-semibold text-white">{filteredCandidates.length}</span> candidate{filteredCandidates.length !== 1 ? 's' : ''}
                      </p>
                      {/* View Mode Toggle Slider */}
                      <div className="flex items-center gap-3">
                      <div className="relative">
                          <button
                            onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
                          className="relative w-32 h-11 rounded-full bg-zinc-800/90 border border-zinc-700/50 shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)] transition-all duration-300 hover:border-zinc-600 focus:outline-none focus:ring-2 focus:ring-white/20"
                            aria-label={`Switch to ${viewMode === 'grid' ? 'List' : 'Grid'} view`}
                          >
                            {/* Background with subtle texture */}
                            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-zinc-800 via-zinc-800 to-zinc-900"></div>
                            
                            {/* Slider Handle - Modern neumorphic style */}
                            <div
                            className={`absolute top-1.5 left-1.5 w-14 h-8 rounded-full bg-gradient-to-br from-white via-zinc-50 to-zinc-100 transition-all duration-300 ease-in-out ${
                              viewMode === 'list' ? 'translate-x-[4rem]' : 'translate-x-0'
                              }`}
                              style={{
                                boxShadow: `
                                  0 4px 12px rgba(0, 0, 0, 0.4),
                                  0 2px 4px rgba(0, 0, 0, 0.2),
                                  inset 0 1px 2px rgba(255, 255, 255, 0.95),
                                  inset 0 -1px 1px rgba(0, 0, 0, 0.1)
                                `
                              }}
                            >
                              {/* Subtle inner glow */}
                              <div className="absolute inset-0 rounded-full bg-gradient-to-br from-white/60 via-transparent to-transparent opacity-50"></div>
                            </div>
                            
                            {/* Labels with smooth transitions */}
                            <div className="relative flex items-center justify-between h-full px-4 z-10">
                              <span
                                className={`text-xs font-bold uppercase tracking-wider transition-all duration-300 ${
                                  viewMode === 'grid' 
                                    ? 'text-zinc-900 drop-shadow-sm' 
                                    : 'text-zinc-500'
                                }`}
                                style={{
                                  textShadow: viewMode === 'grid' ? '0 1px 2px rgba(0, 0, 0, 0.1)' : 'none'
                                }}
                              >
                                GRID
                              </span>
                              <span
                                className={`text-xs font-bold uppercase tracking-wider transition-all duration-300 ${
                                  viewMode === 'list' 
                                    ? 'text-zinc-900 drop-shadow-sm' 
                                    : 'text-zinc-500'
                                }`}
                                style={{
                                  textShadow: viewMode === 'list' ? '0 1px 2px rgba(0, 0, 0, 0.1)' : 'none'
                                }}
                              >
                                LIST
                              </span>
                            </div>
                          </button>
                        </div>
                      </div>
                    </div>
                    
                    {viewMode === 'grid' ? (
                      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
                        {filteredCandidates.map((candidate, index) => (
                          <CandidateCard
                            key={candidate.id || index}
                            candidate={candidate}
                            onViewDetails={handleViewDetails}
                          />
                        ))}
                      </div>
                    ) : (
                      <div className="bg-zinc-900/50 rounded-xl ring-1 ring-zinc-800 overflow-hidden">
                        <div className="overflow-x-auto">
                          <table className="w-full">
                            <thead className="bg-zinc-800/50 border-b border-zinc-700">
                              <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Sr.no</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Candidate Name</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Match Score</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Status</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Action</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-800">
                              {filteredCandidates.map((candidate, index) => {
                                const score = Math.round(Number(candidate.matchScore || candidate.score || 0))
                                const scoreInfo = getScoreInfo(score)
                                
                                return (
                                  <tr key={candidate.id || index} className="hover:bg-zinc-800/30 transition-colors">
                                    <td className="px-6 py-4 whitespace-nowrap">
                                      <span className="text-sm font-medium text-zinc-300">{index + 1}</span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                      <div className="flex items-center gap-3">
                                        <div
                                          className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold text-sm ring-2 ring-zinc-700"
                                          style={{
                                            backgroundImage: getAvatarGradient(
                                              candidate.email || candidate.fullName || String(index)
                                            ),
                                          }}
                                        >
                                          {(candidate.fullName || candidate.name || 'C').charAt(0).toUpperCase()}
                                        </div>
                                        <div>
                                          <div className="text-sm font-medium text-white">
                                            {candidate.fullName || candidate.name || 'Unknown Candidate'}
                                          </div>
                                          <div className="text-xs text-zinc-400">{candidate.email || 'N/A'}</div>
                                        </div>
                                      </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                      <div className="flex items-center gap-2">
                                        <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full ${scoreInfo.bgColor} ring-1 ${scoreInfo.ringColor}`}>
                                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={`w-4 h-4 ${scoreInfo.color}`}>
                                            <path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.006 5.404.434c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.434 2.082-5.005Z" clipRule="evenodd" />
                                          </svg>
                                          <span className={`text-sm font-bold ${scoreInfo.color}`}>{score}%</span>
                                        </div>
                                      </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                      <span className={`text-xs font-medium ${scoreInfo.color}`}>{scoreInfo.label}</span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                      <button
                                        onClick={() => handleViewDetails(candidate)}
                                        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white text-sm font-medium transition-all duration-200 ring-1 ring-white/10 hover:ring-white/20"
                                      >
                                        <span>View</span>
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
                                          <path fillRule="evenodd" d="M16.28 11.47a.75.75 0 0 1 0 1.06l-7.5 7.5a.75.75 0 0 1-1.06-1.06L14.69 12 7.72 5.03a.75.75 0 0 1 1.06-1.06l7.5 7.5Z" clipRule="evenodd" />
                                        </svg>
                                      </button>
                                    </td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Candidate Detail Modal */}
      {selectedCandidate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={closeModal}>
          <div className="bg-zinc-900 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto ring-1 ring-zinc-700 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-zinc-900 border-b border-zinc-800 px-6 py-4 flex items-center justify-between z-10">
              <div className="flex items-center gap-3">
                <div
                  className="w-12 h-12 rounded-full flex items-center justify-center text-white font-semibold text-lg"
                  style={{
                    backgroundImage: getAvatarGradient(
                      selectedCandidate.email || selectedCandidate.fullName || 'candidate'
                    ),
                  }}
                >
                  {(selectedCandidate.fullName || selectedCandidate.name || 'C').charAt(0).toUpperCase()}
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">{selectedCandidate.fullName || selectedCandidate.name || 'Candidate Profile'}</h2>
                  <p className="text-sm text-zinc-400">{selectedCandidate.email || ''}</p>
                </div>
              </div>
              <button onClick={closeModal} className="text-zinc-400 hover:text-white transition p-2 hover:bg-zinc-800 rounded-lg">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 space-y-6">
              {/* Match Score Badge */}
              <div className="flex items-center gap-4 pb-4 border-b border-zinc-800">
                {profileLoading && (
                  <span className="text-xs text-zinc-400 animate-pulse">
                    Syncing latest profile…
                  </span>
                )}
                <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${getScoreInfo(Math.round(Number(selectedCandidate.matchScore || selectedCandidate.score || 0))).bgColor} ring-1 ${getScoreInfo(Math.round(Number(selectedCandidate.matchScore || selectedCandidate.score || 0))).ringColor}`}>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className={`w-5 h-5 ${getScoreInfo(Math.round(Number(selectedCandidate.matchScore || selectedCandidate.score || 0))).color}`}>
                    <path fillRule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.006 5.404.434c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.434 2.082-5.005Z" clipRule="evenodd" />
                  </svg>
                  <span className={`text-lg font-bold ${getScoreInfo(Math.round(Number(selectedCandidate.matchScore || selectedCandidate.score || 0))).color}`}>
                    {Math.round(Number(selectedCandidate.matchScore || selectedCandidate.score || 0))}% Match
                  </span>
                </div>
                <span className={`text-sm font-medium ${getScoreInfo(Math.round(Number(selectedCandidate.matchScore || selectedCandidate.score || 0))).color}`}>
                  {getScoreInfo(Math.round(Number(selectedCandidate.matchScore || selectedCandidate.score || 0))).label}
                </span>
                {selectedCandidate.appliedAt && (
                  <span className="text-sm text-zinc-400 ml-auto">
                    Applied on {new Date(selectedCandidate.appliedAt).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
                  </span>
                )}
              </div>

              {/* Basic Information */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-zinc-400">
                    <path fillRule="evenodd" d="M18.685 19.097A9.723 9.723 0 0 0 21.75 12c0-5.385-4.365-9.75-9.75-9.75S2.25 6.615 2.25 12a9.723 9.723 0 0 0 3.065 7.097A9.716 9.716 0 0 0 12 21.75a9.716 9.716 0 0 0 6.685-2.653Zm-12.54-1.285A7.486 7.486 0 0 1 12 15a7.486 7.486 0 0 1 5.855 2.812A8.224 8.224 0 0 1 12 20.25a8.224 8.224 0 0 1-5.855-2.438ZM15.75 9a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" clipRule="evenodd" />
                  </svg>
                  Basic Information
                </h3>
                <div className="bg-zinc-800/50 rounded-xl p-4 space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-zinc-400 block mb-1">Full Name</span>
                      <span className="text-white font-medium">{selectedCandidate.fullName || selectedCandidate.name || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-zinc-400 block mb-1">Email</span>
                      <span className="text-white font-medium">{selectedCandidate.email || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-zinc-400 block mb-1">Phone</span>
                      <span className="text-white font-medium">{selectedCandidate.phone || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-zinc-400 block mb-1">Current Location</span>
                      <span className="text-white font-medium">{selectedCandidate.currentLocation || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-zinc-400 block mb-1">Preferred Location</span>
                      <span className="text-white font-medium">{selectedCandidate.preferredLocation || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-zinc-400 block mb-1">Experience Level</span>
                      <span className="text-white font-medium capitalize">{selectedCandidate.experienceLevel || 'N/A'}</span>
                    </div>
                  </div>
                  {(selectedCandidate.linkedinUrl || selectedCandidate.portfolioUrl) && (
                    <div className="pt-3 border-t border-zinc-700 space-y-2">
                      {selectedCandidate.linkedinUrl && (
                        <div>
                          <span className="text-zinc-400 block mb-1 text-sm">LinkedIn</span>
                          <a href={selectedCandidate.linkedinUrl} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 text-sm underline">
                            {selectedCandidate.linkedinUrl}
                          </a>
                        </div>
                      )}
                      {selectedCandidate.portfolioUrl && (
                        <div>
                          <span className="text-zinc-400 block mb-1 text-sm">Portfolio</span>
                          <a href={selectedCandidate.portfolioUrl} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 text-sm underline">
                            {selectedCandidate.portfolioUrl}
                          </a>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Notice Period Information */}
              {(selectedCandidate.servingNotice || selectedCandidate.noticePeriod || selectedCandidate.lastWorkingDay) && (
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-zinc-400">
                      <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25ZM12.75 6a.75.75 0 0 0-1.5 0v6c0 .414.336.75.75.75h4.5a.75.75 0 0 0 0-1.5h-3.75V6Z" clipRule="evenodd" />
                    </svg>
                    Notice Period
                  </h3>
                  <div className="bg-zinc-800/50 rounded-xl p-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="text-zinc-400 block mb-1">Serving Notice</span>
                        <span className="text-white font-medium capitalize">{selectedCandidate.servingNotice || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-zinc-400 block mb-1">Notice Period</span>
                        <span className="text-white font-medium">{selectedCandidate.noticePeriod || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-zinc-400 block mb-1">Last Working Day</span>
                        <span className="text-white font-medium">{selectedCandidate.lastWorkingDay || 'N/A'}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Education */}
              {selectedCandidate.education && selectedCandidate.education.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-zinc-400">
                      <path d="M11.7 2.805a.75.75 0 0 1 .6 0A60.65 60.65 0 0 1 22.83 8.72a.75.75 0 0 1-.231 1.337 49.948 49.948 0 0 0-9.902 3.912l-.003.002c-.114.06-.227.119-.34.18a.75.75 0 0 1-.707 0A50.88 50.88 0 0 0 7.5 12.173v-.224c0-.131.067-.248.172-.311a54.615 54.615 0 0 1 4.653-2.52.75.75 0 0 0-.65-1.352 56.123 56.123 0 0 0-4.78 2.589 1.858 1.858 0 0 0-.859 1.228 49.803 49.803 0 0 0-4.634-1.527.75.75 0 0 1-.231-1.337A60.653 60.653 0 0 1 11.7 2.805Z" />
                      <path d="M13.06 15.473a48.45 48.45 0 0 1 7.666-3.282c.134 1.414.22 2.843.255 4.284a.75.75 0 0 1-.46.711 47.87 47.87 0 0 0-8.105 4.342.75.75 0 0 1-.832 0 47.87 47.87 0 0 0-8.104-4.342.75.75 0 0 1-.461-.71c.035-1.442.121-2.87.255-4.286.921.304 1.83.634 2.726.99v1.27a1.5 1.5 0 0 0-.14 2.508c-.09.38-.222.753-.397 1.11.452.213.901.434 1.346.66a6.727 6.727 0 0 0 .551-1.607 1.5 1.5 0 0 0 .14-2.67v-.645a48.549 48.549 0 0 1 3.44 1.667 2.25 2.25 0 0 0 2.12 0Z" />
                    </svg>
                    Education
                  </h3>
                  <div className="space-y-3">
                    {selectedCandidate.education.map((edu, idx) => (
                      <div key={idx} className="bg-zinc-800/50 rounded-lg p-4 border border-zinc-700/50">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="font-semibold text-white text-base mb-1">{edu.degree || 'N/A'}</div>
                            <div className="text-zinc-300 text-sm mb-2">{edu.institution || 'N/A'}</div>
                            <div className="flex items-center gap-4 text-xs text-zinc-400">
                              {edu.cgpa && (
                                <span className="flex items-center gap-1">
                                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">
                                    <path fillRule="evenodd" d="M5.166 5.166A3.75 3.75 0 0 1 8.25 3.75h7.5a3.75 3.75 0 0 1 3.084 1.416A3.75 3.75 0 0 1 18.75 9H8.25a3.75 3.75 0 0 1-3.084-3.834ZM8.25 4.5a2.25 2.25 0 0 0-2.166 2.666A2.25 2.25 0 0 0 6 9h12a2.25 2.25 0 0 0 2.166-1.834A2.25 2.25 0 0 0 18.75 4.5h-10.5Z" clipRule="evenodd" />
                                    <path d="M4.5 12.75a3.75 3.75 0 0 1 3.75-3.75h7.5a3.75 3.75 0 0 1 3.75 3.75v3a3.75 3.75 0 0 1-3.75 3.75h-7.5a3.75 3.75 0 0 1-3.75-3.75v-3Zm3.75-2.25a2.25 2.25 0 0 0-2.25 2.25v3a2.25 2.25 0 0 0 2.25 2.25h7.5a2.25 2.25 0 0 0 2.25-2.25v-3a2.25 2.25 0 0 0-2.25-2.25h-7.5Z" />
                                  </svg>
                                  CGPA: {edu.cgpa}
                                </span>
                              )}
                              {(edu.startMonth || edu.endMonth) && (
                                <span className="flex items-center gap-1">
                                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">
                                    <path fillRule="evenodd" d="M6.75 2.25A.75.75 0 0 1 7.5 3v1.5h9V3a.75.75 0 0 1 1.5 0v1.5h1.5a3 3 0 0 1 3 3v11.25a3 3 0 0 1-3 3H5.25a3 3 0 0 1-3-3V7.5a3 3 0 0 1 3-3H6.75V3Zm-1.5 4.5v-.75a1.5 1.5 0 0 1 1.5-1.5h13.5a1.5 1.5 0 0 1 1.5 1.5v.75h-16.5Zm16.5 0H4.5v8.25a1.5 1.5 0 0 0 1.5 1.5h13.5a1.5 1.5 0 0 0 1.5-1.5V6.75Z" clipRule="evenodd" />
                                  </svg>
                                  {edu.startMonth || 'N/A'} - {edu.endMonth || 'N/A'}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Experience */}
              {selectedCandidate.experiences && selectedCandidate.experiences.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-zinc-400">
                      <path fillRule="evenodd" d="M7.5 5.25a3 3 0 0 1 3-3h3a3 3 0 0 1 3 3V8.25a.75.75 0 0 1-1.5 0V5.25a1.5 1.5 0 0 0-1.5-1.5h-3a1.5 1.5 0 0 0-1.5 1.5v3a.75.75 0 0 1-1.5 0V5.25Zm-1.5 3.75A2.25 2.25 0 0 0 3.75 11.25v8.25A2.25 2.25 0 0 0 6 21.75h12a2.25 2.25 0 0 0 2.25-2.25v-8.25A2.25 2.25 0 0 0 18 9H6Z" clipRule="evenodd" />
                    </svg>
                    Work Experience
                  </h3>
                  <div className="space-y-3">
                    {selectedCandidate.experiences.map((exp, idx) => (
                      <div key={idx} className="bg-zinc-800/50 rounded-lg p-4 border border-zinc-700/50">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="font-semibold text-white text-base mb-1">{exp.role || 'N/A'}</div>
                            <div className="text-zinc-300 text-sm mb-2">{exp.company || 'N/A'}</div>
                            <div className="flex items-center gap-1 text-xs text-zinc-400">
                              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">
                                <path fillRule="evenodd" d="M6.75 2.25A.75.75 0 0 1 7.5 3v1.5h9V3a.75.75 0 0 1 1.5 0v1.5h1.5a3 3 0 0 1 3 3v11.25a3 3 0 0 1-3 3H5.25a3 3 0 0 1-3-3V7.5a3 3 0 0 1 3-3H6.75V3Zm-1.5 4.5v-.75a1.5 1.5 0 0 1 1.5-1.5h13.5a1.5 1.5 0 0 1 1.5 1.5v.75h-16.5Zm16.5 0H4.5v8.25a1.5 1.5 0 0 0 1.5 1.5h13.5a1.5 1.5 0 0 0 1.5-1.5V6.75Z" clipRule="evenodd" />
                              </svg>
                              {exp.startMonth || 'N/A'} - {exp.isCurrent ? 'Present' : (exp.endMonth || 'N/A')}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Certifications */}
              {selectedCandidate.certifications && selectedCandidate.certifications.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 text-zinc-400">
                      <path fillRule="evenodd" d="M9 12.15 5.67 9.85a.75.75 0 0 0-1.06 1.06l3.75 3.75a.75.75 0 0 0 1.06 0l8.25-8.25a.75.75 0 1 0-1.06-1.06L9 12.15Z" clipRule="evenodd" />
                      <path d="M21.75 12.75a.75.75 0 0 1-.75.75H3a.75.75 0 0 1 0-1.5h18a.75.75 0 0 1 .75.75Z" />
                    </svg>
                    Certifications
                  </h3>
                  <div className="space-y-3">
                    {selectedCandidate.certifications.map((cert, idx) => (
                      <div key={idx} className="bg-zinc-800/50 rounded-lg p-4 border border-zinc-700/50">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="font-semibold text-white text-base mb-1">{cert.certification || 'N/A'}</div>
                            <div className="text-zinc-300 text-sm mb-2">{cert.issuer || 'N/A'}</div>
                            {cert.endMonth && (
                              <div className="flex items-center gap-1 text-xs text-zinc-400">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">
                                  <path fillRule="evenodd" d="M6.75 2.25A.75.75 0 0 1 7.5 3v1.5h9V3a.75.75 0 0 1 1.5 0v1.5h1.5a3 3 0 0 1 3 3v11.25a3 3 0 0 1-3 3H5.25a3 3 0 0 1-3-3V7.5a3 3 0 0 1 3-3H6.75V3Zm-1.5 4.5v-.75a1.5 1.5 0 0 1 1.5-1.5h13.5a1.5 1.5 0 0 1 1.5 1.5v.75h-16.5Zm16.5 0H4.5v8.25a1.5 1.5 0 0 0 1.5 1.5h13.5a1.5 1.5 0 0 0 1.5-1.5V6.75Z" clipRule="evenodd" />
                                </svg>
                                Valid till: {cert.endMonth}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Resume */}
              <div>
                {(() => {
                  const resolvedResumeUrl = buildResumeUrl(selectedCandidate)
                  const hasResume = Boolean(selectedCandidate.resumeFileName || resolvedResumeUrl)
                  if (!hasResume) {
                    return (
                      <>
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 text-zinc-400">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                          </svg>
                          Resume
                        </h3>
                        <div className="bg-zinc-800/50 rounded-lg p-4 border border-zinc-700/50">
                          <p className="text-sm text-zinc-400">Candidate has not uploaded a resume.</p>
                        </div>
                      </>
                    )
                  }

                  return (
                    <>
                      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 text-zinc-400">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                        </svg>
                        Resume
                      </h3>
                      <div className="bg-zinc-800/50 rounded-lg p-4 border border-zinc-700/50">
                        <div className="flex flex-wrap gap-3">
                          <button
                            onClick={() => handleResumeAction({ ...selectedCandidate, resumeUrl: resolvedResumeUrl }, 'view')}
                            disabled={resumeAction.isLoading}
                            className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/60 rounded-lg text-white text-sm font-medium transition-all duration-200 shadow-lg hover:shadow-xl"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12s3.75-7.5 9.75-7.5 9.75 7.5 9.75 7.5-3.75 7.5-9.75 7.5S2.25 12 2.25 12Z" />
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
                            </svg>
                            <span>{resumeAction.isLoading ? 'Opening…' : 'View Resume'}</span>
                          </button>
                          <button
                            onClick={() => handleResumeAction({ ...selectedCandidate, resumeUrl: resolvedResumeUrl }, 'download')}
                            disabled={resumeAction.isLoading}
                            className="inline-flex items-center gap-2 px-5 py-2.5 bg-zinc-200 hover:bg-white text-zinc-900 rounded-lg text-sm font-medium transition-all duration-200 shadow-lg hover:shadow-xl disabled:bg-zinc-300"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                              <path fillRule="evenodd" d="M3 16.5a.75.75 0 0 1 .75.75v2.25h16.5V17.25a.75.75 0 0 1 1.5 0V20.25a1.5 1.5 0 0 1-1.5 1.5H3.75a1.5 1.5 0 0 1-1.5-1.5V17.25A.75.75 0 0 1 3 16.5Zm6.22-7.28a.75.75 0 0 0-1.06 1.06l3 3a.75.75 0 0 0 1.06 0l3-3a.75.75 0 0 0-1.06-1.06L12.75 11.94V3.75a.75.75 0 0 0-1.5 0v8.19L9.22 9.22Z" clipRule="evenodd" />
                            </svg>
                            <span>{resumeAction.isLoading ? 'Preparing…' : 'Download PDF'}</span>
                          </button>
                        </div>
                      </div>
                    </>
                  )
                })()}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

