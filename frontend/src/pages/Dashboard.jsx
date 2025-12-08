import React, { useState, useEffect } from 'react'
import { useApp } from '../context/AppContext.jsx'

// Helper function to format date for display
const formatDisplayDate = (dateString) => {
  if (!dateString) return ''
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return dateString
  }
}

export default function Dashboard() {
  const { jobs, addJob, setJobEnabled, updateJob, user } = useApp()
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState(user?.company || '')
  const [location, setLocation] = useState('')
  const [salary, setSalary] = useState('')
  const [experienceFrom, setExperienceFrom] = useState('')
  const [experienceTo, setExperienceTo] = useState('')
  const [description, setDescription] = useState('')
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  // Edit state
  const [editingJobId, setEditingJobId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [editLocation, setEditLocation] = useState('')
  const [editSalary, setEditSalary] = useState('')
  const [editExperienceFrom, setEditExperienceFrom] = useState('')
  const [editExperienceTo, setEditExperienceTo] = useState('')
  const [editDescription, setEditDescription] = useState('')

  // Update company field when user data loads
  useEffect(() => {
    if (user?.company && !company) {
      setCompany(user.company)
    }
  }, [user])

  // Update company field when user data loads
  useEffect(() => {
    if (user?.company && !company) {
      setCompany(user.company)
    }
  }, [user])

  const onSubmit = async (e) => {
    e.preventDefault()
    addJob({ title, company, location, salary, experienceFrom, experienceTo, description })
    setTitle('')
    // Keep company field populated with admin's company after submission
    setCompany(user?.company || '')
    setLocation('')
    setSalary('')
    setExperienceFrom('')
    setExperienceTo('')
    setDescription('')
    setSuccess('Job posted! It now appears on the Jobs page.')
    setTimeout(() => setSuccess(''), 2500)
  }

  const handleEditClick = (job) => {
    setEditingJobId(job.id)
    setEditTitle(job.title || '')
    setEditLocation(job.location || '')
    setEditSalary(job.salary || '')
    setEditExperienceFrom(job.experienceFrom || '')
    setEditExperienceTo(job.experienceTo || '')
    setEditDescription(job.description || '')
  }

  const handleEditCancel = () => {
    setEditingJobId(null)
    setEditTitle('')
    setEditLocation('')
    setEditSalary('')
    setEditExperienceFrom('')
    setEditExperienceTo('')
    setEditDescription('')
  }

  const handleEditSubmit = (e) => {
    e.preventDefault()
    if (editingJobId) {
      updateJob(editingJobId, {
        title: editTitle,
        location: editLocation,
        salary: editSalary,
        experienceFrom: editExperienceFrom,
        experienceTo: editExperienceTo,
        description: editDescription,
      })
      setSuccess('Job updated successfully!')
      setTimeout(() => setSuccess(''), 2500)
      handleEditCancel()
    }
  }

  return (
    <section className="py-10">
      <div className="max-w-5xl mx-auto px-4">
        <h2 className="text-2xl font-bold text-gray-100">Job Posting Dashboard</h2>
        <p className="mt-1 text-sm text-zinc-400">Create a new job post</p>

        <form onSubmit={onSubmit} className="mt-6 bg-zinc-900 p-6 rounded-xl shadow-sm ring-1 ring-zinc-800 space-y-4">
          {success && <div className="text-green-400 text-sm">{success}</div>}
          {error && <div className="text-red-400 text-sm">{error}</div>}

          <div>
            <label className="block text-sm font-medium text-zinc-300">Job Title</label>
            <input
              className="mt-1 w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Senior React Developer"
              required
            />
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-300">Company</label>
              <input
                className="mt-1 w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Acme Corp"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-300">Location</label>
              <input
                className="mt-1 w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Bengaluru, KA"
                required
              />
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-zinc-300">Salary (optional)</label>
              <input
                className="mt-1 w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
                value={salary}
                onChange={(e) => setSalary(e.target.value)}
                placeholder="₹15-25 LPA"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-300">Experience range (years)</label>
              <div className="mt-1 grid grid-cols-2 gap-3">
                <input
                  type="number"
                  min="0"
                  className="w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
                  value={experienceFrom}
                  onChange={(e) => setExperienceFrom(e.target.value)}
                  placeholder="From (e.g., 0)"
                />
                <input
                  type="number"
                  min="0"
                  className="w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
                  value={experienceTo}
                  onChange={(e) => setExperienceTo(e.target.value)}
                  placeholder="To (e.g., 2)"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300">Description</label>
            <textarea
              className="mt-1 w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600 min-h-[120px]"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe responsibilities, requirements, and perks"
              required
            />
          </div>

          <div className="pt-2">
            <button 
              type="submit" 
              disabled={isSubmitting}
              className={`${isSubmitting ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-100'} bg-white text-black font-medium px-5 py-2.5 rounded-lg transition`}
            >
              {isSubmitting ? 'Posting...' : 'Post Job'}
            </button>
          </div>
        </form>

        {/* Jobs list with enable/disable slider */}
        <div className="mt-10">
          <h3 className="text-lg font-semibold text-gray-100">Your Job Posts</h3>
          <div className="mt-4 grid gap-4">
            {jobs.length === 0 ? (
              <div className="text-sm text-zinc-400">No jobs yet. Create one above.</div>
            ) : (
              jobs.map((job) => {
                const isDisabled = job.enabled === false
                return (
                  <div key={job.id} className={`relative rounded-xl ring-1 p-5 transition ${
                    isDisabled ? 'bg-zinc-900 ring-zinc-800 opacity-70' : 'bg-zinc-900 ring-zinc-800'
                  }`}>
                    {/* Toggle switch top-right */}
                    <label className="absolute top-4 right-4 inline-flex items-center cursor-pointer select-none">
                      <input
                        type="checkbox"
                        className="sr-only peer"
                        checked={job.enabled !== false}
                        onChange={(e) => setJobEnabled(job.id, e.target.checked)}
                      />
                      <span className={`mr-2 text-xs ${job.enabled === false ? 'text-zinc-500' : 'text-emerald-400'}`}>{job.enabled === false ? 'Disabled' : 'Enabled'}</span>
                      <span className="w-11 h-6 bg-zinc-700 rounded-full peer transition-colors relative peer-checked:bg-emerald-500">
                        <span className="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transform transition-transform peer-checked:translate-x-5" />
                      </span>
                    </label>

                    <div className="pr-28">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <h4 className={`text-base font-semibold ${isDisabled ? 'text-zinc-400' : 'text-white'}`}>{job.title}</h4>
                          <div className={`mt-1 text-sm ${isDisabled ? 'text-zinc-400' : 'text-zinc-300'}`}>{job.company}</div>
                          <div className={`mt-2 flex items-center gap-4 text-sm ${isDisabled ? 'text-zinc-500' : 'text-zinc-400'}`}>
                            <span>{job.location}</span>
                            {job.salary ? <span>{job.salary}</span> : null}
                            {job.experienceFrom || job.experienceTo ? (
                              <span>
                                {(job.experienceFrom ?? '')}{(job.experienceFrom || job.experienceTo) ? '-' : ''}{(job.experienceTo ?? '')} yrs
                              </span>
                            ) : null}
                          </div>
                          {job.postedOn && (
                            <div className={`mt-2 text-xs ${isDisabled ? 'text-zinc-500' : 'text-zinc-400'}`}>
                              <span className="inline-flex items-center gap-1">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3"><path d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25ZM12.75 6a.75.75 0 0 0-1.5 0v6c0 .414.336.75.75.75h4.5a.75.75 0 0 0 0-1.5h-3.75V6Z"/></svg>
                                Posted on {formatDisplayDate(job.postedOn)}
                              </span>
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => handleEditClick(job)}
                          className="text-sm font-medium px-3 py-1.5 rounded-lg transition bg-blue-600 hover:bg-blue-700 text-white"
                        >
                          Edit
                        </button>
                      </div>
                      {job.description ? (
                        <p className={`mt-3 text-sm ${isDisabled ? 'text-zinc-500' : 'text-zinc-300'}`}>{job.description}</p>
                      ) : null}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>

      {/* Edit Modal */}
      {editingJobId && (
        <div className="fixed inset-0 z-[200]">
          <div className="absolute inset-0 bg-black/60" onClick={handleEditCancel} />
          <div className="absolute inset-0 overflow-y-auto p-4 flex items-start justify-center">
            <div className="w-full max-w-2xl bg-zinc-900 ring-1 ring-zinc-800 rounded-xl shadow-xl mt-10 mb-10" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
                <h3 className="text-lg font-semibold text-white">Edit Job Post</h3>
                <button onClick={handleEditCancel} className="p-2 text-zinc-400 hover:text-white">✕</button>
              </div>

              <form onSubmit={handleEditSubmit} className="px-6 py-4 space-y-4">
                {success && <div className="text-green-400 text-sm">{success}</div>}

                <div>
                  <label className="block text-sm font-medium text-zinc-300">Job Title</label>
                  <input
                    className="mt-1 w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    placeholder="e.g., Senior React Developer"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-300">Location</label>
                  <input
                    className="mt-1 w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
                    value={editLocation}
                    onChange={(e) => setEditLocation(e.target.value)}
                    placeholder="Bengaluru, KA"
                    required
                  />
                </div>

                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-zinc-300">Salary (optional)</label>
                    <input
                      className="mt-1 w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
                      value={editSalary}
                      onChange={(e) => setEditSalary(e.target.value)}
                      placeholder="₹15-25 LPA"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-zinc-300">Experience range (years)</label>
                    <div className="mt-1 grid grid-cols-2 gap-3">
                      <input
                        type="number"
                        min="0"
                        className="w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
                        value={editExperienceFrom}
                        onChange={(e) => setEditExperienceFrom(e.target.value)}
                        placeholder="From (e.g., 0)"
                      />
                      <input
                        type="number"
                        min="0"
                        className="w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600"
                        value={editExperienceTo}
                        onChange={(e) => setEditExperienceTo(e.target.value)}
                        placeholder="To (e.g., 2)"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-300">Description</label>
                  <textarea
                    className="mt-1 w-full rounded-lg border-zinc-700 bg-zinc-800 text-gray-100 focus:ring-blue-600 focus:border-blue-600 min-h-[120px]"
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="Describe responsibilities, requirements, and perks"
                    required
                  />
                </div>

                <div className="flex gap-3 pt-2">
                  <button type="submit" className="bg-white hover:bg-gray-100 text-black font-medium px-5 py-2.5 rounded-lg transition">
                    Save Changes
                  </button>
                  <button type="button" onClick={handleEditCancel} className="bg-zinc-700 hover:bg-zinc-600 text-white font-medium px-5 py-2.5 rounded-lg transition">
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}


