import React from 'react'
import { Link, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { useTheme } from '@/core/context/ThemeContext.jsx'
import ThemeToggle from '@/shared/components/ThemeToggle.jsx'
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
import { isRecruiter, isHeadHr, isCeo, isStaff } from '@/core/permissions/rbac.js'

function isStaffAppPath(pathname) {
  return (
    pathname.startsWith('/jobs') ||
    pathname.startsWith('/dashboard') ||
    pathname.startsWith('/candidates') ||
    pathname.startsWith('/admin') ||
    pathname.startsWith('/settings') ||
    pathname.startsWith('/integrations')
  )
}

export default function Navbar() {
  const { auth, logout, user } = useApp()
  const { isDark } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()

  const isAuthChrome =
    location.pathname.startsWith('/login') ||
    location.pathname.startsWith('/signup') ||
    location.pathname.startsWith('/forgot-password')

  const isStaffChrome = isStaffAppPath(location.pathname)
  // Global preference drives chrome; staff/auth routes stay enterprise-styled in dark mode
  const darkChrome = isDark

  const activeClass = ({ isActive }) => {
    if (isAuthChrome && darkChrome) {
      return isActive ? 'auth-nav-link auth-nav-link-active' : 'auth-nav-link'
    }
    if (darkChrome && (isStaffChrome || isAuthChrome)) {
      return isActive
        ? 'text-[var(--ei-text-primary)] font-semibold'
        : 'text-[var(--ei-text-secondary)] hover:text-[var(--ei-text-primary)] transition-colors'
    }
    return isActive
      ? 'text-slate-900 font-semibold'
      : 'text-slate-600 hover:text-slate-900 transition-colors'
  }

  const isHrRecruiter = auth.isLoggedIn && isRecruiter(auth)
  const isHeadHrLoggedIn = auth.isLoggedIn && isHeadHr(auth)
  const isCeoLoggedIn = auth.isLoggedIn && isCeo(auth)
  const showHrmsFeedback = auth.isLoggedIn && isStaff(auth)

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
      <span
        className={
          isAuthChrome && darkChrome
            ? 'px-3 py-2 inline-block text-[14px] font-medium'
            : darkChrome && isStaffChrome
              ? 'px-3 py-2 rounded-lg hover:bg-white/[0.06] transition-colors inline-block'
              : 'px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors inline-block'
        }
      >
        {label}
      </span>
    </NavLink>
  )

  const showLogin = !isHrRecruiter && !isHeadHrLoggedIn && !isCeoLoggedIn

  const menuContentClass = darkChrome
    ? 'w-56 border-white/10 bg-[#121A24] text-[#E8EDF3] shadow-[0_16px_48px_rgba(0,0,0,0.45)]'
    : 'w-56'

  const menuItemClass = darkChrome
    ? 'text-[#C5CED8] focus:bg-white/[0.06] focus:text-white'
    : ''

  const toggleClass = darkChrome
    ? isAuthChrome
      ? 'auth-nav-link hover:bg-white/5 hover:text-white text-[#94a2af] border-white/10'
      : 'text-[var(--ei-text-secondary)] hover:text-[var(--ei-text-primary)] hover:bg-white/[0.09] border-white/10 bg-white/[0.05]'
    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 border-slate-200 bg-white'

  const headerClass = (() => {
    if (isAuthChrome && darkChrome) return 'sticky top-0 z-30 w-full auth-nav px-3 sm:px-6'
    if (isAuthChrome && !darkChrome) {
      return 'sticky top-0 z-30 w-full h-16 bg-white/90 backdrop-blur-xl border-b border-slate-200'
    }
    if (isStaffChrome && darkChrome) {
      return 'sticky top-0 z-30 w-full h-16 border-b border-[var(--ei-border-primary)] bg-[color-mix(in_srgb,var(--ei-bg-primary)_90%,transparent)] backdrop-blur-xl'
    }
    if (isStaffChrome && !darkChrome) {
      return 'sticky top-0 z-30 w-full h-16 bg-white/90 backdrop-blur-xl border-b border-slate-200 shadow-sm'
    }
    return darkChrome
      ? 'sticky top-0 z-30 w-full h-16 border-b border-[var(--ei-border-primary)] bg-[var(--ei-bg-primary)]/90 backdrop-blur-xl'
      : 'sticky top-0 z-30 w-full h-16 bg-white border-b border-slate-200 shadow-sm'
  })()

  return (
    <header className={headerClass}>
      <div
        className={
          isAuthChrome && darkChrome
            ? 'auth-nav-inner'
            : 'max-w-7xl mx-auto px-6 h-full flex items-center justify-between gap-6'
        }
      >
        <Link to="/" className="flex items-center gap-2.5 shrink-0 group">
          {darkChrome ? (
            <>
              <div className="relative h-10 w-10">
                <div className="absolute inset-0 rounded-full bg-gradient-to-br from-sky-400/30 to-blue-600/20 blur-md opacity-80 group-hover:opacity-100 transition-opacity" />
                <div className="relative h-full w-full rounded-full bg-gradient-to-br from-sky-400 to-blue-600 flex items-center justify-center text-white font-display font-bold text-lg ring-1 ring-white/20">
                  H
                </div>
              </div>
              <div className="leading-tight">
                <span className="block font-display font-semibold text-[15px] sm:text-base text-[var(--ei-text-primary)] tracking-tight">
                  HR Intelligence
                </span>
                <span className="hidden sm:block text-[10px] text-[var(--ei-text-muted)] tracking-[0.18em] uppercase font-medium">
                  Enterprise Platform
                </span>
              </div>
            </>
          ) : (
            <>
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
            </>
          )}
        </Link>

        <nav className="flex items-center gap-1 sm:gap-4">
          {navItem('/jobs', 'Jobs')}

          {showLogin && navItem('/login', 'Login')}

          {isHrRecruiter && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className={`rounded-full ${darkChrome ? 'hover:bg-white/[0.06]' : ''}`}
                >
                  <AvatarWithInitials
                    initials={hrInitials}
                    size="sm"
                    className={darkChrome ? 'bg-sky-500/20 text-sky-300 ring-1 ring-sky-400/30' : 'bg-blue-100 text-blue-600'}
                  />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className={menuContentClass}>
                <DropdownMenuItem onClick={() => navigate('/dashboard')} className={menuItemClass}>
                  <FiBriefcase className="mr-2 h-4 w-4" /> Dashboard
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/candidates')} className={menuItemClass}>
                  <FiUsers className="mr-2 h-4 w-4" /> Candidates
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/admin/bulk-resume-parser')} className={menuItemClass}>
                  <FiFileText className="mr-2 h-4 w-4" /> Bulk Resume Parser
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/admin/feedback')} className={menuItemClass}>
                  <FiMessageSquare className="mr-2 h-4 w-4" /> Feedback (Admin)
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/integrations')} className={menuItemClass}>
                  <FiBriefcase className="mr-2 h-4 w-4" /> Integrations
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate('/settings')} className={menuItemClass}>
                  <FiSettings className="mr-2 h-4 w-4" /> Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator className={darkChrome ? 'bg-white/10' : ''} />
                <DropdownMenuItem
                  onClick={handleLogout}
                  className={darkChrome ? 'text-red-400 focus:text-red-300 focus:bg-red-500/10' : 'text-red-600 focus:text-red-600'}
                >
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

          <ThemeToggle variant="chrome" className={toggleClass} />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className={
                  isAuthChrome && darkChrome
                    ? 'auth-nav-link hover:bg-white/5 hover:text-white'
                    : darkChrome
                      ? 'text-[var(--ei-text-secondary)] hover:text-[var(--ei-text-primary)] hover:bg-white/[0.06]'
                      : 'text-slate-600'
                }
              >
                <FiHelpCircle className="mr-1.5 h-4 w-4" /> <span className="hidden sm:inline">Support</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className={darkChrome ? 'w-52 border-white/10 bg-[#121A24] text-[#E8EDF3]' : 'w-52'}>
              <DropdownMenuItem onClick={() => navigate('/support/faq')} className={menuItemClass}>
                <FiBook className="mr-2 h-4 w-4" /> FAQ
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/support/contact')} className={menuItemClass}>
                <FiMessageCircle className="mr-2 h-4 w-4" /> Contact Us
              </DropdownMenuItem>
              {showHrmsFeedback && (
                <DropdownMenuItem onClick={() => navigate('/support/hrms-feedback')} className={menuItemClass}>
                  <FiMessageSquare className="mr-2 h-4 w-4" /> HRMS Testing Feedback
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>
      </div>
    </header>
  )
}
