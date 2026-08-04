import React, { useState, useEffect } from 'react'
import { useApp } from '@/core/context/AppContext.jsx'
import JDUploadWithParsing from '@/shared/components/JDUploadWithParsing.jsx'
import PremiumButton from '@/shared/components/PremiumButton.jsx'
import PremiumInput from '@/shared/components/PremiumInput.jsx'
import AnimatedContainer from '@/shared/components/AnimatedContainer.jsx'
import JobDescriptionView from '@/shared/components/JobDescriptionView.jsx'
import { Card } from '@/shared/components/ui/index.js'
import { motion, AnimatePresence } from 'framer-motion'
import { FiBriefcase, FiMapPin, FiClock, FiEdit2, FiX, FiCheck, FiAlertCircle, FiTrash2, FiEye } from 'react-icons/fi'

const formatDisplayDate = (dateString) => {
  if (!dateString) return ''
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return dateString
  }
}

export default function RecruiterJobDashboard({ embedded = false, onJobChange, hideJobList = false }) {
  const { jobs, addJob, updateJob, setJobEnabled, deleteJob, user } = useApp()
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState(user?.company || '')
  const [location, setLocation] = useState('')
  const [salary, setSalary] = useState('')
  const [experienceFrom, setExperienceFrom] = useState('')
  const [experienceTo, setExperienceTo] = useState('')
  const [description, setDescription] = useState('')
  const [keywords, setKeywords] = useState('')
  const [mandatorySkills, setMandatorySkills] = useState('')
  const [preferredSkills, setPreferredSkills] = useState('')
  const [parsedCompany, setParsedCompany] = useState('')
  const [parsedJdId, setParsedJdId] = useState(null)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [togglingJobId, setTogglingJobId] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [showPreview, setShowPreview] = useState(false)

  const [editingJobId, setEditingJobId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [editLocation, setEditLocation] = useState('')
  const [editSalary, setEditSalary] = useState('')
  const [editExperienceFrom, setEditExperienceFrom] = useState('')
  const [editExperienceTo, setEditExperienceTo] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editKeywords, setEditKeywords] = useState('')

  useEffect(() => {
    if (user?.company && (!company || company.trim() === '')) {
      setCompany(user.company)
    }
  }, [user?.company, company])

  useEffect(() => {
    if (!showPreview) return
    const onEscape = (e) => {
      if (e.key === 'Escape') setShowPreview(false)
    }
    window.addEventListener('keydown', onEscape)
    return () => window.removeEventListener('keydown', onEscape)
  }, [showPreview])

  const notifyChange = () => {
    onJobChange?.()
  }

  const handleToggleEnabled = async (job, nextEnabled) => {
    const jobId = job.id || job.jdid
    if (!jobId) return
    setTogglingJobId(jobId)
    setError('')
    try {
      const result = await setJobEnabled(jobId, nextEnabled)
      if (result?.success === false) {
        setError(result.error || 'Failed to update job status')
      } else {
        setSuccess(nextEnabled ? 'Job enabled' : 'Job disabled (draft)')
        setTimeout(() => setSuccess(''), 3000)
        notifyChange()
      }
    } finally {
      setTogglingJobId(null)
    }
  }

  const handleDeleteConfirm = async () => {
    if (!confirmDelete) return
    const jobId = confirmDelete.id || confirmDelete.jdid
    setDeleting(jobId)
    setError('')
    try {
      const result = await deleteJob(jobId)
      if (result?.success === false) {
        setError(result.error || 'Failed to delete job')
      } else {
        setSuccess('Job deleted successfully')
        setTimeout(() => setSuccess(''), 3000)
        notifyChange()
      }
    } finally {
      setDeleting(null)
      setConfirmDelete(null)
    }
  }

  const splitList = (value) =>
    String(value || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)

  const previewCompany = user?.company || company || ''
  const previewMandatory = splitList(mandatorySkills)
  const previewPreferred = splitList(preferredSkills)
  const previewKeywords = splitList(keywords)
  const previewExperience =
    experienceFrom || experienceTo
      ? `${[experienceFrom, experienceTo].filter((v) => v !== '' && v != null).join('–')} yrs`
      : ''

  const handleJDAutofill = (parsedData) => {
    setTitle(parsedData.title || '')
    setLocation(parsedData.location || '')
    setSalary(parsedData.salary || '')
    setExperienceFrom(parsedData.experienceFrom || '')
    setExperienceTo(parsedData.experienceTo || '')
    setDescription(parsedData.description || '')
    const kw = parsedData.keywords
      || (Array.isArray(parsedData._keywords) ? parsedData._keywords.join(', ') : '')
      || ''
    setKeywords(kw)
    setMandatorySkills(
      Array.isArray(parsedData.mandatorySkills)
        ? parsedData.mandatorySkills.join(', ')
        : (parsedData._mandatorySkills || []).join(', ') || '',
    )
    setPreferredSkills(
      Array.isArray(parsedData.preferredSkills)
        ? parsedData.preferredSkills.join(', ')
        : (parsedData._preferredSkills || []).join(', ') || '',
    )
    setParsedCompany(parsedData.company || '')
    if (parsedData._parsedId) {
      setParsedJdId(parsedData._parsedId)
    }
    // Keep HR account company as posting company; retain parsed company for display note
    setCompany(user?.company || parsedData.company || '')
    setError('')
    setSuccess(
      parsedData.company && user?.company && parsedData.company !== user.company
        ? `Job description parsed! Using your HR company (${user.company}). Parsed employer: ${parsedData.company}.`
        : 'Job description parsed! Please review the fields below.',
    )
    setTimeout(() => setSuccess(''), 5000)
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError('')
    try {
      const companyToUse = user?.company || company
      // Skills stay in their own fields — do not inject them into Description
      const mand = mandatorySkills.split(',').map((s) => s.trim()).filter(Boolean)
      const pref = preferredSkills.split(',').map((s) => s.trim()).filter(Boolean)
      const payload = {
        title,
        company: companyToUse,
        location,
        salary,
        experienceFrom,
        experienceTo,
        description: (description || '').trim(),
        keywords,
        mandatorySkills: mand,
        preferredSkills: pref,
      }
      if (parsedJdId) payload.parsedJdId = parsedJdId
      const result = await addJob(payload)
      if (!result?.success) {
        setError(result?.error || 'Failed to post job')
        return
      }
      setTitle('')
      setCompany(user?.company || '')
      setLocation('')
      setSalary('')
      setExperienceFrom('')
      setExperienceTo('')
      setDescription('')
      setKeywords('')
      setMandatorySkills('')
      setPreferredSkills('')
      setParsedCompany('')
      setParsedJdId(null)
      setSuccess('Job posted! It now appears in your job posts below.')
      setTimeout(() => setSuccess(''), 2500)
      notifyChange()
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
    setEditKeywords(job.keywords || '')
  }

  const handleEditCancel = () => {
    setEditingJobId(null)
    setEditTitle('')
    setEditLocation('')
    setEditSalary('')
    setEditExperienceFrom('')
    setEditExperienceTo('')
    setEditDescription('')
    setEditKeywords('')
  }

  const handleEditSubmit = async (e) => {
    e.preventDefault()
    if (!editingJobId) return
    await updateJob(editingJobId, {
      title: editTitle,
      location: editLocation,
      salary: editSalary,
      experienceFrom: editExperienceFrom,
      experienceTo: editExperienceTo,
      description: editDescription,
      keywords: editKeywords,
    })
    setSuccess('Job updated successfully!')
    setTimeout(() => setSuccess(''), 2500)
    handleEditCancel()
    notifyChange()
  }

  return (
    <div className={embedded ? 'min-w-0' : undefined}>
      {embedded && (
        <div className="mb-5">
          <h2 className="font-display text-[22px] font-semibold text-[var(--ei-text-primary)] tracking-tight">Job posting</h2>
          <p className="mt-1 text-sm text-[var(--ei-text-muted)]">Create and manage your job postings</p>
        </div>
      )}

      <AnimatedContainer animation="slideUp" delay={embedded ? 0 : 0.2}>
        <Card className={`space-y-6 ${embedded ? 'org-glass-panel p-6 sm:p-7 border-0 shadow-none hover:shadow-none bg-transparent' : 'p-8'}`}>
          <form id="recruiter-job-form" onSubmit={onSubmit} className="space-y-6">
            {success && (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className={`border px-5 py-4 rounded-xl flex items-center gap-3 ${
                  embedded
                    ? 'border-[rgba(54,214,160,0.3)] bg-[rgba(54,214,160,0.1)]'
                    : 'border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10'
                }`}
              >
                <FiCheck className={`w-5 h-5 flex-shrink-0 ${embedded ? 'text-[#36D6A0]' : 'text-emerald-600 dark:text-emerald-400'}`} />
                <span className={`text-sm font-medium ${embedded ? 'text-[#9AE6C8]' : 'text-emerald-700 dark:text-emerald-300'}`}>{success}</span>
              </motion.div>
            )}
            {error && (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className={`border px-5 py-4 rounded-xl flex items-center gap-3 ${
                  embedded
                    ? 'border-[rgba(255,102,133,0.3)] bg-[rgba(255,102,133,0.1)]'
                    : 'border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10'
                }`}
              >
                <FiAlertCircle className={`w-5 h-5 flex-shrink-0 ${embedded ? 'text-[#FF6685]' : 'text-red-600 dark:text-red-400'}`} />
                <span className={`text-sm font-medium ${embedded ? 'text-[#FF8FA3]' : 'text-red-700 dark:text-red-300'}`}>{error}</span>
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
                <label className={`block text-sm font-semibold mb-2 ${embedded ? 'text-[var(--ei-text-label)]' : 'text-slate-700 dark:text-slate-300'}`}>
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
              label="Required / Mandatory Skills"
              value={mandatorySkills}
              onChange={(e) => setMandatorySkills(e.target.value)}
              placeholder="Python, SQL, Docker (comma-separated)"
            />
            <PremiumInput
              label="Preferred Skills"
              value={preferredSkills}
              onChange={(e) => setPreferredSkills(e.target.value)}
              placeholder="Kubernetes, AWS (comma-separated)"
            />
            {parsedCompany ? (
              <p className={`text-xs ${embedded ? 'text-[#9FB2C4]' : 'text-slate-500'}`}>
                Parsed employer from JD: {parsedCompany}
                {parsedJdId ? ' · ATS will use linked parsed JD (re-parse if you change requirements significantly).' : ''}
              </p>
            ) : null}

            <PremiumInput
              label="Description"
              as="textarea"
              required
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe responsibilities, requirements, and perks"
              className="min-h-[120px] resize-y"
            />
            <PremiumInput
              label="Keywords"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="Python, RAG, GenAI (comma-separated)"
              helperText="Auto-filled from the job description — only JD-related terms"
            />

            <div className="pt-4 flex flex-wrap items-center gap-3">
              <PremiumButton
                type="button"
                variant="primary"
                icon={FiEye}
                disabled={isSubmitting}
                onClick={() => setShowPreview(true)}
                className={embedded ? '!bg-gradient-to-br !from-[#00A6FF] !to-[#276DFF] !shadow-[0_8px_24px_rgba(0,166,255,0.2)] rounded-xl min-h-[46px]' : ''}
              >
                Preview Post
              </PremiumButton>
              <PremiumButton
                type="submit"
                variant="primary"
                loading={isSubmitting}
                disabled={isSubmitting}
                className={embedded ? '!bg-gradient-to-br !from-[#00A6FF] !to-[#276DFF] !shadow-[0_8px_24px_rgba(0,166,255,0.2)] rounded-xl min-h-[46px]' : ''}
              >
                {isSubmitting ? 'Posting...' : 'Post Job'}
              </PremiumButton>
            </div>
          </form>
        </Card>
      </AnimatedContainer>

      {!hideJobList && (
      <AnimatedContainer animation="fadeIn" delay={embedded ? 0.1 : 0.4}>
        <div className={embedded ? 'mt-7' : 'mt-10'}>
          <h3 className={`text-lg font-semibold mb-4 ${embedded ? 'text-[var(--ei-text-primary)]' : 'text-slate-900 dark:text-[var(--ei-text-primary)]'}`}>Your Job Posts</h3>
          <div className="grid gap-4">
            {jobs.length === 0 ? (
              <Card className={`p-8 text-center ${embedded ? 'org-glass-panel border-0 shadow-none hover:shadow-none' : ''}`}>
                <div className={`w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center ${embedded ? 'bg-white/[0.05]' : 'bg-slate-100 dark:bg-slate-700'}`}>
                  <FiBriefcase className={`w-8 h-8 ${embedded ? 'text-[var(--ei-text-muted)]' : 'text-slate-500 dark:text-slate-400'}`} />
                </div>
                <p className={embedded ? 'text-[var(--ei-text-muted)]' : 'text-slate-500 dark:text-slate-400'}>No jobs yet. Create one above.</p>
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
                    className={`rounded-2xl p-6 border transition-all duration-[180ms] ${
                      embedded
                        ? `org-glass-card ${isDisabled ? 'opacity-60 hover:transform-none' : ''}`
                        : `bg-white dark:bg-slate-800/80 shadow-card dark:shadow-premium-dark ${
                            isDisabled ? 'border-slate-200 dark:border-slate-700 opacity-60' : 'border-slate-200 dark:border-slate-700 hover:shadow-card-hover'
                          }`
                    }`}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <h4 className={`text-lg font-semibold ${isDisabled ? 'text-[var(--ei-text-muted)]' : embedded ? 'text-[var(--ei-text-primary)]' : 'text-slate-900 dark:text-[var(--ei-text-primary)]'}`}>
                          {job.title}
                        </h4>
                        <p className={`text-sm ${isDisabled ? 'text-[var(--ei-text-muted)]' : embedded ? 'text-[var(--ei-text-muted)]' : 'text-slate-500 dark:text-slate-400'}`}>
                          {job.company}
                        </p>
                      </div>

                      <div className="flex items-center gap-2.5 shrink-0">
                        <label
                          className="inline-flex items-center cursor-pointer select-none"
                          title={isDisabled ? 'Disabled — click to enable' : 'Enabled — click to disable'}
                        >
                          <span className="sr-only">{isDisabled ? 'Disabled' : 'Enabled'}</span>
                          <input
                            type="checkbox"
                            className="sr-only"
                            checked={!isDisabled}
                            disabled={togglingJobId === (job.id || job.jdid)}
                            onChange={(e) => handleToggleEnabled(job, e.target.checked)}
                          />
                          <span
                            className={`relative inline-block w-11 h-6 shrink-0 rounded-full transition-colors ${
                              !isDisabled
                                ? embedded
                                  ? 'bg-emerald-500'
                                  : 'bg-emerald-500'
                                : embedded
                                  ? 'bg-white/20'
                                  : 'bg-slate-300 dark:bg-slate-600'
                            } ${togglingJobId === (job.id || job.jdid) ? 'opacity-60' : ''}`}
                            aria-hidden
                          >
                            <span
                              className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                                !isDisabled ? 'translate-x-5' : 'translate-x-0'
                              }`}
                            />
                          </span>
                        </label>
                        <PremiumButton
                          variant="secondary"
                          size="sm"
                          icon={FiEdit2}
                          onClick={() => handleEditClick(job)}
                          className={embedded ? '!bg-white/[0.05] !border-[var(--ei-border-primary)] !text-[var(--ei-text-primary)] hover:!bg-white/[0.09]' : ''}
                        >
                          Edit
                        </PremiumButton>
                        <button
                          type="button"
                          onClick={() => setConfirmDelete(job)}
                          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${
                            embedded
                              ? 'text-red-400 hover:bg-red-500/10 border-red-500/30'
                              : 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 border-red-200 dark:border-red-500/30'
                          }`}
                        >
                          <FiTrash2 className="w-3.5 h-3.5" />
                          Delete
                        </button>
                      </div>
                    </div>

                    <div className={`flex flex-wrap items-center gap-4 text-sm mb-4 ${isDisabled ? 'text-[var(--ei-text-muted)]' : embedded ? 'text-[var(--ei-text-muted)]' : 'text-slate-500 dark:text-slate-400'}`}>
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
                      <p className={`text-sm line-clamp-3 ${isDisabled ? 'text-[var(--ei-text-muted)]' : embedded ? 'text-[var(--ei-text-secondary)]' : 'text-slate-600 dark:text-slate-300'}`}>
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
      )}

      <AnimatePresence>
        {confirmDelete && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[210] flex items-center justify-center p-4"
          >
            <div className="absolute inset-0 bg-slate-900/50 dark:bg-black/60 backdrop-blur-sm" onClick={() => !deleting && setConfirmDelete(null)} />
            <motion.div
              initial={{ scale: 0.96, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.96, opacity: 0, y: 10 }}
              className={`relative w-full max-w-md rounded-2xl overflow-hidden border p-6 ${
                embedded
                  ? 'org-glass-panel border-[var(--ei-border-primary)]'
                  : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 shadow-premium'
              }`}
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className={`text-lg font-semibold ${embedded ? 'text-[var(--ei-text-primary)]' : 'text-slate-900 dark:text-[var(--ei-text-primary)]'}`}>
                Delete Job?
              </h3>
              <p className={`mt-2 text-sm ${embedded ? 'text-[var(--ei-text-secondary)]' : 'text-slate-600 dark:text-slate-400'}`}>
                This will permanently delete{' '}
                <span className={`font-medium ${embedded ? 'text-[var(--ei-text-primary)]' : 'text-slate-900 dark:text-[var(--ei-text-primary)]'}`}>
                  &quot;{confirmDelete.title}&quot;
                </span>
                . All associated applications will also be removed.
              </p>
              <div className="mt-5 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setConfirmDelete(null)}
                  disabled={Boolean(deleting)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    embedded
                      ? 'text-[var(--ei-text-primary)] hover:bg-white/10 border border-[var(--ei-border-primary)]'
                      : 'text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-600'
                  }`}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleDeleteConfirm}
                  disabled={deleting === (confirmDelete.id || confirmDelete.jdid)}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-500 disabled:opacity-50 transition-colors"
                >
                  {deleting === (confirmDelete.id || confirmDelete.jdid) ? 'Deleting…' : 'Delete'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

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
              className={`relative w-full max-w-2xl rounded-2xl overflow-hidden border ${
                embedded
                  ? 'org-glass-panel border-[var(--ei-border-primary)]'
                  : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 shadow-premium'
              }`}
              onClick={(e) => e.stopPropagation()}
            >
              <div className={`flex items-center justify-between px-6 py-4 border-b ${
                embedded ? 'border-[var(--ei-border-primary)] bg-white/[0.03]' : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80'
              }`}>
                <h3 className={`text-xl font-semibold ${embedded ? 'text-[var(--ei-text-primary)]' : 'text-slate-900 dark:text-[var(--ei-text-primary)]'}`}>Edit Job Post</h3>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleEditCancel}
                  className={`p-2 rounded-xl transition-colors ${
                    embedded
                      ? 'text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)] hover:bg-white/[0.05]'
                      : 'text-slate-400 hover:text-slate-600 dark:hover:text-[var(--ei-text-primary)] hover:bg-slate-100 dark:hover:bg-slate-700'
                  }`}
                >
                  <FiX className="w-5 h-5" />
                </motion.button>
              </div>

              <form onSubmit={handleEditSubmit} className="px-6 py-6 space-y-6 max-h-[70vh] overflow-y-auto bg-white dark:bg-slate-800">
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
                    <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">
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
                <PremiumInput
                  label="Keywords"
                  value={editKeywords}
                  onChange={(e) => setEditKeywords(e.target.value)}
                  placeholder="Python, RAG, GenAI (comma-separated)"
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

      <AnimatePresence>
        {showPreview && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[200] flex items-center justify-center p-4"
          >
            <div
              className="absolute inset-0 bg-slate-900/50 dark:bg-black/60 backdrop-blur-sm"
              onClick={() => setShowPreview(false)}
            />

            <motion.div
              initial={{ scale: 0.96, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.96, opacity: 0, y: 10 }}
              className="relative flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl"
              onClick={(e) => e.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-labelledby="job-preview-title"
            >
              <div className="flex-shrink-0 border-b border-slate-200 px-6 pb-4 pt-5">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <span className="inline-flex items-center gap-1.5 rounded-lg bg-sky-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-sky-700">
                    <FiEye className="h-3.5 w-3.5" />
                    Preview
                  </span>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    type="button"
                    onClick={() => setShowPreview(false)}
                    className="rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                    aria-label="Close preview"
                  >
                    <FiX className="h-5 w-5" />
                  </motion.button>
                </div>
                <h3 id="job-preview-title" className="text-xl font-semibold tracking-tight text-slate-900">
                  {title.trim() || 'Untitled role'}
                </h3>
                {previewCompany ? (
                  <p className="mt-1 text-sm text-slate-500">{previewCompany}</p>
                ) : null}
                <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-slate-500">
                  {location.trim() ? (
                    <span className="flex items-center gap-1.5">
                      <FiMapPin className="h-4 w-4" /> {location}
                    </span>
                  ) : null}
                  {salary.trim() ? <span>{salary}</span> : null}
                  {previewExperience ? (
                    <span className="flex items-center gap-1.5">
                      <FiBriefcase className="h-4 w-4" />
                      {previewExperience}
                    </span>
                  ) : null}
                  <span className="flex items-center gap-1.5">
                    <FiClock className="h-3.5 w-3.5" /> Posted today
                  </span>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
                {previewMandatory.length > 0 && (
                  <div>
                    <h4 className="mb-2 text-sm font-semibold text-slate-700">Required skills</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {previewMandatory.map((skill) => (
                        <span
                          key={`m-${skill}`}
                          className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-600"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {previewPreferred.length > 0 && (
                  <div>
                    <h4 className="mb-2 text-sm font-semibold text-slate-700">Preferred skills</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {previewPreferred.map((skill) => (
                        <span
                          key={`p-${skill}`}
                          className="rounded-md border border-slate-200 bg-white px-2 py-0.5 text-xs font-medium text-slate-600"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {previewKeywords.length > 0 && (
                  <div>
                    <h4 className="mb-2 text-sm font-semibold text-slate-700">Keywords</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {previewKeywords.map((kw) => (
                        <span
                          key={`k-${kw}`}
                          className="rounded-md border border-sky-100 bg-sky-50/80 px-2 py-0.5 text-xs font-medium text-sky-800"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <h4 className="mb-2 text-sm font-semibold text-slate-700">Description</h4>
                  <JobDescriptionView
                    description={description.trim() || 'No description provided yet.'}
                    textClassName="text-slate-600"
                  />
                </div>
              </div>

              <div className="flex-shrink-0 border-t border-slate-200 px-6 py-4 flex flex-col sm:flex-row gap-3 sm:justify-end">
                <PremiumButton
                  type="button"
                  variant="secondary"
                  onClick={() => setShowPreview(false)}
                  className="sm:min-w-[140px] min-h-[46px] rounded-xl"
                >
                  Close
                </PremiumButton>
                <PremiumButton
                  type="button"
                  variant="primary"
                  loading={isSubmitting}
                  disabled={isSubmitting}
                  onClick={() => {
                    setShowPreview(false)
                    // Submit the same form the Post Job button uses
                    const form = document.getElementById('recruiter-job-form')
                    form?.requestSubmit()
                  }}
                  className={`sm:min-w-[140px] ${embedded ? '!bg-gradient-to-br !from-[#00A6FF] !to-[#276DFF] !shadow-[0_8px_24px_rgba(0,166,255,0.2)] rounded-xl min-h-[46px]' : 'rounded-xl min-h-[46px]'}`}
                >
                  Post Job
                </PremiumButton>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
