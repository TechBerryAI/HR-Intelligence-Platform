import React, { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useApp } from '@/core/context/AppContext.jsx'
import { useOrgPanel } from '@/core/context/OrgPanelContext.jsx'
import ThemeToggle from '@/shared/components/ThemeToggle.jsx'
import BrandMark from '@/shared/components/BrandMark.jsx'
import { useDeveloperMode } from '@/features/admin/hooks/useDeveloperMode.js'
import {
  LayoutDashboard,
  Users,
  User,
  Briefcase,
  Layers,
  Puzzle,
  Settings,
  Activity,
  LogOut,
  Menu,
  X,
} from 'lucide-react'

const headHrNavBase = [
  { label: 'Overview', path: '/head-hr', icon: LayoutDashboard, end: true, group: 'workspace' },
  { label: 'Admins', path: '/head-hr/admins', icon: Users, group: 'workspace' },
  { label: 'Candidates', path: '/head-hr/candidates', icon: User, group: 'workspace' },
  { label: 'Jobs', path: '/head-hr/jobs', icon: Briefcase, group: 'workspace' },
  { label: 'Bulk Parsing', path: '/head-hr/bulk-parsing', icon: Layers, group: 'tools' },
  { label: 'Integrations', path: '/head-hr/integrations', icon: Puzzle, group: 'tools' },
  { label: 'Settings', path: '/head-hr/settings', icon: Settings, group: 'tools' },
]

const ceoNav = [
  { label: 'Overview', path: '/ceo', icon: LayoutDashboard, end: true, group: 'workspace' },
  { label: 'Candidates', path: '/ceo/candidates', icon: User, group: 'workspace' },
  { label: 'Jobs', path: '/ceo/jobs', icon: Briefcase, group: 'workspace' },
]

const GROUP_LABELS = {
  workspace: 'Workspace',
  tools: 'Tools',
}

function initialsFromName(name) {
  if (!name || typeof name !== 'string') return 'HR'
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'HR'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

function groupNavItems(items) {
  const groups = []
  items.forEach((item) => {
    const key = item.group || 'workspace'
    const last = groups[groups.length - 1]
    if (!last || last.key !== key) {
      groups.push({ key, label: GROUP_LABELS[key] || key, items: [item] })
    } else {
      last.items.push(item)
    }
  })
  return groups
}

export default function OrgPanelLayout({ children, variant = 'head-hr' }) {
  const { logout, auth } = useApp()
  const { readOnly } = useOrgPanel()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const isCeoPanel = variant === 'ceo' || readOnly
  const { enabled: developerModeEnabled } = useDeveloperMode()
  const headHrNav = developerModeEnabled
    ? [
        ...headHrNavBase.slice(0, 6),
        { label: 'Developer Mode', path: '/head-hr/developer', icon: Activity, group: 'tools' },
        headHrNavBase[6],
      ]
    : headHrNavBase
  const navItems = isCeoPanel ? ceoNav : headHrNav
  const navGroups = groupNavItems(navItems)
  const displayEmail = auth?.email
  const displayName = auth?.fullName || (isCeoPanel ? 'CEO' : 'Head of HR')
  const companyLabel = auth?.company || ''
  const panelTitle = isCeoPanel ? 'Executive Panel' : 'Head of HR Panel'
  const roleLabel = isCeoPanel ? 'Read-only' : 'Administrator'
  const initials = initialsFromName(displayName)

  const handleLogout = () => {
    logout()
    navigate('/login/admin')
  }

  const Sidebar = ({ mobile = false }) => (
    <aside
      className={
        mobile
          ? 'org-sidebar relative flex flex-col h-full min-h-0'
          : 'org-sidebar hidden lg:flex flex-col w-[17.5rem] shrink-0 h-screen sticky top-0 self-start'
      }
    >
      <div className="org-sidebar-glow" aria-hidden />

      <div className="relative flex items-center gap-3 px-4 pt-5 pb-4 shrink-0">
        <BrandMark size="sm" />
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold tracking-tight text-[var(--ei-text-primary)] leading-none">
            HR Intelligence
          </p>
          <p className="mt-1 text-[11px] text-[var(--ei-text-muted)] truncate">{panelTitle}</p>
        </div>
        {mobile ? (
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="p-2 rounded-xl text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)] hover:bg-[var(--ei-surface-hover)] transition-colors"
            aria-label="Close menu"
          >
            <X className="w-4 h-4" strokeWidth={2} />
          </button>
        ) : null}
      </div>

      <div className="relative mx-3 mb-4 shrink-0">
        <div className="org-sidebar-identity">
          <div className="org-sidebar-avatar" aria-hidden>
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-[var(--ei-text-primary)] truncate leading-tight">{displayName}</p>
            {displayEmail ? (
              <p className="mt-0.5 text-[11px] text-[var(--ei-text-muted)] truncate">{displayEmail}</p>
            ) : null}
            {companyLabel ? (
              <p className="mt-0.5 text-[11px] text-[var(--ei-text-secondary)] truncate" title={companyLabel}>
                {companyLabel}
              </p>
            ) : null}
            <span className={`org-role-pill ${isCeoPanel ? 'org-role-pill-readonly' : ''}`}>{roleLabel}</span>
          </div>
        </div>
      </div>

      <nav className="relative px-3 pb-4 space-y-4 flex-1 overflow-y-auto min-h-0">
        {navGroups.map((group) => (
          <div key={group.key}>
            <p className="org-nav-section">{group.label}</p>
            <div className="space-y-1">
              {group.items.map(({ label, path, icon: Icon, end }) => (
                <NavLink
                  key={path}
                  to={path}
                  end={end}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) => `org-nav-item ${isActive ? 'org-nav-item-active' : ''}`}
                >
                  <span className="org-nav-icon">
                    <Icon className="w-4 h-4" strokeWidth={1.85} />
                  </span>
                  <span className="min-w-0 truncate">{label}</span>
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="relative px-3 pt-3 pb-5 shrink-0 org-sidebar-footer">
        <button type="button" onClick={handleLogout} className="org-sidebar-logout">
          <span className="org-nav-icon">
            <LogOut className="w-4 h-4" strokeWidth={1.85} />
          </span>
          Logout
        </button>
      </div>
    </aside>
  )

  return (
    <div className="org-shell flex h-[100dvh] max-h-[100dvh] overflow-hidden">
      <Sidebar />

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <div className="relative z-50 h-full w-[17.5rem] max-w-[85vw] shadow-[8px_0_40px_rgba(0,0,0,0.35)]">
            <Sidebar mobile />
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-[var(--ei-border-primary)] bg-[var(--ei-surface-glass)] backdrop-blur-xl shrink-0">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="text-[var(--ei-text-muted)] hover:text-[var(--ei-text-primary)] p-2 rounded-xl hover:bg-[var(--ei-surface-hover)] transition-all duration-[180ms]"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" strokeWidth={2} />
          </button>
          <span className="flex items-center gap-2.5 flex-1 min-w-0">
            <BrandMark size="sm" />
            <span className="text-sm font-semibold text-[var(--ei-text-primary)] truncate">{panelTitle}</span>
          </span>
          <ThemeToggle variant="org" compact />
        </div>

        <main className="flex-1 min-h-0 overflow-y-auto p-6 sm:p-7 lg:p-9">
          <div className="mx-auto w-full max-w-[1500px]">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
