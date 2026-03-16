import React, { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'
import { motion, AnimatePresence } from 'framer-motion'
import { FiBriefcase, FiUser, FiFileText, FiLogOut, FiUsers, FiHelpCircle, FiMessageCircle, FiMessageSquare, FiBook, FiShield, FiSettings } from 'react-icons/fi'

export default function Navbar() {
  const { auth, applicantAuth, applicantProfile, logout, user, superAdminAuth } = useApp()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [hrMenuOpen, setHrMenuOpen] = useState(false)
  const [supportMenuOpen, setSupportMenuOpen] = useState(false)
  const menuRef = useRef(null)
  const hrMenuRef = useRef(null)
  const supportMenuRef = useRef(null)

  const activeClass = ({ isActive }) =>
    isActive ? 'text-white font-semibold' : 'text-zinc-300 hover:text-white transition-colors'

  const isHrLoggedIn = auth.isLoggedIn && (auth.role === 'HR' || auth.role === 'head_hr')
  const isApplicantLoggedIn = applicantAuth.isLoggedIn && !isHrLoggedIn
  const isSuperAdminLoggedIn = superAdminAuth?.isLoggedIn

  const applicantInitials = (() => {
    const name = applicantProfile?.completed && applicantProfile?.fullName ? applicantProfile.fullName : ''
    if (!name) return ''
    const parts = name.trim().split(/\s+/)
    return parts.slice(0, 2).map(p => p[0]).join('').toUpperCase()
  })()

  const hrInitials = (() => {
    const name = user?.fullName || user?.name || ''
    if (!name) return 'HR'
    const parts = name.trim().split(/\s+/)
    return parts.slice(0, 2).map(p => p[0]).join('').toUpperCase()
  })()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  useEffect(() => {
    const onDocClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
      if (hrMenuRef.current && !hrMenuRef.current.contains(e.target)) {
        setHrMenuOpen(false)
      }
      if (supportMenuRef.current && !supportMenuRef.current.contains(e.target)) {
        setSupportMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  return (
    <div className="sticky top-0 z-30 w-full min-h-[64px]">
      <motion.header
        initial={{ y: -100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 100, damping: 20 }}
        className="glass-card border-b border-white/10 backdrop-blur-xl"
        style={{ willChange: 'transform', minHeight: '64px' }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 group">
            <motion.div
              whileHover={{ rotate: 360, scale: 1.1 }}
              transition={{ duration: 0.5 }}
              className="w-10 h-10 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white grid place-items-center font-bold text-lg shadow-glow"
            >
              J
            </motion.div>
            <span className="font-bold text-lg bg-gradient-to-r from-white to-zinc-300 bg-clip-text text-transparent">
              Job Portal
            </span>
          </Link>

          <nav className="flex items-center gap-6">
            <NavLink to="/jobs" className={activeClass}>
              <motion.span whileHover={{ scale: 1.05 }} className="inline-block">
                Jobs
              </motion.span>
            </NavLink>
            {!isHrLoggedIn && !isApplicantLoggedIn && !isSuperAdminLoggedIn ? (
              <>
                <NavLink to="/login" className={activeClass}>
                  <motion.span whileHover={{ scale: 1.05 }} className="inline-block">
                    Login
                  </motion.span>
                </NavLink>
              </>
            ) : (
              <>
                {isHrLoggedIn && (
                  <div className="relative" ref={hrMenuRef}>
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setHrMenuOpen((o) => !o)}
                      className="w-10 h-10 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-bold grid place-items-center shadow-glow"
                    >
                      {hrInitials}
                    </motion.button>
                    <AnimatePresence>
                      {hrMenuOpen && (
                        <motion.div
                          initial={{ opacity: 0, scale: 0.95, y: -10 }}
                          animate={{ opacity: 1, scale: 1, y: 0 }}
                          exit={{ opacity: 0, scale: 0.95, y: -10 }}
                          transition={{ duration: 0.2 }}
                          className="absolute right-0 mt-2 w-52 rounded-xl border border-white/10 shadow-premium overflow-hidden bg-zinc-900 shadow-xl"
                        >
                          <div className="py-2">
                            <motion.button
                              whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                              className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                              onClick={() => { setHrMenuOpen(false); navigate('/dashboard') }}
                            >
                              <FiBriefcase className="w-4 h-4" />
                              Dashboard
                            </motion.button>
                            <motion.button
                              whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                              className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                              onClick={() => { setHrMenuOpen(false); navigate('/candidates') }}
                            >
                              <FiUsers className="w-4 h-4" />
                              Candidates
                            </motion.button>
                            <motion.button
                              whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                              className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                              onClick={() => { setHrMenuOpen(false); navigate('/admin/bulk-resume-parser') }}
                            >
                              <FiFileText className="w-4 h-4" />
                              Bulk Resume Parser
                            </motion.button>
                            <motion.button
                              whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                              className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                              onClick={() => { setHrMenuOpen(false); navigate('/admin/feedback') }}
                            >
                              <FiMessageSquare className="w-4 h-4" />
                              Feedback (Admin)
                            </motion.button>
                            <motion.button
                              whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                              className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                              onClick={() => { setHrMenuOpen(false); navigate('/settings') }}
                            >
                              <FiSettings className="w-4 h-4" />
                              Settings
                            </motion.button>
                            <div className="border-t border-white/10 my-1" />
                            <motion.button
                              whileHover={{ backgroundColor: 'rgba(239, 68, 68, 0.1)' }}
                              className="w-full text-left px-4 py-2.5 text-sm text-red-300 flex items-center gap-3"
                              onClick={() => { setHrMenuOpen(false); handleLogout() }}
                            >
                              <FiLogOut className="w-4 h-4" />
                              Logout
                            </motion.button>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
                {isApplicantLoggedIn && (
                  <div className="relative" ref={menuRef}>
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setMenuOpen((o) => !o)}
                      className={
                        applicantInitials
                          ? 'w-10 h-10 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-bold grid place-items-center shadow-glow'
                          : 'text-zinc-300 hover:text-white'
                      }
                    >
                      {applicantInitials || 'My Profile'}
                    </motion.button>
                    <AnimatePresence>
                      {menuOpen && (
                        <motion.div
                          initial={{ opacity: 0, scale: 0.95, y: -10 }}
                          animate={{ opacity: 1, scale: 1, y: 0 }}
                          exit={{ opacity: 0, scale: 0.95, y: -10 }}
                          transition={{ duration: 0.2 }}
                          className="absolute right-0 mt-2 w-52 rounded-xl border border-white/10 shadow-premium overflow-hidden bg-zinc-900 shadow-xl"
                        >
                          <div className="py-2">
                            <motion.button
                              whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                              className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                              onClick={() => { setMenuOpen(false); navigate('/profile/applicant') }}
                            >
                              <FiUser className="w-4 h-4" />
                              Profile
                            </motion.button>
                            <motion.button
                              whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                              className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                              onClick={() => { setMenuOpen(false); navigate('/applications') }}
                            >
                              <FiFileText className="w-4 h-4" />
                              Application Status
                            </motion.button>
                            <motion.button
                              whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                              className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                              onClick={() => { setMenuOpen(false); navigate('/settings/applicant') }}
                            >
                              <FiSettings className="w-4 h-4" />
                              Settings
                            </motion.button>
                            <div className="border-t border-white/10 my-1" />
                            <motion.button
                              whileHover={{ backgroundColor: 'rgba(239, 68, 68, 0.1)' }}
                              className="w-full text-left px-4 py-2.5 text-sm text-red-300 flex items-center gap-3"
                              onClick={() => { setMenuOpen(false); handleLogout() }}
                            >
                              <FiLogOut className="w-4 h-4" />
                              Logout
                            </motion.button>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
              </>
            )}

            {/* Super Admin: direct link to Overview (no dropdown) */}
            {isSuperAdminLoggedIn && (
              <Link to="/super-admin">
                <motion.span
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 shadow-glow transition-all duration-200 inline-block"
                >
                  <FiShield className="w-3.5 h-3.5" />
                  Super Admin
                </motion.span>
              </Link>
            )}

            {/* Support Dropdown - Always at the end */}
            <div className="relative" ref={supportMenuRef}>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setSupportMenuOpen((o) => !o)}
                className="text-zinc-300 hover:text-white transition-colors flex items-center gap-1"
              >
                <FiHelpCircle className="w-4 h-4" />
                Support
              </motion.button>
              <AnimatePresence>
                {supportMenuOpen && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: -10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: -10 }}
                    transition={{ duration: 0.2 }}
                    className="absolute right-0 mt-2 w-52 rounded-xl border border-white/10 shadow-premium overflow-hidden bg-zinc-900 shadow-xl"
                  >
                    <div className="py-2">
                      <motion.button
                        whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                        className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                        onClick={() => { setSupportMenuOpen(false); navigate('/support/faq') }}
                      >
                        <FiBook className="w-4 h-4" />
                        FAQ
                      </motion.button>
                      <motion.button
                        whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                        className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                        onClick={() => { setSupportMenuOpen(false); navigate('/support/contact') }}
                      >
                        <FiMessageCircle className="w-4 h-4" />
                        Contact Us
                      </motion.button>
                      <motion.button
                        whileHover={{ backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
                        className="w-full text-left px-4 py-2.5 text-sm text-zinc-200 flex items-center gap-3"
                        onClick={() => { setSupportMenuOpen(false); navigate('/support/hrms-feedback') }}
                      >
                        <FiMessageSquare className="w-4 h-4" />
                        HRMS Testing Feedback
                      </motion.button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </nav>
        </div>
      </div>
      </motion.header>
    </div>
  )
}
