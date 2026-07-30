import React from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Button,
  AvatarWithInitials,
} from './ui/index.js'
import { FiBriefcase, FiFileText, FiLogOut, FiUsers, FiHelpCircle, FiMessageCircle, FiMessageSquare, FiBook, FiShield, FiSettings } from 'react-icons/fi'
import { isRecruiter, isHeadHr, isCeo } from '@/core/permissions/rbac.js'

export default function Navbar() {
  const { auth, logout, user } = useApp()
  const navigate = useNavigate()

  const activeClass = ({ isActive }) =>
    isActive ? 'text-slate-900 font-semibold' : 'text-slate-600 hover:text-slate-900 transition-colors'

  const isHrRecruiter = auth.isLoggedIn && isRecruiter(auth)
  const isHeadHrLoggedIn = auth.isLoggedIn && isHeadHr(auth)
  const isCeoLoggedIn = auth.isLoggedIn && isCeo(auth)

  const hrInitials = (() => {
    const name = user?.fullName || user?.name || auth?.fullName || ''
    if (!name) return 'Recruiter'
    return name.trim().split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase()
  })()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const navItem = (path, label) => (
    <NavLink to={path} className={activeClass}>
      <span className="px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors inline-block">{label}</span>
    </NavLink>
  )

  const showLogin = !isHrRecruiter && !isHeadHrLoggedIn && !isCeoLoggedIn

  return (
    <header className="sticky top-0 z-30 w-full h-16 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between gap-6">
        <Link to="/" className="flex items-center gap-2.5 shrink-0 group">
          <div className="relative h-10 w-10">
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-sky-400/30 to-blue-600/20 blur-md opacity-80 group-hover:opacity-100 transition-opacity" />
            <div className="relative h-full w-full rounded-full bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center text-white font-bold text-lg ring-1 ring-blue-500/20 shadow-sm">
              H
            </div>
          </div>
          <div className="leading-tight">
            <span className="block font-bold text-lg text-slate-900 tracking-tight">HR Intelligence</span>
            <span className="hidden sm:block text-[10px] font-medium uppercase tracking-[0.16em] text-slate-400">
              Enterprise Platform
            </span>
          </div>
        </Link>

        <nav className="flex items-center gap-1 sm:gap-4">
          {navItem('/jobs', 'Jobs')}

          {showLogin && navItem('/login', 'Login')}

          {isHrRecruiter && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="rounded-full">
                  <AvatarWithInitials initials={hrInitials} size="sm" className="bg-blue-100 text-blue-600" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuItem onClick={() => navigate('/dashboard')}>
                  <FiBriefcase className="mr-2 h-4 w-4" /> Dashboard
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/candidates')}>
                  <FiUsers className="mr-2 h-4 w-4" /> Candidates
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/admin/bulk-resume-parser')}>
                  <FiFileText className="mr-2 h-4 w-4" /> Bulk Resume Parser
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/admin/feedback')}>
                  <FiMessageSquare className="mr-2 h-4 w-4" /> Feedback (Admin)
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/settings')}>
                  <FiSettings className="mr-2 h-4 w-4" /> Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="text-red-600 focus:text-red-600">
                  <FiLogOut className="mr-2 h-4 w-4" /> Logout
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {isHeadHrLoggedIn && (
            <Link to="/head-hr">
              <Button variant="default" size="sm" className="gap-1.5">
                <FiShield className="h-3.5 w-3.5" /> Head of HR
              </Button>
            </Link>
          )}

          {isCeoLoggedIn && (
            <Link to="/ceo">
              <Button variant="default" size="sm" className="gap-1.5">
                <FiShield className="h-3.5 w-3.5" /> Executive
              </Button>
            </Link>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="text-slate-600">
                <FiHelpCircle className="mr-1.5 h-4 w-4" /> <span className="hidden sm:inline">Support</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuItem onClick={() => navigate('/support/faq')}>
                <FiBook className="mr-2 h-4 w-4" /> FAQ
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/support/contact')}>
                <FiMessageCircle className="mr-2 h-4 w-4" /> Contact Us
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/support/hrms-feedback')}>
                <FiMessageSquare className="mr-2 h-4 w-4" /> HRMS Testing Feedback
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>
      </div>
    </header>
  )
}
