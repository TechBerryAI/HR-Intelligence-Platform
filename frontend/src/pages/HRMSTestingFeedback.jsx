import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FiUser,
  FiMessageSquare,
  FiCheckCircle,
  FiSend,
  FiAlertTriangle,
  FiImage,
  FiLayers,
} from 'react-icons/fi'
import PremiumInput from '../components/PremiumInput.jsx'
import PremiumButton from '../components/PremiumButton.jsx'
import { useToast } from '../components/Toast.jsx'
import { useApp } from '../context/AppContext.jsx'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000'

const FEEDBACK_TYPES = [
  { value: 'Bug Report', label: 'Bug Report' },
  { value: 'Feature Request', label: 'Feature Request' },
  { value: 'General Feedback', label: 'General Feedback' },
  { value: 'Appreciation', label: 'Appreciation' },
]

const MODULES = [
  { value: 'Leave Management', label: 'Leave Management' },
  { value: 'Payroll', label: 'Payroll' },
  { value: 'Attendance', label: 'Attendance' },
  { value: 'Dashboard', label: 'Dashboard' },
  { value: 'Other', label: 'Other' },
]

const SEVERITIES = [
  { value: 'Low', label: 'Low' },
  { value: 'Medium', label: 'Medium' },
  { value: 'High', label: 'High' },
  { value: 'Critical', label: 'Critical' },
]

const ALLOWED_SCREENSHOT_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp']
const MAX_SCREENSHOT_SIZE = 5 * 1024 * 1024 // 5MB

