import React, { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { useOrgPanel } from '@/core/context/OrgPanelContext.jsx'
import {
  FiGrid, FiUsers, FiBriefcase, FiLogOut, FiMenu, FiX, FiShield, FiSettings, FiBarChart2,
} from 'react-icons/fi'

const headHrNav = [
  { label: 'Overview', path: '/head-hr', icon: FiGrid, end: true },
  { label: 'Admins', path: '/head-hr/admins', icon: FiUsers },
  { label: 'Jobs', path: '/head-hr/jobs', icon: FiBriefcase },
  { label: 'Settings', path: '/head-hr/settings', icon: FiSettings },
]

const ceoNav = [
  { label: 'Overview', path: '/ceo', icon: FiGrid, end: true },
  { label: 'Jobs', path: '/ceo/jobs', icon: FiBriefcase },
]

function initialsFromName(name) {
  if (!name || typeof name !== 'string') return 'HR'
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'HR'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

export default function OrgPanelLayout({ children, variant = 'head-hr' }) {
  const { logout, auth } = useApp()
  const { readOnly } = useOrgPanel()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const isCeoPanel = variant === 'ceo' || readOnly
  const navItems = isCeoPanel ? ceoNav : headHrNav
  const displayEmail = auth?.email
  const displayName = auth?.fullName || (isCeoPanel ? 'CEO' : 'Head of HR')
  const panelTitle = isCeoPanel ? 'Executive Panel' : 'Head of HR Panel'
  const roleLabel = isCeoPanel ? 'Executive' : 'Administrator'
  const PanelIcon = isCeoPanel ? FiBarChart2 : FiShield
  const initials = initialsFromName(displayName)

  const handleLogout = () => {
    logout()
    navigate('/login/admin')
  }

  const Sidebar = ({ mobile = false }) => (
    <aside
      className={
        mobile
          ? 'flex flex-col h-full'
          : 'org-sidebar hidden lg:flex flex-col w-60 min-h-screen'
      }
    >
      <div className="flex items-center gap-3 px-5 py-5 border-b border-white/[0.08]">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#00A6FF] to-[#276DFF] text-white grid place-items-center flex-shrink-0 text-xs font-bold shadow-[0_0_20px_rgba(0,166,255,0.25)]">
          {initials}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#F5F7FA] truncate">{displayName}</p>
          <p className="text-xs text-[#8E9BA8] truncate">{displayEmail || ''}</p>
          <p className="text-[10px] uppercase tracking-[0.08em] text-[#00A6FF]/80 mt-1">
            {isCeoPanel ? 'Read-only access' : roleLabel}
          </p>
        </div>
      </div>

      <nav className="px-3 py-4 space-y-1">
        {navItems.map(({ label, path, icon: Icon, end }) => (
          <NavLink
            key={path}
            to={path}
            end={end}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `org-nav-item ${isActive ? 'org-nav-item-active' : ''}`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 pt-1 pb-5 mt-1 border-t border-white/[0.08]">
        <button
          type="button"
          onClick={handleLogout}
          className="org-nav-item w-full mt-2 text-[#FF8FA3] hover:text-[#FFB0BC] hover:bg-[rgba(255,102,133,0.08)]"
        >
          <FiLogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
      <div className="flex-1" aria-hidden />
    </aside>
  )

  return (
    <div className="org-shell flex flex-1 min-h-0">
      <Sidebar />

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <div className="org-sidebar relative z-50 flex flex-col w-64 h-full border-r border-white/[0.08]">
            <div className="flex items-center justify-between px-4 py-4 border-b border-white/[0.08]">
              <span className="text-sm font-semibold text-[#F5F7FA] flex items-center gap-2">
                <PanelIcon className="w-4 h-4 text-[#00A6FF]" /> {panelTitle}
              </span>
              <button
                type="button"
                onClick={() => setSidebarOpen(false)}
                className="text-[#8E9BA8] hover:text-white p-2 rounded-xl hover:bg-white/[0.05] transition-all duration-[180ms]"
              >
                <FiX className="w-5 h-5" />
              </button>
            </div>
            <Sidebar mobile />
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-white/[0.08] bg-[rgba(13,20,27,0.88)] backdrop-blur-xl">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="text-[#8E9BA8] hover:text-white p-2 rounded-xl hover:bg-white/[0.05] transition-all duration-[180ms]"
          >
            <FiMenu className="w-5 h-5" />
          </button>
          <span className="text-sm font-semibold text-[#F5F7FA] flex items-center gap-2">
            <PanelIcon className="w-4 h-4 text-[#00A6FF]" /> {panelTitle}
          </span>
        </div>

        <main className="flex-1 overflow-auto p-6 sm:p-7 lg:p-9">
          <div className="mx-auto w-full max-w-[1500px]">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
