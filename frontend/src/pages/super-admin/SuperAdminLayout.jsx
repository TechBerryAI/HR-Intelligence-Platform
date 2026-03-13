import React, { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useApp } from '../../context/AppContext.jsx'
import {
  FiGrid, FiUsers, FiUser, FiBriefcase, FiFileText, FiLogOut, FiMenu, FiX, FiShield,
} from 'react-icons/fi'

const navItems = [
  { label: 'Overview', path: '/super-admin', icon: FiGrid, end: true },
  { label: 'Admins', path: '/super-admin/admins', icon: FiUsers },
  { label: 'Candidates', path: '/super-admin/candidates', icon: FiUser },
  { label: 'Jobs', path: '/super-admin/jobs', icon: FiBriefcase },
  { label: 'Applications', path: '/super-admin/applications', icon: FiFileText },
]

export default function SuperAdminLayout({ children }) {
  const { logoutSuperAdmin, logout, auth, superAdminAuth } = useApp()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const isHeadHr = auth?.isLoggedIn && auth?.role === 'head_hr'
  const displayEmail = isHeadHr ? auth?.email : superAdminAuth?.email
  const displayName = isHeadHr ? (auth?.fullName || 'Head of HR') : (superAdminAuth?.name || 'Super Admin')
  const panelLabel = isHeadHr ? 'Head of HR' : 'Super Admin'

  const handleLogout = () => {
    if (isHeadHr) {
      logout()
      navigate('/login/admin')
    } else {
      logoutSuperAdmin()
      navigate('/login/admin')
    }
  }

  const Sidebar = ({ mobile = false }) => (
    <aside
      className={
        mobile
          ? 'flex flex-col h-full'
          : 'hidden lg:flex flex-col w-60 min-h-screen bg-zinc-900/60 border-r border-zinc-800 backdrop-blur-sm'
      }
    >
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-zinc-800">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white grid place-items-center shadow-lg flex-shrink-0">
          <FiShield className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-bold text-white truncate">{displayName}</p>
          <p className="text-xs text-zinc-500 truncate">{displayEmail || ''}</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map(({ label, path, icon: Icon, end }) => (
          <NavLink
            key={path}
            to={path}
            end={end}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-white/10 text-white border border-white/15'
                  : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800'
              }`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Logout */}
      <div className="px-3 pb-5 border-t border-zinc-800 pt-3">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-all duration-150"
        >
          <FiLogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </aside>
  )

  return (
    <div className="flex flex-1 min-h-0">
      <Sidebar />

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <div className="relative z-50 flex flex-col w-64 h-full bg-zinc-900 border-r border-zinc-800">
            <div className="flex items-center justify-between px-4 py-4">
              <span className="text-sm font-semibold text-white">{panelLabel} Panel</span>
              <button onClick={() => setSidebarOpen(false)} className="text-zinc-400 hover:text-white">
                <FiX className="w-5 h-5" />
              </button>
            </div>
            <Sidebar mobile />
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile topbar */}
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-zinc-800 bg-zinc-900/50">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-zinc-400 hover:text-white transition-colors"
          >
            <FiMenu className="w-5 h-5" />
          </button>
          <span className="text-sm font-semibold text-white flex items-center gap-2">
            <FiShield className="w-4 h-4" /> {panelLabel} Panel
          </span>
        </div>

        <main className="flex-1 overflow-auto p-5 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
