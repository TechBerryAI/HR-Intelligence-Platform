import React, { useState, useEffect } from 'react'
import { useApp } from '../context/AppContext.jsx'
import { apiRequest } from '../utils/api.js'
import { tokenService } from '../utils/tokenService.js'
import JDUploadWithParsing from '../components/JDUploadWithParsing.jsx'
import PasswordInput from '../components/PasswordInput.jsx'
import PremiumButton from '../components/PremiumButton.jsx'
import PremiumInput from '../components/PremiumInput.jsx'
import AnimatedContainer from '../components/AnimatedContainer.jsx'
import { StatCard, Card, CardHeader, CardTitle, CardContent, Modal } from '../components/ui/index.js'
import { PageContainer } from '../components/PageContainer.jsx'
import { motion, AnimatePresence } from 'framer-motion'
import { FiBriefcase, FiMapPin, FiClock, FiEdit2, FiX, FiCheck, FiAlertCircle, FiPlus, FiUsers, FiLayers } from 'react-icons/fi'

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
  const { jobs, addJob, setJobEnabled, updateJob, user, auth } = useApp()
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

  const isHeadHr = auth?.role === 'head_hr'
  const [showCreateAdmin, setShowCreateAdmin] = useState(false)
  const [createAdminForm, setCreateAdminForm] = useState({ email: '', fullName: '', company: '', password: '' })
  const [creatingAdmin, setCreatingAdmin] = useState(false)
  const [createAdminToast, setCreateAdminToast] = useState(null)

  const showCreateAdminToast = (msg, type = 'success') => {
    setCreateAdminToast({ msg, type })
    setTimeout(() => setCreateAdminToast(null), 3000)
  }

  const handleCreateAdmin = async (e) => {
    e.preventDefault()
    if (!createAdminForm.email?.trim() || !createAdminForm.fullName?.trim() || !createAdminForm.company?.trim() || !createAdminForm.password || createAdminForm.password.length < 6) {
      showCreateAdminToast('Please fill all fields; password must be at least 6 characters', 'error')
      return
    }
    setCreatingAdmin(true)
    try {
      const token = tokenService.getToken()
      await apiRequest('/api/super-admin/admins', {
        method: 'POST',
        token,
        body: {
          email: createAdminForm.email.trim().toLowerCase(),
          fullName: createAdminForm.fullName.trim(),
          company: createAdminForm.company.trim(),
          password: createAdminForm.password,
        },
      })
      setShowCreateAdmin(false)
      setCreateAdminForm({ email: '', fullName: '', company: '', password: '' })
      showCreateAdminToast('Admin account created successfully')
    } catch (err) {
      showCreateAdminToast(err?.message || 'Failed to create admin', 'error')
    } finally {
      setCreatingAdmin(false)
    }
  }

  // Always ensure company field is set to user's company when user data loads
  useEffect(() => {
    if (user?.company) {
      // Set company to user's company if it's empty or not set
      if (!company || company.trim() === '') {
        setCompany(user.company)
      }
    }
  }, [user?.company]) // Only depend on user.company to avoid infinite loops

  // Handle JD autofill from parsing (company is never changed — always from HR account)
  const handleJDAutofill = (parsedData) => {
    setTitle(parsedData.title || '');
    setLocation(parsedData.location || '');
    setSalary(parsedData.salary || '');
    setExperienceFrom(parsedData.experienceFrom || '');
    setExperienceTo(parsedData.experienceTo || '');
    setDescription(parsedData.description || '');
    // Keep company as the logged-in HR's company; do not overwrite with parsed JD
    setCompany(user?.company || '');
    setSuccess('Job description parsed! Please review the fields below.');
    setTimeout(() => setSuccess(''), 5000);
  };

  const onSubmit = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      const companyToUse = user?.company || company
      await addJob({ title, company: companyToUse, location, salary, experienceFrom, experienceTo, description })
      setTitle('')
      setCompany(user?.company || '')
      setLocation('')
      setSalary('')
      setExperienceFrom('')
      setExperienceTo('')
      setDescription('')
      setSuccess('Job posted! It now appears on the Jobs page.')
      setTimeout(() => setSuccess(''), 2500)
    } finally {
      setIsSubmitting(false)
    }
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

  const activeJobs = jobs.filter((j) => j.enabled !== false).length

  return (
    <PageContainer className="max-w-5xl">
      <AnimatedContainer animation="slideDown">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-3xl font-bold text-slate-900">Job Posting Dashboard</h2>
            <p className="mt-1 text-slate-500">Create and manage your job postings</p>
          </div>
            {isHeadHr && (
              <button
                type="button"
                onClick={() => setShowCreateAdmin(true)}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md transition-colors"
              >
                <FiPlus className="w-4 h-4" />
                Create Admin
              </button>
            )}
          </div>
        </AnimatedContainer>

        {/* Stat cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
          <StatCard title="Total jobs" value={jobs.length} icon={FiBriefcase} />
          <StatCard title="Active" value={activeJobs} subtitle="Currently visible" icon={FiLayers} />
        </div>

        {createAdminToast && (
          <div
            className={`fixed top-20 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-xl shadow-md text-sm font-medium border ${
              createAdminToast.type === 'error'
                ? 'bg-red-50 border-red-200 text-red-700'
                : 'bg-emerald-50 border-emerald-200 text-emerald-700'
            }`}
          >
            {createAdminToast.msg}
          </div>
        )}

        <Modal open={showCreateAdmin} onClose={() => { setShowCreateAdmin(false); setCreateAdminForm({ email: '', fullName: '', company: '', password: '' }) }} title="Create Admin Account" size="md">
          <p className="text-sm text-slate-500 mb-6">New HR admin can log in and create jobs, manage candidates.</p>
          <form onSubmit={handleCreateAdmin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input
                type="email"
                value={createAdminForm.email}
                onChange={(e) => setCreateAdminForm((f) => ({ ...f, email: e.target.value }))}
                className="input-premium"
                placeholder="hr@company.com"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Full name</label>
              <input
                type="text"
                value={createAdminForm.fullName}
                onChange={(e) => setCreateAdminForm((f) => ({ ...f, fullName: e.target.value }))}
                className="input-premium"
                placeholder="Jane Doe"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Company</label>
              <input
                type="text"
                value={createAdminForm.company}
                onChange={(e) => setCreateAdminForm((f) => ({ ...f, company: e.target.value }))}
                className="input-premium"
                placeholder="Acme Inc"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Password (min 6 characters)</label>
              <PasswordInput
                value={createAdminForm.password}
                onChange={(e) => setCreateAdminForm((f) => ({ ...f, password: e.target.value }))}
                className="input-premium"
                placeholder="••••••••"
                minLength={6}
                required
              />
            </div>
            <div className="flex gap-3 justify-end pt-2">
              <button
                type="button"
                onClick={() => { setShowCreateAdmin(false); setCreateAdminForm({ email: '', fullName: '', company: '', password: '' }) }}
                className="px-4 py-2.5 rounded-xl text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creatingAdmin}
                className="px-4 py-2.5 rounded-xl text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 transition-colors"
              >
                {creatingAdmin ? 'Creating…' : 'Create'}
              </button>
            </div>
          </form>
        </Modal>

        <AnimatedContainer animation="slideUp" delay={0.2}>
          <Card className="p-8 space-y-6">
          <form onSubmit={onSubmit} className="space-y-6">
            {success && (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="border border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10 px-5 py-4 rounded-xl flex items-center gap-3"
              >
                <FiCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
                <span className="text-sm font-medium text-emerald-700 dark:text-emerald-300">{success}</span>
              </motion.div>
            )}
            {error && (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="border border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10 px-5 py-4 rounded-xl flex items-center gap-3"
              >
                <FiAlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0" />
                <span className="text-sm font-medium text-red-700 dark:text-red-300">{error}</span>
              </motion.div>
            )}

            <JDUploadWithParsing onAutofill={handleJDAutofill} />

            <PremiumInput
              label="Job Title"
              icon={FiBriefcase}
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Senior React Developer"
            />

            <div className="grid sm:grid-cols-2 gap-6">
              <PremiumInput
                label="Company"
                icon={FiBriefcase}
                required
                value={user?.company || company}
                readOnly
                placeholder="From your account"
                title="Company is set from your HR account and cannot be changed here."
              />
              <PremiumInput
                label="Location"
                icon={FiMapPin}
                required
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Bengaluru, KA"
              />
            </div>

            <div className="grid sm:grid-cols-2 gap-6">
              <PremiumInput
                label="Salary (optional)"
                value={salary}
                onChange={(e) => setSalary(e.target.value)}
                placeholder="₹15-25 LPA"
              />
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Experience Range (years)
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <input
                    type="number"
                    min="0"
                    className="premium-input"
                    value={experienceFrom}
                    onChange={(e) => setExperienceFrom(e.target.value)}
                    placeholder="From (e.g., 0)"
                  />
                  <input
                    type="number"
                    min="0"
                    className="premium-input"
                    value={experienceTo}
                    onChange={(e) => setExperienceTo(e.target.value)}
                    placeholder="To (e.g., 2)"
                  />
                </div>
              </div>
            </div>

            <PremiumInput
              label="Description"
              as="textarea"
              required
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe responsibilities, requirements, and perks"
              className="min-h-[120px] resize-y"
            />

            <div className="pt-4">
              <PremiumButton
                type="submit"
                variant="primary"
                loading={isSubmitting}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Posting...' : 'Post Job'}
              </PremiumButton>
            </div>
          </form>
          </Card>
        </AnimatedContainer>

        {/* Jobs list */}
        <AnimatedContainer animation="fadeIn" delay={0.4}>
          <div className="mt-10">
            <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-6">Your Job Posts</h3>
            <div className="grid gap-4">
              {jobs.length === 0 ? (
                <Card className="p-8 text-center">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-100 dark:bg-slate-700 flex items-center justify-center">
                    <FiBriefcase className="w-8 h-8 text-slate-500 dark:text-slate-400" />
                  </div>
                  <p className="text-slate-500 dark:text-slate-400">No jobs yet. Create one above.</p>
                </Card>
              ) : (
                jobs.map((job, index) => {
                  const isDisabled = job.enabled === false
                  return (
                    <motion.div
                      key={job.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className={`rounded-2xl p-6 border bg-white dark:bg-slate-800/80 transition-all duration-300 shadow-card dark:shadow-premium-dark ${
                        isDisabled ? 'border-slate-200 dark:border-slate-700 opacity-60' : 'border-slate-200 dark:border-slate-700 hover:shadow-card-hover'
                      }`}
                    >
                      {/* Toggle switch */}
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex-1">
                          <h4 className={`text-lg font-semibold ${isDisabled ? 'text-slate-400' : 'text-slate-900 dark:text-white'}`}>
                            {job.title}
                          </h4>
                          <p className={`text-sm ${isDisabled ? 'text-slate-400' : 'text-slate-500 dark:text-slate-400'}`}>
                            {job.company}
                          </p>
                        </div>
                        
                        <div className="flex items-center gap-3">
                          <motion.label
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            className="inline-flex items-center gap-2 cursor-pointer select-none"
                          >
                            <span className={`text-xs font-medium ${job.enabled === false ? 'text-slate-500' : 'text-emerald-600 dark:text-emerald-400'}`}>
                              {job.enabled === false ? 'Disabled' : 'Enabled'}
                            </span>
                            <input
                              type="checkbox"
                              className="sr-only peer"
                              checked={job.enabled !== false}
                              onChange={(e) => setJobEnabled(job.id, e.target.checked)}
                            />
                            <div className={`relative w-11 h-6 rounded-full transition-colors ${
                              job.enabled === false ? 'bg-slate-300 dark:bg-slate-600' : 'bg-emerald-500'
                            }`}>
                              <motion.div
                                animate={{ x: job.enabled === false ? 2 : 22 }}
                                transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                                className="absolute top-0.5 w-5 h-5 bg-white rounded-full shadow"
                              />
                            </div>
                          </motion.label>
                          
                          <PremiumButton
                            variant="secondary"
                            size="sm"
                            icon={FiEdit2}
                            onClick={() => handleEditClick(job)}
                          >
                            Edit
                          </PremiumButton>
                        </div>
                      </div>

                      <div className={`flex flex-wrap items-center gap-4 text-sm mb-4 ${isDisabled ? 'text-slate-400' : 'text-slate-500 dark:text-slate-400'}`}>
                        <div className="flex items-center gap-1">
                          <FiMapPin className="w-4 h-4" />
                          <span>{job.location}</span>
                        </div>
                        {job.salary && (
                          <div className="flex items-center gap-1">
                            <span>{job.salary}</span>
                          </div>
                        )}
                        {(job.experienceFrom || job.experienceTo) && (
                          <div className="flex items-center gap-1">
                            <FiClock className="w-4 h-4" />
                            <span>
                              {job.experienceFrom ?? ''}{(job.experienceFrom || job.experienceTo) ? '-' : ''}{job.experienceTo ?? ''} yrs
                            </span>
                          </div>
                        )}
                        {job.postedOn && (
                          <div className="flex items-center gap-1 text-xs">
                            <FiClock className="w-3 h-3" />
                            <span>Posted {formatDisplayDate(job.postedOn)}</span>
                          </div>
                        )}
                      </div>

                      {job.description && (
                        <p className={`text-sm ${isDisabled ? 'text-slate-400' : 'text-slate-600 dark:text-slate-300'} line-clamp-3`}>
                          {job.description}
                        </p>
                      )}
                    </motion.div>
                  )
                })
              )}
            </div>
          </div>
        </AnimatedContainer>

      {/* Edit Modal */}
      <AnimatePresence>
        {editingJobId && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[200] flex items-center justify-center p-4"
          >
            <div className="absolute inset-0 bg-slate-900/50 dark:bg-black/60 backdrop-blur-sm" onClick={handleEditCancel} />
            
            <motion.div
              initial={{ scale: 0.96, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.96, opacity: 0, y: 10 }}
              className="relative w-full max-w-2xl rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-premium overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80">
                <h3 className="text-xl font-semibold text-slate-900 dark:text-white">Edit Job Post</h3>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleEditCancel}
                  className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                >
                  <FiX className="w-5 h-5" />
                </motion.button>
              </div>

              <form onSubmit={handleEditSubmit} className="px-6 py-6 space-y-6 max-h-[70vh] overflow-y-auto bg-white dark:bg-slate-800">
                {success && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="border border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10 px-4 py-3 rounded-xl flex items-center gap-2"
                  >
                    <FiCheck className="w-4 h-4 text-emerald-600" />
                    <span className="text-sm text-emerald-700 dark:text-emerald-300">{success}</span>
                  </motion.div>
                )}

                <PremiumInput
                  label="Job Title"
                  icon={FiBriefcase}
                  required
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  placeholder="e.g., Senior React Developer"
                />

                <PremiumInput
                  label="Location"
                  icon={FiMapPin}
                  required
                  value={editLocation}
                  onChange={(e) => setEditLocation(e.target.value)}
                  placeholder="Bengaluru, KA"
                />

                <div className="grid sm:grid-cols-2 gap-6">
                  <PremiumInput
                    label="Salary (optional)"
                    value={editSalary}
                    onChange={(e) => setEditSalary(e.target.value)}
                    placeholder="₹15-25 LPA"
                  />
                  <div>
                    <label className="block text-sm font-medium text-zinc-300 mb-2">
                      Experience Range (years)
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      <input
                        type="number"
                        min="0"
                        className="premium-input"
                        value={editExperienceFrom}
                        onChange={(e) => setEditExperienceFrom(e.target.value)}
                        placeholder="From"
                      />
                      <input
                        type="number"
                        min="0"
                        className="premium-input"
                        value={editExperienceTo}
                        onChange={(e) => setEditExperienceTo(e.target.value)}
                        placeholder="To"
                      />
                    </div>
                  </div>
                </div>

                <PremiumInput
                  label="Description"
                  as="textarea"
                  required
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Describe responsibilities, requirements, and perks"
                  className="min-h-[120px] resize-y"
                />

                <div className="flex gap-3 pt-2">
                  <PremiumButton type="submit" variant="primary">
                    Save Changes
                  </PremiumButton>
                  <PremiumButton type="button" variant="secondary" onClick={handleEditCancel}>
                    Cancel
                  </PremiumButton>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </PageContainer>
  )
}
