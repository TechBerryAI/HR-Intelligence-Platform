import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FiChevronDown, FiHelpCircle, FiMessageCircle } from 'react-icons/fi'
import { useNavigate } from 'react-router-dom'
import PremiumButton from '@/shared/components/PremiumButton.jsx'

const faqs = [
  {
    category: 'General',
    questions: [
      {
        question: 'What is HR Intelligence?',
        answer:
          'HR Intelligence is an enterprise platform that connects job seekers with employers. Candidates can browse jobs, upload a resume to autofill an apply form, and submit applications directly — no account required. HR professionals can post job openings and manage applications.',
      },
      {
        question: 'Is this service free to use?',
        answer:
          'Yes! Job seekers can apply for jobs completely free without creating an account. Employers can post jobs and review applications at no cost.',
      },
      {
        question: 'How do I get started?',
        answer:
          'Browse Jobs and click Apply on a role. Upload your resume to autofill the form, review the details, and submit. HR staff can use Login for the admin portal.',
      },
    ],
  },
  {
    category: 'For Job Seekers',
    questions: [
      {
        question: 'Do I need an account to apply?',
        answer:
          'No. Click Apply on a job, fill the form (or upload a resume for AI autofill), and submit. Your application is stored for recruiters to review.',
      },
      {
        question: 'Can I upload my resume?',
        answer:
          'Yes! Upload a PDF or DOCX resume on the apply form. Our system parses it with AI and autofills your details, which you can review and edit before submitting.',
      },
      {
        question: 'How do I apply for a job?',
        answer:
          'Browse available jobs, click Apply, upload your resume or fill the form, then submit. Recruiters will review your application from their dashboard.',
      },
      {
        question: 'Can I track my application status?',
        answer:
          'Application status is managed by recruiters in their dashboard. After you apply, they will contact you using the email you provided on the form.',
      },
    ],
  },
  {
    category: 'For HR Professionals',
    questions: [
      {
        question: 'How do I post a job opening?',
        answer:
          'After logging in as an HR professional, go to your dashboard and click "Post New Job". Fill in the job details including title, description, requirements, and qualifications. You can also upload a job description document for auto-filling.',
      },
      {
        question: 'How can I review applications?',
        answer:
          'Go to your dashboard to see all your posted jobs and the number of applications for each. Click on a job to view all applicants, their profiles, resumes, and change their application status.',
      },
      {
        question: 'Can I edit or delete job postings?',
        answer:
          'Yes! From your dashboard, you can edit job details or delete job postings at any time. Note that deleting a job will also remove all associated applications.',
      },
      {
        question: 'How do I manage candidates?',
        answer:
          'Use the "Candidates" page to view all applicants across all your job postings. You can filter by job, view detailed profiles, and update application statuses.',
      },
    ],
  },
  {
    category: 'Technical & Account',
    questions: [
      {
        question: 'I forgot my password. What should I do?',
        answer:
          'Open Login → HR / Admin Login, then click Forgot password. Enter your work email and we send a 6-digit OTP. Verify the OTP, set a new password, then sign in again.',
      },
      {
        question: 'Is my data secure?',
        answer:
          'Yes. HR Intelligence uses secure authentication and encrypted connections to protect your information. We never share your personal information with third parties without your consent.',
      },
      {
        question: 'What file formats are supported for resume upload?',
        answer: 'We support PDF and DOCX formats for resume uploads. Maximum file size is 10MB. Legacy .DOC is not supported.',
      },
      {
        question: 'The website is not working properly. What should I do?',
        answer:
          'Try refreshing the page or clearing your browser cache. If the problem persists, please contact us through the "Contact Us" form with details about the issue you\'re experiencing.',
      },
    ],
  },
]

export default function FAQ() {
  const [expandedItems, setExpandedItems] = useState({})
  const navigate = useNavigate()

  const toggleItem = (categoryIndex, questionIndex) => {
    const key = `${categoryIndex}-${questionIndex}`
    setExpandedItems((prev) => ({
      ...prev,
      [key]: !prev[key],
    }))
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
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
            <div className="w-20 h-20 mx-auto rounded-full bg-gradient-to-r from-sky-500 to-blue-600 flex items-center justify-center shadow-glow">
              <FiHelpCircle className="w-10 h-10 text-white" />
            </div>
          </motion.div>

          <h1 className="text-4xl font-bold bg-gradient-to-r from-[var(--ei-text-primary)] to-[var(--ei-text-secondary)] bg-clip-text text-transparent mb-3">
            Frequently Asked Questions
          </h1>
          <p className="text-[var(--ei-text-muted)] text-lg">
            Find answers to common questions about HR Intelligence
          </p>
        </motion.div>

        <div className="space-y-8">
          {faqs.map((category, categoryIndex) => (
            <motion.div
              key={categoryIndex}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: categoryIndex * 0.1 }}
            >
              <h2 className="text-2xl font-bold text-[var(--ei-text-primary)] mb-4 flex items-center gap-2">
                <span className="w-1 h-8 bg-gradient-to-b from-sky-500 to-blue-600 rounded-full" />
                {category.category}
              </h2>

              <div className="space-y-3">
                {category.questions.map((item, questionIndex) => {
                  const key = `${categoryIndex}-${questionIndex}`
                  const isExpanded = expandedItems[key]

                  return (
                    <motion.div
                      key={questionIndex}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: categoryIndex * 0.1 + questionIndex * 0.05 }}
                      className="glass-card rounded-xl border border-[var(--ei-border-primary)] overflow-hidden"
                    >
                      <button
                        onClick={() => toggleItem(categoryIndex, questionIndex)}
                        className="w-full text-left px-6 py-4 flex items-center justify-between gap-4 hover:bg-[var(--ei-surface-hover)] transition-colors"
                      >
                        <span className="text-[var(--ei-text-primary)] font-medium">{item.question}</span>
                        <motion.div
                          animate={{ rotate: isExpanded ? 180 : 0 }}
                          transition={{ duration: 0.3 }}
                        >
                          <FiChevronDown className="w-5 h-5 text-[var(--ei-text-muted)] flex-shrink-0" />
                        </motion.div>
                      </button>

                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.3 }}
                            className="overflow-hidden"
                          >
                            <div className="px-6 pb-4 pt-2 text-[var(--ei-text-muted)] leading-relaxed border-t border-[var(--ei-border-primary)]">
                              {item.answer}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  )
                })}
              </div>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.6 }}
          className="mt-12 org-glass-card hover:transform-none rounded-2xl p-8 text-center"
        >
          <FiMessageCircle className="w-12 h-12 text-sky-400 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-[var(--ei-text-primary)] mb-2">Still have questions?</h3>
          <p className="text-[var(--ei-text-muted)] mb-6">
            Can&apos;t find the answer you&apos;re looking for? Our support team is here to help!
          </p>
          <PremiumButton onClick={() => navigate('/support/contact')} className="mx-auto">
            <FiMessageCircle className="mr-2" />
            Contact Support
          </PremiumButton>
        </motion.div>
      </div>
    </div>
  )
}
