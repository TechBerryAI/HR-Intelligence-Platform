import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FiChevronDown, FiHelpCircle, FiMessageCircle } from 'react-icons/fi'
import { useNavigate } from 'react-router-dom'
import PremiumButton from '../components/PremiumButton.jsx'

const faqs = [
  {
    category: 'General',
    questions: [
      {
        question: 'What is this Job Portal?',
        answer: 'This is a comprehensive job portal that connects job seekers with employers. Candidates can create profiles, upload resumes, and apply for jobs, while HR professionals can post job openings and manage applications.'
      },
      {
        question: 'Is this service free to use?',
        answer: 'Yes! Job seekers can create accounts, upload resumes, and apply for jobs completely free. Employers can post jobs and review applications at no cost.'
      },
      {
        question: 'How do I get started?',
        answer: 'Simply click on "Login" and select whether you\'re a candidate or an HR professional. If you don\'t have an account, you can sign up from the login page. Complete your profile and you\'re ready to go!'
      }
    ]
  },
  {
    category: 'For Job Seekers',
    questions: [
      {
        question: 'How do I create a candidate profile?',
        answer: 'After signing up as a candidate, go to your profile page and fill in your details including education, experience, skills, and upload your resume. Make sure to complete all required fields to make your profile visible to employers.'
      },
      {
        question: 'Can I upload my resume?',
        answer: 'Yes! You can upload your resume in PDF, DOC, or DOCX format. Our system will parse your resume and auto-fill your profile information, which you can then review and edit.'
      },
      {
        question: 'How do I apply for a job?',
        answer: 'Browse available jobs, click on a job that interests you, and click the "Apply" button. Make sure your profile is complete before applying, as employers will review your profile along with your application.'
      },
      {
        question: 'Can I track my application status?',
        answer: 'Yes! Go to "Application Status" from your profile menu to see all your applications and their current status (pending, reviewed, shortlisted, or rejected).'
      },
      {
        question: 'Can I save jobs to apply later?',
        answer: 'Absolutely! Click the bookmark icon on any job listing to save it. You can view all your saved jobs later and apply when you\'re ready.'
      }
    ]
  },
  {
    category: 'For HR Professionals',
    questions: [
      {
        question: 'How do I post a job opening?',
        answer: 'After logging in as an HR professional, go to your dashboard and click "Post New Job". Fill in the job details including title, description, requirements, and qualifications. You can also upload a job description document for auto-filling.'
      },
      {
        question: 'How can I review applications?',
        answer: 'Go to your dashboard to see all your posted jobs and the number of applications for each. Click on a job to view all applicants, their profiles, resumes, and change their application status.'
      },
      {
        question: 'Can I edit or delete job postings?',
        answer: 'Yes! From your dashboard, you can edit job details or delete job postings at any time. Note that deleting a job will also remove all associated applications.'
      },
      {
        question: 'How do I manage candidates?',
        answer: 'Use the "Candidates" page to view all applicants across all your job postings. You can filter by job, view detailed profiles, and update application statuses.'
      }
    ]
  },
  {
    category: 'Technical & Account',
    questions: [
      {
        question: 'I forgot my password. What should I do?',
        answer: 'Click on "Login" and then "Forgot Password". Enter your email address and follow the instructions sent to your email to reset your password.'
      },
      {
        question: 'Can I change my email address?',
        answer: 'Currently, email addresses cannot be changed after registration as they are used for authentication. If you need to change your email, please contact our support team.'
      },
      {
        question: 'Is my data secure?',
        answer: 'Yes! We take data security seriously. All passwords are encrypted, and we use industry-standard security practices to protect your information. We never share your personal information with third parties without your consent.'
      },
      {
        question: 'What file formats are supported for resume upload?',
        answer: 'We support PDF, DOC, and DOCX file formats for resume uploads. Maximum file size is 10MB.'
      },
      {
        question: 'The website is not working properly. What should I do?',
        answer: 'Try refreshing the page or clearing your browser cache. If the problem persists, please contact us through the "Contact Us" form with details about the issue you\'re experiencing.'
      }
    ]
  }
]

export default function FAQ() {
  const [expandedItems, setExpandedItems] = useState({})
  const navigate = useNavigate()

  const toggleItem = (categoryIndex, questionIndex) => {
    const key = `${categoryIndex}-${questionIndex}`
    setExpandedItems(prev => ({
      ...prev,
      [key]: !prev[key]
    }))
  }

  return (
    <div className="min-h-screen bg-zinc-950 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
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
              <FiHelpCircle className="w-10 h-10 text-white" />
            </div>
          </motion.div>
          
          <h1 className="text-4xl font-bold bg-gradient-to-r from-white to-zinc-300 bg-clip-text text-transparent mb-3">
            Frequently Asked Questions
          </h1>
          <p className="text-zinc-400 text-lg">
            Find answers to common questions about our job portal
          </p>
        </motion.div>

        {/* FAQ Categories */}
        <div className="space-y-8">
          {faqs.map((category, categoryIndex) => (
            <motion.div
              key={categoryIndex}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: categoryIndex * 0.1 }}
            >
              <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
                <span className="w-1 h-8 bg-gradient-to-b from-purple-600 to-blue-600 rounded-full"></span>
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
                      transition={{ delay: (categoryIndex * 0.1) + (questionIndex * 0.05) }}
                      className="glass-card rounded-xl border border-white/10 overflow-hidden"
                    >
                      <button
                        onClick={() => toggleItem(categoryIndex, questionIndex)}
                        className="w-full text-left px-6 py-4 flex items-center justify-between gap-4 hover:bg-white/5 transition-colors"
                      >
                        <span className="text-white font-medium">{item.question}</span>
                        <motion.div
                          animate={{ rotate: isExpanded ? 180 : 0 }}
                          transition={{ duration: 0.3 }}
                        >
                          <FiChevronDown className="w-5 h-5 text-zinc-400 flex-shrink-0" />
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
                            <div className="px-6 pb-4 pt-2 text-zinc-400 leading-relaxed border-t border-white/5">
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

        {/* Still have questions CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.6 }}
          className="mt-12 glass-card rounded-2xl p-8 border border-white/10 text-center"
        >
          <FiMessageCircle className="w-12 h-12 text-purple-500 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-white mb-2">
            Still have questions?
          </h3>
          <p className="text-zinc-400 mb-6">
            Can't find the answer you're looking for? Our support team is here to help!
          </p>
          <PremiumButton
            onClick={() => navigate('/support/contact')}
            className="mx-auto"
          >
            <FiMessageCircle className="mr-2" />
            Contact Support
          </PremiumButton>
        </motion.div>
      </div>
    </div>
  )
}

