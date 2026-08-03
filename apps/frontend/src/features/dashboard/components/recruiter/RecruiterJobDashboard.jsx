import React, { useState, useEffect } from 'react'
import { useApp } from '@/core/context/AppContext.jsx'
import JDUploadWithParsing from '@/shared/components/JDUploadWithParsing.jsx'
import PremiumButton from '@/shared/components/PremiumButton.jsx'
import PremiumInput from '@/shared/components/PremiumInput.jsx'
import AnimatedContainer from '@/shared/components/AnimatedContainer.jsx'
import { Card } from '@/shared/components/ui/index.js'
import { motion, AnimatePresence } from 'framer-motion'
import { FiBriefcase, FiMapPin, FiClock, FiEdit2, FiX, FiCheck, FiAlertCircle } from 'react-icons/fi'

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
  const { jobs, addJob, updateJob, user } = useApp()
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState(user?.company || '')
  const [location, setLocation] = useState('')
  const [salary, setSalary] = useState('')
  const [experienceFrom, setExperienceFrom] = useState('')
  const [experienceTo, setExperienceTo] = useState('')
  const [description, setDescription] = useState('')
  const [mandatorySkills, setMandatorySkills] = useState('')
  const [preferredSkills, setPreferredSkills] = useState('')
  const [parsedCompany, setParsedCompany] = useState('')
  const [parsedJdId, setParsedJdId] = useState(null)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [editingJobId, setEditingJobId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [editLocation, setEditLocation] = useState('')
  const [editSalary, setEditSalary] = useState('')
  const [editExperienceFrom, setEditExperienceFrom] = useState('')
  const [editExperienceTo, setEditExperienceTo] = useState('')
  const [editDescription, setEditDescription] = useState('')

  useEffect(() => {
    if (user?.company && (!company || company.trim() === '')) {
      setCompany(user.company)
    }
  }, [user?.company, company])

  const notifyChange = () => {
    onJobChange?.()
  }

  const handleJDAutofill = (parsedData) => {
    setTitle(parsedData.title || '')
    setLocation(parsedData.location || '')
    setSalary(parsedData.salary || '')
    setExperienceFrom(parsedData.experienceFrom || '')
    setExperienceTo(parsedData.experienceTo || '')
    setDescription(parsedData.description || '')
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
      // Keep description skill sections in sync with structured skill fields
      let descriptionToSend = description
      const mand = mandatorySkills.split(',').map((s) => s.trim()).filter(Boolean)
      const pref = preferredSkills.split(',').map((s) => s.trim()).filter(Boolean)
      if (mand.length || pref.length) {
        let body = descriptionToSend
        // Strip old skill sections then append current
        body = body.replace(/\*\*(?:Required|Mandatory|Preferred)\s*Skills?:\*\*[\s\S]*?(?=\n\*\*|\n*$)/gi, '').trim()
        if (mand.length) {
          body += `\n\n**Required Skills:**\n${mand.join(', ')}`
        }
        if (pref.length) {
          body += `\n\n**Preferred Skills:**\n${pref.join(', ')}`
        }
        descriptionToSend = body.trim()
      }
      const payload = {
        title,
        company: companyToUse,
        location,
        salary,
        experienceFrom,
        experienceTo,
        description: descriptionToSend,
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
          <h2 className="font-display text-[22px] font-semibold text-[#F5F7FA] tracking-tight">Job posting</h2>
          <p className="mt-1 text-sm text-[#8E9BA8]">Create and manage your job postings</p>
        </div>
      )}

      <AnimatedContainer animation="slideUp" delay={embedded ? 0 : 0.2}>
        <Card className={`space-y-6 ${embedded ? 'org-glass-panel p-6 sm:p-7 border-0 shadow-none hover:shadow-none bg-transparent' : 'p-8'}`}>
          <form onSubmit={onSubmit} className="space-y-6">
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
                <label className={`block text-sm font-semibold mb-2 ${embedded ? 'text-[#DCE3EA]' : 'text-slate-700 dark:text-slate-300'}`}>
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

            <div className="pt-4">
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
          <h3 className={`text-lg font-semibold mb-4 ${embedded ? 'text-[#F5F7FA]' : 'text-slate-900 dark:text-white'}`}>Your Job Posts</h3>
          <div className="grid gap-4">
            {jobs.length === 0 ? (
              <Card className={`p-8 text-center ${embedded ? 'org-glass-panel border-0 shadow-none hover:shadow-none' : ''}`}>
                <div className={`w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center ${embedded ? 'bg-white/[0.05]' : 'bg-slate-100 dark:bg-slate-700'}`}>
                  <FiBriefcase className={`w-8 h-8 ${embedded ? 'text-[#8E9BA8]' : 'text-slate-500 dark:text-slate-400'}`} />
                </div>
                <p className={embedded ? 'text-[#8E9BA8]' : 'text-slate-500 dark:text-slate-400'}>No jobs yet. Create one above.</p>
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
                        <h4 className={`text-lg font-semibold ${isDisabled ? 'text-[#71808E]' : embedded ? 'text-[#F5F7FA]' : 'text-slate-900 dark:text-white'}`}>
                          {job.title}
                        </h4>
                        <p className={`text-sm ${isDisabled ? 'text-[#71808E]' : embedded ? 'text-[#8E9BA8]' : 'text-slate-500 dark:text-slate-400'}`}>
                          {job.company}
                        </p>
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        <PremiumButton
                          variant="secondary"
                          size="sm"
                          icon={FiEdit2}
                          onClick={() => handleEditClick(job)}
                          className={embedded ? '!bg-white/[0.05] !border-white/10 !text-[#E8EDF3] hover:!bg-white/[0.09]' : ''}
                        >
                          Edit
                        </PremiumButton>
                      </div>
                    </div>

                    <div className={`flex flex-wrap items-center gap-4 text-sm mb-4 ${isDisabled ? 'text-[#71808E]' : embedded ? 'text-[#8E9BA8]' : 'text-slate-500 dark:text-slate-400'}`}>
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
                      <p className={`text-sm line-clamp-3 ${isDisabled ? 'text-[#71808E]' : embedded ? 'text-[#A0ABB6]' : 'text-slate-600 dark:text-slate-300'}`}>
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
                  ? 'org-glass-panel border-white/[0.08]'
                  : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 shadow-premium'
              }`}
              onClick={(e) => e.stopPropagation()}
            >
              <div className={`flex items-center justify-between px-6 py-4 border-b ${
                embedded ? 'border-white/[0.08] bg-white/[0.03]' : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80'
              }`}>
                <h3 className={`text-xl font-semibold ${embedded ? 'text-[#F5F7FA]' : 'text-slate-900 dark:text-white'}`}>Edit Job Post</h3>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleEditCancel}
                  className={`p-2 rounded-xl transition-colors ${
                    embedded
                      ? 'text-[#8E9BA8] hover:text-white hover:bg-white/[0.05]'
                      : 'text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-700'
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
    </div>
  )
}
