import React, { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext.jsx'
import { useOrgPanel } from '../../context/OrgPanelContext.jsx'
import {
  FiGrid, FiUsers, FiUser, FiBriefcase, FiFileText, FiLogOut, FiMenu, FiX, FiShield, FiSettings, FiBarChart2,
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
  const PanelIcon = isCeoPanel ? FiBarChart2 : FiShield

  const handleLogout = () => {
    logout()
    navigate('/login/admin')
  }

  const Sidebar = ({ mobile = false }) => (
    <aside
      className={
        mobile
          ? 'flex flex-col h-full'
          : 'hidden lg:flex flex-col w-60 min-h-screen bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700'
      }
    >
      <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-200 dark:border-slate-700">
        <div className="w-9 h-9 rounded-xl bg-primary dark:bg-accent-blue text-white grid place-items-center flex-shrink-0">
          <PanelIcon className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-bold text-slate-900 dark:text-white truncate">{displayName}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{displayEmail || ''}</p>
          {isCeoPanel && (
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">Read-only access</p>
          )}
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map(({ label, path, icon: Icon, end }) => (
          <NavLink
            key={path}
            to={path}
            end={end}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white border border-slate-200 dark:border-slate-600'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-800/50'
              }`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 pb-5 border-t border-slate-200 dark:border-slate-700 pt-3">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-all duration-150"
        >
          <FiLogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </aside>
  )

  return (
    <div className="flex flex-1 min-h-0 bg-slate-50 dark:bg-slate-900">
      <Sidebar />

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <div className="relative z-50 flex flex-col w-64 h-full bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between px-4 py-4 border-b border-slate-200 dark:border-slate-700">
              <span className="text-sm font-semibold text-slate-900 dark:text-white">{panelTitle}</span>
              <button onClick={() => setSidebarOpen(false)} className="text-slate-500 hover:text-slate-700 dark:hover:text-white p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800">
                <FiX className="w-5 h-5" />
              </button>
            </div>
            <Sidebar mobile />
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900/80">
          <button onClick={() => setSidebarOpen(true)} className="text-slate-500 hover:text-slate-700 dark:hover:text-white p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800">
            <FiMenu className="w-5 h-5" />
          </button>
          <span className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
            <PanelIcon className="w-4 h-4" /> {panelTitle}
          </span>
        </div>

        <main className="flex-1 overflow-auto p-5 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
