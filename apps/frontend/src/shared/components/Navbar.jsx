import React from 'react'
import { Link, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { useTheme } from '@/core/context/ThemeContext.jsx'
import ThemeToggle from '@/shared/components/ThemeToggle.jsx'
import BrandMark from '@/shared/components/BrandMark.jsx'
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

/** Same chrome pill as ThemeToggle — shared so Light / Support match. */
function chromeControlClass(darkChrome, isAuthChrome) {
  const base =
    'inline-flex items-center justify-center gap-2 h-9 px-3 rounded-xl text-sm font-medium border transition-colors'
  if (!darkChrome) {
    return `${base} text-slate-700 hover:text-slate-900 hover:bg-slate-100 border-slate-200 bg-white`
  }
  if (isAuthChrome) {
    return `${base} auth-nav-link hover:bg-white/5 hover:text-white text-[#c5d0db] border-white/10 bg-white/[0.04]`
  }
  return `${base} text-[#d7dee6] hover:text-white hover:bg-white/[0.09] border-white/12 bg-white/[0.05]`
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
  const darkChrome = isDark

  const activeClass = ({ isActive }) => {
    if (isAuthChrome && darkChrome) {
      return isActive ? 'auth-nav-link auth-nav-link-active' : 'auth-nav-link'
    }
    if (darkChrome) {
      return isActive
        ? 'text-[var(--ei-text-primary)] font-semibold'
        : 'text-[#b8c2cc] hover:text-[var(--ei-text-primary)] transition-colors'
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
            : darkChrome
              ? 'px-3 py-2 rounded-lg hover:bg-white/[0.06] transition-colors inline-block text-[14px] font-medium'
              : 'px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors inline-block text-[14px] font-medium'
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

  const chromeClass = chromeControlClass(darkChrome, isAuthChrome)

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
        <Link to="/" className="flex items-center gap-3 shrink-0 group">
          <BrandMark
            className={
              darkChrome
                ? 'group-hover:border-white/16 transition-[border-color]'
                : 'bg-slate-900 border-slate-900/20 text-white shadow-sm group-hover:bg-slate-800'
            }
          />
          <div className="leading-tight">
            <span
              className={
                darkChrome
                  ? 'block font-display font-semibold text-[15px] sm:text-base text-[var(--ei-text-primary)] tracking-tight'
                  : 'block font-bold text-lg text-slate-900 tracking-tight'
              }
            >
              HR Intelligence
            </span>
            <span
              className={
                darkChrome
                  ? 'hidden sm:block text-[10px] text-[var(--ei-text-muted)] tracking-[0.18em] uppercase font-medium'
                  : 'hidden sm:block text-[10px] font-medium uppercase tracking-[0.16em] text-slate-400'
              }
            >
              Enterprise Platform
            </span>
          </div>
        </Link>

        <nav className="flex items-center gap-1 sm:gap-3">
          {navItem('/jobs', 'Jobs')}

          {showLogin && navItem('/login', 'Login')}

          {isHrRecruiter && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className={`rounded-full ${darkChrome ? 'hover:bg-white/[0.06] text-[var(--ei-text-primary)]' : ''}`}
                >
                  <AvatarWithInitials
                    initials={hrInitials}
                    size="sm"
                    className={
                      darkChrome
                        ? 'bg-white/[0.08] text-[#e8eef4] ring-1 ring-white/12'
                        : 'bg-slate-100 text-slate-700'
                    }
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

          <ThemeToggle variant="chrome" className={chromeClass} />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className={chromeClass} aria-label="Support">
                <FiHelpCircle className="w-4 h-4 shrink-0" strokeWidth={2} />
                <span className="hidden sm:inline">Support</span>
              </button>
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
