import React, { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext.jsx'

export default function Navbar() {
  const { auth, applicantAuth, applicantProfile, logout, user } = useApp()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [hrMenuOpen, setHrMenuOpen] = useState(false)
  const menuRef = useRef(null)
  const hrMenuRef = useRef(null)

  const activeClass = ({ isActive }) =>
    isActive ? 'text-white' : 'text-zinc-300 hover:text-white'

  const isHrLoggedIn = auth.isLoggedIn && auth.role === 'HR'
  const isApplicantLoggedIn = applicantAuth.isLoggedIn && !isHrLoggedIn

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
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  return (
    <header className="bg-zinc-950/80 sticky top-0 z-30 border-b border-zinc-900/80 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 group">
            <div className="w-8 h-8 rounded-lg bg-white text-black grid place-items-center font-bold">J</div>
            <span className="font-semibold text-white transition">Job Portal</span>
          </Link>

          <nav className="flex items-center gap-6">
            <NavLink to="/jobs" className={activeClass}>Jobs</NavLink>
            {!isHrLoggedIn && !isApplicantLoggedIn ? (
              <>
                <NavLink to="/login" className={activeClass}>Login</NavLink>
              </>
            ) : (
              <>
                {isHrLoggedIn && (
                  <div className="relative" ref={hrMenuRef}>
                    <button
                      onClick={() => setHrMenuOpen((o) => !o)}
                      className="w-8 h-8 rounded-full bg-zinc-800 text-white text-xs font-semibold grid place-items-center ring-1 ring-zinc-700 hover:ring-zinc-500 transition-all"
                    >
                      {hrInitials}
                    </button>
                    {hrMenuOpen && (
                      <div className="absolute right-0 mt-2 w-44 rounded-lg border border-zinc-800 bg-zinc-900/95 backdrop-blur shadow-lg py-1">
                        <button
                          className="w-full text-left px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-800"
                          onClick={() => { setHrMenuOpen(false); navigate('/dashboard') }}
                        >Dashboard</button>
                        <button
                          className="w-full text-left px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-800"
                          onClick={() => { setHrMenuOpen(false); navigate('/candidates') }}
                        >Candidates</button>
                        <button
                          className="w-full text-left px-3 py-2 text-sm text-red-300 hover:bg-zinc-800"
                          onClick={() => { setHrMenuOpen(false); handleLogout() }}
                        >Logout</button>
                      </div>
                    )}
                  </div>
                )}
                {isApplicantLoggedIn && (
                  <div className="relative" ref={menuRef}>
                    <button
                      onClick={() => setMenuOpen((o) => !o)}
                      className={
                        applicantInitials
                          ? 'w-8 h-8 rounded-full bg-zinc-800 text-white text-xs font-semibold grid place-items-center ring-1 ring-zinc-700 hover:ring-zinc-500'
                          : 'text-zinc-300 hover:text-white'
                      }
                    >
                      {applicantInitials || 'My Profile'}
                    </button>
                    {menuOpen && (
                      <div className="absolute right-0 mt-2 w-44 rounded-lg border border-zinc-800 bg-zinc-900/95 backdrop-blur shadow-lg py-1">
                        <button
                          className="w-full text-left px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-800"
                          onClick={() => { setMenuOpen(false); navigate('/profile/applicant') }}
                        >Profile</button>
                        <button
                          className="w-full text-left px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-800"
                          onClick={() => { setMenuOpen(false); navigate('/applications') }}
                        >Application Status</button>
                        <button
                          className="w-full text-left px-3 py-2 text-sm text-red-300 hover:bg-zinc-800"
                          onClick={() => { setMenuOpen(false); handleLogout() }}
                        >Logout</button>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </nav>
        </div>
      </div>
    </header>
  )
}