export default function HRMSTestingFeedback() {
  const { user, auth, applicantProfile, applicantAuth } = useApp()
  const toast = useToast()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const isHrLoggedIn = auth.isLoggedIn && (auth.role === 'HR' || auth.role === 'head_hr')
  const isApplicantLoggedIn = applicantAuth.isLoggedIn && !isHrLoggedIn

  const defaultName = isApplicantLoggedIn
    ? applicantProfile?.fullName || ''
    : isHrLoggedIn
      ? user?.fullName || user?.name || ''
      : ''
  const defaultEmployeeId = isHrLoggedIn ? user?.hrId || '' : isApplicantLoggedIn ? applicantAuth?.userId || applicantProfile?.cid : ''

  const [form, setForm] = useState({
    employee_name: defaultName,
    employee_id: defaultEmployeeId,
    department: '',
    feedback_type: 'General Feedback',
    module: 'Other',
    severity: 'Medium',
    description: '',
  })
  const [screenshotFile, setScreenshotFile] = useState(null)
  const [screenshotError, setScreenshotError] = useState('')
  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (defaultName) setForm((prev) => ({ ...prev, employee_name: defaultName }))
    if (defaultEmployeeId) setForm((prev) => ({ ...prev, employee_id: defaultEmployeeId }))
  }, [defaultName, defaultEmployeeId])

  const updateField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: '' }))
  }

  const validate = () => {
    const newErrors = {}
    if (!form.employee_name.trim()) newErrors.employee_name = 'Employee name is required'
    if (!form.description.trim()) newErrors.description = 'Description is required'
    else if (form.description.trim().length < 10) newErrors.description = 'Please provide at least 10 characters'
    if (form.feedback_type === 'Bug Report' && !form.severity) newErrors.severity = 'Severity is required for bug reports'
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const onScreenshotChange = (e) => {
    const file = e.target.files?.[0]
    setScreenshotError('')
    setScreenshotFile(null)
    if (!file) return
    if (!ALLOWED_SCREENSHOT_TYPES.includes(file.type)) {
      setScreenshotError('Please choose an image (PNG, JPG, GIF, WebP)')
      return
    }
    if (file.size > MAX_SCREENSHOT_SIZE) {
      setScreenshotError('Image must be under 5MB')
      return
    }
    setScreenshotFile(file)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) {
      toast.error('Please fix the errors below')
      return
    }
    setIsSubmitting(true)
    try {
      let response
      if (screenshotFile) {
        const fd = new FormData()
        fd.append('employee_name', form.employee_name.trim())
        fd.append('employee_id', (form.employee_id || '').trim())
        fd.append('department', (form.department || '').trim())
        fd.append('feedback_type', form.feedback_type)
        fd.append('module', form.module)
        fd.append('description', form.description.trim())
        if (form.feedback_type === 'Bug Report') fd.append('severity', form.severity)
        fd.append('screenshot', screenshotFile)
        response = await fetch(`${API_BASE_URL}/api/feedback/submit`, {
          method: 'POST',
          body: fd,
        })
      } else {
        const payload = {
          employee_name: form.employee_name.trim(),
          employee_id: (form.employee_id || '').trim() || undefined,
          department: (form.department || '').trim() || undefined,
          feedback_type: form.feedback_type,
          module: form.module,
          description: form.description.trim(),
        }
        if (form.feedback_type === 'Bug Report') payload.severity = form.severity
        response = await fetch(`${API_BASE_URL}/api/feedback/submit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
      }
      const data = await response.json()
      if (response.ok && data.success) {
        setSubmitted(true)
        toast.success(data.message || 'Feedback submitted successfully.')
      } else {
        toast.error(data.error || 'Failed to submit feedback')
      }
    } catch (err) {
      console.error('Feedback submit error:', err)
      toast.error('An error occurred. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 py-8 sm:py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="text-center mb-8"
        >
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.15, type: 'spring', stiffness: 200, damping: 15 }}
            className="inline-block mb-3"
          >
            <div className="w-16 h-16 mx-auto rounded-full bg-gradient-to-r from-emerald-600 to-teal-600 flex items-center justify-center shadow-lg">
              <FiMessageSquare className="w-8 h-8 text-white" />
            </div>
          </motion.div>
          <h1 className="text-3xl sm:text-4xl font-bold bg-gradient-to-r from-white to-zinc-300 bg-clip-text text-transparent mb-2">
            HRMS Testing Feedback
          </h1>
          <p className="text-zinc-400 text-sm sm:text-base">
            Report bugs, suggest features, or share general feedback to help improve HRMS.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="glass-card rounded-2xl p-6 sm:p-8 border border-white/10"
        >
          <AnimatePresence mode="wait">
            {submitted ? (
              <motion.div
                key="success"
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.96 }}
                className="text-center py-10"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.15, type: 'spring', stiffness: 200, damping: 12 }}
                  className="inline-block mb-4"
                >
                  <div className="w-20 h-20 mx-auto rounded-full bg-emerald-500/20 flex items-center justify-center">
                    <FiCheckCircle className="w-10 h-10 text-emerald-500" />
                  </div>
                </motion.div>
                <h2 className="text-xl font-bold text-white mb-2">Thank you</h2>
                <p className="text-zinc-400 text-sm sm:text-base">
                  Your feedback has been recorded and will help improve HRMS.
                </p>
              </motion.div>
            ) : (
              <motion.form
                key="form"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onSubmit={handleSubmit}
                className="space-y-5"
              >
                <PremiumInput
                  label="Employee Name"
                  icon={FiUser}
                  type="text"
                  value={form.employee_name}
                  onChange={(e) => updateField('employee_name', e.target.value)}
                  error={errors.employee_name}
                  placeholder="Your full name"
                  required
                />
                <PremiumInput
                  label="Employee ID (optional)"
                  type="text"
                  value={form.employee_id}
                  onChange={(e) => updateField('employee_id', e.target.value)}
                  placeholder="e.g. HRID001"
                />
                <PremiumInput
                  label="Department (optional)"
                  type="text"
                  value={form.department}
                  onChange={(e) => updateField('department', e.target.value)}
                  placeholder="Your department"
                />

                <PremiumInput
                  label="Feedback Type"
                  icon={FiLayers}
                  as="select"
                  value={form.feedback_type}
                  onChange={(e) => updateField('feedback_type', e.target.value)}
                  required
                >
                  {FEEDBACK_TYPES.map((opt) => (
                    <option key={opt.value} value={opt.value} style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>
                      {opt.label}
                    </option>
                  ))}
                </PremiumInput>

                <PremiumInput
                  label="Affected Module"
                  as="select"
                  value={form.module}
                  onChange={(e) => updateField('module', e.target.value)}
                >
                  {MODULES.map((opt) => (
                    <option key={opt.value} value={opt.value} style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>
                      {opt.label}
                    </option>
                  ))}
                </PremiumInput>

                <PremiumInput
                  label="Description"
                  as="textarea"
                  value={form.description}
                  onChange={(e) => updateField('description', e.target.value)}
                  error={errors.description}
                  placeholder="Describe the issue, feature idea, or feedback in detail..."
                  rows={5}
                  className="resize-none"
                  required
                />

                {form.feedback_type === 'Bug Report' && (
                  <PremiumInput
                    label="Severity"
                    icon={FiAlertTriangle}
                    as="select"
                    value={form.severity}
                    onChange={(e) => updateField('severity', e.target.value)}
                    error={errors.severity}
                  >
                    {SEVERITIES.map((opt) => (
                      <option key={opt.value} value={opt.value} style={{ color: '#f3f4f6', backgroundColor: '#18181b' }}>
                        {opt.label}
                      </option>
                    ))}
                  </PremiumInput>
                )}

                <div>
                  <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                    <FiImage className="inline w-4 h-4 mr-1.5 text-zinc-400" />
                    Screenshot (optional)
                  </label>
                  <input
                    type="file"
                    accept=".png,.jpg,.jpeg,.gif,.webp,image/png,image/jpeg,image/gif,image/webp"
                    onChange={onScreenshotChange}
                    className="block w-full text-sm text-zinc-400 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-white/10 file:text-zinc-200 file:cursor-pointer hover:file:bg-white/15"
                  />
                  {screenshotFile && (
                    <p className="mt-1 text-xs text-zinc-500">{screenshotFile.name}</p>
                  )}
                  {screenshotError && (
                    <p className="mt-1 text-xs text-red-400">{screenshotError}</p>
                  )}
                </div>

                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                >
                  <PremiumButton type="submit" disabled={isSubmitting} className="w-full">
                    {isSubmitting ? (
                      <>
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                          className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full mr-2"
                        />
                        Submitting...
                      </>
                    ) : (
                      <>
                        <FiSend className="mr-2" />
                        Submit Feedback
                      </>
                    )}
                  </PremiumButton>
                </motion.div>
              </motion.form>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </div>
  )
}
