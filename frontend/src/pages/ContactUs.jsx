import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FiUser, FiMail, FiAlertCircle, FiMessageSquare, FiCheckCircle, FiSend } from 'react-icons/fi'
import PremiumInput from '../components/PremiumInput.jsx'
import PremiumButton from '../components/PremiumButton.jsx'
import { useToast } from '../components/Toast.jsx'
import { useApp } from '../context/AppContext.jsx'

export default function ContactUs() {
  const { applicantProfile, user, auth, applicantAuth } = useApp()
  const toast = useToast()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [requestId, setRequestId] = useState(null)

  // Determine user info based on who's logged in
  const isHrLoggedIn = auth.isLoggedIn && auth.role === 'HR'
  const isApplicantLoggedIn = applicantAuth.isLoggedIn && !isHrLoggedIn

  const defaultName = isApplicantLoggedIn 
    ? applicantProfile.fullName || '' 
    : isHrLoggedIn 
      ? user?.fullName || user?.name || '' 
      : ''
  
  const defaultEmail = isApplicantLoggedIn 
    ? applicantProfile.email || '' 
    : isHrLoggedIn 
      ? user?.email || '' 
      : ''

  const [form, setForm] = useState({
    name: defaultName,
    email: defaultEmail,
    subject: '',
    message: '',
    priority: 'medium'
  })

  const [errors, setErrors] = useState({})

  const updateField = (key, value) => {
    setForm(prev => ({ ...prev, [key]: value }))
    // Clear error when user starts typing
    if (errors[key]) {
      setErrors(prev => ({ ...prev, [key]: '' }))
    }
  }

  const validate = () => {
    const newErrors = {}
    
    if (!form.name.trim()) {
      newErrors.name = 'Name is required'
    }
    
    if (!form.email.trim()) {
      newErrors.email = 'Email is required'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      newErrors.email = 'Please enter a valid email address'
    }
    
    if (!form.subject.trim()) {
      newErrors.subject = 'Subject is required'
    }
    
    if (!form.message.trim()) {
      newErrors.message = 'Message is required'
    } else if (form.message.trim().length < 10) {
      newErrors.message = 'Message must be at least 10 characters'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!validate()) {
      toast.error('Please fix the errors in the form')
      return
    }

    setIsSubmitting(true)
    try {
      const payload = {
        name: form.name.trim(),
        email: form.email.trim(),
        subject: form.subject.trim(),
        message: form.message.trim(),
        priority: form.priority
      }

      // Add user info if logged in
      if (isApplicantLoggedIn) {
        payload.user_type = 'candidate'
        payload.user_id = applicantProfile.cid || applicantAuth.userId
      } else if (isHrLoggedIn) {
        payload.user_type = 'hr'
        payload.user_id = user?.hrid || auth.userId
      } else {
        payload.user_type = 'guest'
      }

      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000'
      const response = await fetch(`${API_BASE_URL}/api/support/submit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      const data = await response.json()

      if (response.ok && data.success) {
        setSubmitted(true)
        setRequestId(data.request_id)
        toast.success('Support request submitted successfully!')
        
        // Reset form after 3 seconds
        setTimeout(() => {
          setForm({
            name: defaultName,
            email: defaultEmail,
            subject: '',
            message: '',
            priority: 'medium'
          })
          setSubmitted(false)
          setRequestId(null)
        }, 5000)
      } else {
        toast.error(data.error || 'Failed to submit support request')
      }
    } catch (error) {
      console.error('Support request error:', error)
      toast.error('An error occurred. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 200, damping: 15 }}
            className="inline-block mb-4"
          >
            <div className="w-20 h-20 mx-auto rounded-full bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center shadow-glow">
              <FiMessageSquare className="w-10 h-10 text-white" />
            </div>
          </motion.div>
          
          <h1 className="text-4xl font-bold bg-gradient-to-r from-white to-zinc-300 bg-clip-text text-transparent mb-3">
            Contact Us
          </h1>
          <p className="text-zinc-400 text-lg">
            We're here to help! Tell us about any issues or questions you have.
          </p>
        </motion.div>

        {/* Form */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="glass-card rounded-2xl p-8 border border-white/10"
        >
          <AnimatePresence mode="wait">
            {submitted ? (
              <motion.div
                key="success"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="text-center py-12"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: 'spring', stiffness: 200, damping: 10 }}
                  className="inline-block mb-6"
                >
                  <div className="w-24 h-24 mx-auto rounded-full bg-green-500/20 flex items-center justify-center">
                    <FiCheckCircle className="w-12 h-12 text-green-500" />
                  </div>
                </motion.div>
                
                <h2 className="text-2xl font-bold text-white mb-3">
                  Request Submitted Successfully!
                </h2>
                <p className="text-zinc-400 mb-2">
                  Thank you for contacting us. We've received your support request.
                </p>
                {requestId && (
                  <p className="text-sm text-zinc-500">
                    Request ID: <span className="text-purple-400 font-mono">#{requestId}</span>
                  </p>
                )}
                <p className="text-zinc-400 mt-4">
                  We'll get back to you as soon as possible at{' '}
                  <span className="text-purple-400">{form.email}</span>
                </p>
              </motion.div>
            ) : (
              <motion.form
                key="form"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onSubmit={handleSubmit}
                className="space-y-6"
              >
                {/* Name */}
                <PremiumInput
                  label="Your Name"
                  icon={FiUser}
                  type="text"
                  value={form.name}
                  onChange={(e) => updateField('name', e.target.value)}
                  error={errors.name}
                  placeholder="Enter your full name"
                  required
                />

                {/* Email */}
                <PremiumInput
                  label="Email Address"
                  icon={FiMail}
                  type="email"
                  value={form.email}
                  onChange={(e) => updateField('email', e.target.value)}
                  error={errors.email}
                  placeholder="your.email@example.com"
                  helperText="We'll use this to respond to your request"
                  required
                />

                {/* Priority */}
                <PremiumInput
                  label="Priority Level"
                  icon={FiAlertCircle}
                  as="select"
                  value={form.priority}
                  onChange={(e) => updateField('priority', e.target.value)}
                  helperText="Help us understand how urgent your issue is"
                >
                  <option value="low">Low - General inquiry</option>
                  <option value="medium">Medium - Need assistance</option>
                  <option value="high">High - Important issue</option>
                  <option value="urgent">Urgent - Critical problem</option>
                </PremiumInput>

                {/* Subject */}
                <PremiumInput
                  label="Subject"
                  type="text"
                  value={form.subject}
                  onChange={(e) => updateField('subject', e.target.value)}
                  error={errors.subject}
                  placeholder="Brief description of your issue"
                  required
                />

                {/* Message */}
                <PremiumInput
                  label="Message"
                  as="textarea"
                  value={form.message}
                  onChange={(e) => updateField('message', e.target.value)}
                  error={errors.message}
                  placeholder="Describe your issue or question in detail..."
                  rows={6}
                  className="resize-none"
                  helperText="Please provide as much detail as possible"
                  required
                />

                {/* Submit Button */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                >
                  <PremiumButton
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full"
                  >
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
                        Submit Support Request
                      </>
                    )}
                  </PremiumButton>
                </motion.div>
              </motion.form>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Info Cards */}
        {!submitted && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="mt-8 grid md:grid-cols-3 gap-4"
          >
            <div className="glass-card p-4 rounded-xl border border-white/10 text-center">
              <div className="text-2xl mb-2">⚡</div>
              <h3 className="text-sm font-semibold text-white mb-1">Quick Response</h3>
              <p className="text-xs text-zinc-400">We typically respond within 24 hours</p>
            </div>
            
            <div className="glass-card p-4 rounded-xl border border-white/10 text-center">
              <div className="text-2xl mb-2">🔒</div>
              <h3 className="text-sm font-semibold text-white mb-1">Privacy First</h3>
              <p className="text-xs text-zinc-400">Your information is kept secure</p>
            </div>
            
            <div className="glass-card p-4 rounded-xl border border-white/10 text-center">
              <div className="text-2xl mb-2">💬</div>
              <h3 className="text-sm font-semibold text-white mb-1">Friendly Support</h3>
              <p className="text-xs text-zinc-400">We're here to help you succeed</p>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}

