import React, { useEffect, useState } from 'react'
import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'
import { useApp } from '@/core/context/AppContext.jsx'
import { isHeadHr } from '@/core/permissions/rbac.js'
import { useAsyncAction } from '@/shared/hooks/useAsyncAction.js'
import HeadHrLayout from './HeadHrLayout.jsx'
import PasswordInput from '@/shared/components/PasswordInput.jsx'
import { FiTrash2, FiRefreshCw, FiSearch, FiDownload, FiPlus, FiArrowUp, FiArrowDown, FiEdit2 } from 'react-icons/fi'
import { Users } from 'lucide-react'
import { generateAdminsPdf } from '@/shared/utils/pdfReportUtils.js'

const Spinner = () => (
  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
)

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function HeadHrAdmins() {
  const { auth } = useApp()
  const { run: runRefresh, loading: refreshLoading } = useAsyncAction()
  const { run: runReport, loading: reportLoading } = useAsyncAction()
  const [admins, setAdmins] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [deleting, setDeleting] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [toast, setToast] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({ email: '', fullName: '', company: '', password: '' })
  const [creating, setCreating] = useState(false)
  const [editingAdmin, setEditingAdmin] = useState(null)
  const [editForm, setEditForm] = useState({ fullName: '', company: '', password: '' })
  const [editSaving, setEditSaving] = useState(false)
  const canManageAdmins = isHeadHr(auth)
  const [idOrder, setIdOrder] = useState('desc') // 'asc' | 'desc'

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const token = tokenService.getToken()
      const data = await apiRequest('/api/head-hr/admins', { method: 'GET', token })
      setAdmins(data.admins || [])
    } catch (err) {
      setError(err?.message || 'Failed to load admins')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleCreateAdmin = async (e) => {
    e.preventDefault()
    if (!createForm.email?.trim() || !createForm.fullName?.trim() || !createForm.company?.trim() || !createForm.password || createForm.password.length < 6) {
      showToast('Please fill all fields; password must be at least 6 characters', 'error')
      return
    }
    setCreating(true)
    try {
      const token = tokenService.getToken()
      await apiRequest('/api/head-hr/admins', {
        method: 'POST',
        token,
        body: {
          email: createForm.email.trim().toLowerCase(),
          fullName: createForm.fullName.trim(),
          company: createForm.company.trim(),
          password: createForm.password,
        },
      })
      setShowCreate(false)
      setCreateForm({ email: '', fullName: '', company: '', password: '' })
      load()
      showToast('Admin account created successfully')
    } catch (err) {
      showToast(err?.message || 'Failed to create admin', 'error')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (hrid) => {
    setDeleting(hrid)
    try {
      const token = tokenService.getToken()
      await apiRequest(`/api/head-hr/admins/${hrid}`, { method: 'DELETE', token })
      setAdmins((prev) => prev.filter((a) => a.hrid !== hrid))
      showToast('Admin deleted successfully')
    } catch (err) {
      showToast(err?.message || 'Failed to delete admin', 'error')
    } finally {
      setDeleting(null)
      setConfirmDelete(null)
    }
  }

  const openEditAdmin = (admin) => {
    setEditingAdmin(admin)
    setEditForm({
      fullName: admin.full_name || '',
      company: admin.company || '',
      password: '',
    })
  }

  const closeEditAdmin = () => {
    setEditingAdmin(null)
    setEditForm({ fullName: '', company: '', password: '' })
  }

  const handleEditAdmin = async (e) => {
    e.preventDefault()
    if (!editingAdmin?.hrid) return
    if (!editForm.fullName?.trim() || !editForm.company?.trim()) {
      showToast('Full name and company are required', 'error')
      return
    }
    if (editForm.password && editForm.password.length < 6) {
      showToast('Password must be at least 6 characters', 'error')
      return
    }
    setEditSaving(true)
    try {
      const token = tokenService.getToken()
      const body = {
        fullName: editForm.fullName.trim(),
        company: editForm.company.trim(),
      }
      if (editForm.password) body.password = editForm.password
      await apiRequest(`/api/head-hr/admins/${encodeURIComponent(editingAdmin.hrid)}`, {
        method: 'PUT',
        token,
        body,
      })
      closeEditAdmin()
      load()
      showToast('Admin updated successfully')
    } catch (err) {
      showToast(err?.message || 'Failed to update admin', 'error')
    } finally {
      setEditSaving(false)
    }
  }

  const filtered = admins.filter(
    (a) =>
      !search ||
      a.full_name?.toLowerCase().includes(search.toLowerCase()) ||
      a.email?.toLowerCase().includes(search.toLowerCase()) ||
      a.company?.toLowerCase().includes(search.toLowerCase()) ||
      a.hrid?.toLowerCase().includes(search.toLowerCase()),
  )

  const sortedAdmins = [...filtered].sort((a, b) => {
    const numA = parseInt((a.hrid || '').replace(/\D/g, '') || '0', 10)
    const numB = parseInt((b.hrid || '').replace(/\D/g, '') || '0', 10)
    return idOrder === 'asc' ? numA - numB : numB - numA
  })

  return (
    <HeadHrLayout>
      {/* Toast */}
      {toast && (
        <div
          className={`fixed top-20 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl text-sm font-medium transition-all ${
            toast.type === 'error'
              ? 'bg-red-50 dark:bg-red-500/20 border border-red-200 dark:border-red-500/30 text-red-700 dark:text-red-300'
              : 'bg-green-50 dark:bg-green-500/20 border border-green-200 dark:border-green-500/30 text-green-700 dark:text-green-300'
          }`}
        >
          {toast.msg}
        </div>
      )}

      {/* Create admin modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-2xl bg-[var(--ei-bg-secondary)] border border-[var(--ei-border-primary)] p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-[var(--ei-text-primary)]">Create Admin Account</h3>
            <p className="mt-1 text-sm text-[var(--ei-text-muted)]">New HR admin can log in and create jobs, manage candidates.</p>
            <form onSubmit={handleCreateAdmin} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">Email</label>
                <input
                  type="email"
                  value={createForm.email}
                  onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] text-[var(--ei-text-primary)] placeholder:text-[var(--ei-text-placeholder)] focus:outline-none focus:border-white/40 text-sm"
                  placeholder="hr@company.com"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">Full name</label>
                <input
                  type="text"
                  value={createForm.fullName}
                  onChange={(e) => setCreateForm((f) => ({ ...f, fullName: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] text-[var(--ei-text-primary)] placeholder:text-[var(--ei-text-placeholder)] focus:outline-none focus:border-white/40 text-sm"
                  placeholder="Jane Doe"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">Company</label>
                <input
                  type="text"
                  value={createForm.company}
                  onChange={(e) => setCreateForm((f) => ({ ...f, company: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] text-[var(--ei-text-primary)] placeholder:text-[var(--ei-text-placeholder)] focus:outline-none focus:border-white/40 text-sm"
                  placeholder="Acme Inc"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">Password (min 6 characters)</label>
                <PasswordInput
                  value={createForm.password}
                  onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
                  className="px-3 py-2 rounded-lg bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] text-[var(--ei-text-primary)] placeholder:text-[var(--ei-text-placeholder)] focus:outline-none focus:border-white/40 text-sm"
                  placeholder="••••••••"
                  minLength={6}
                  required
                />
              </div>
              <div className="flex gap-3 justify-end pt-2">
                <button
                  type="button"
                  onClick={() => { setShowCreate(false); setCreateForm({ email: '', fullName: '', company: '', password: '' }) }}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-zinc-300 bg-zinc-800 hover:bg-zinc-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 transition-colors"
                >
                  {creating ? 'Creating…' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit admin modal */}
      {editingAdmin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-2xl bg-[var(--ei-bg-secondary)] border border-[var(--ei-border-primary)] p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-[var(--ei-text-primary)]">Edit Admin</h3>
            <p className="mt-1 text-sm text-[var(--ei-text-muted)]">
              Update profile for {editingAdmin.email} ({editingAdmin.hrid}).
            </p>
            <form onSubmit={handleEditAdmin} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">Email</label>
                <input
                  type="email"
                  value={editingAdmin.email || ''}
                  disabled
                  className="w-full px-3 py-2 rounded-lg bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] text-[var(--ei-text-muted)] opacity-70 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">Full name</label>
                <input
                  type="text"
                  value={editForm.fullName}
                  onChange={(e) => setEditForm((f) => ({ ...f, fullName: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] text-[var(--ei-text-primary)] placeholder:text-[var(--ei-text-placeholder)] focus:outline-none focus:border-white/40 text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">Company</label>
                <input
                  type="text"
                  value={editForm.company}
                  onChange={(e) => setEditForm((f) => ({ ...f, company: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] text-[var(--ei-text-primary)] placeholder:text-[var(--ei-text-placeholder)] focus:outline-none focus:border-white/40 text-sm"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--ei-text-muted)] mb-1">
                  New password (optional)
                </label>
                <PasswordInput
                  value={editForm.password}
                  onChange={(e) => setEditForm((f) => ({ ...f, password: e.target.value }))}
                  className="px-3 py-2 rounded-lg bg-[var(--ei-surface-input)] border border-[var(--ei-border-primary)] text-[var(--ei-text-primary)] placeholder:text-[var(--ei-text-placeholder)] focus:outline-none focus:border-white/40 text-sm"
                  placeholder="Leave blank to keep current"
                  minLength={6}
                />
              </div>
              <div className="flex gap-3 justify-end pt-2">
                <button
                  type="button"
                  onClick={closeEditAdmin}
                  disabled={editSaving}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-[var(--ei-text-secondary)] bg-[var(--ei-surface-hover)] hover:bg-[var(--ei-surface-hover)] border border-[var(--ei-border-primary)] transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editSaving}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 transition-colors"
                >
                  {editSaving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Confirm dialog */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-sm rounded-2xl bg-[var(--ei-bg-secondary)] border border-[var(--ei-border-primary)] p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-[var(--ei-text-primary)]">Delete Admin?</h3>
            <p className="mt-2 text-sm text-[var(--ei-text-muted)]">
              This will permanently delete admin{' '}
              <span className="text-[var(--ei-text-primary)] font-medium">{confirmDelete.full_name}</span> ({confirmDelete.hrid}). Their jobs and login data will also be removed.
            </p>
            <div className="mt-5 flex gap-3 justify-end">
              <button
                onClick={() => setConfirmDelete(null)}
                className="px-4 py-2 rounded-lg text-sm font-medium text-zinc-300 bg-zinc-800 hover:bg-zinc-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(confirmDelete.hrid)}
                disabled={deleting === confirmDelete.hrid}
                className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-500 disabled:opacity-50 transition-colors"
              >
                {deleting === confirmDelete.hrid ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="org-page-title flex items-center gap-2">
            <Users size={32} className="org-page-icon" /> HR Admins
          </h1>
          <p className="org-page-subtitle">{admins.length} admin{admins.length !== 1 ? 's' : ''} registered</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {canManageAdmins && (
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors border border-emerald-500/30 shadow-sm"
            >
              <FiPlus className="w-4 h-4" /> Create Admin
            </button>
          )}
          <button
            onClick={() => runRefresh(load)}
            disabled={refreshLoading}
            className="org-btn-secondary"
          >
            {refreshLoading ? <Spinner /> : <FiRefreshCw className="w-4 h-4" />}
            {refreshLoading ? 'Refreshing…' : 'Refresh'}
          </button>
          <button
            onClick={() => runReport(() => { generateAdminsPdf(sortedAdmins.length ? sortedAdmins : admins) })}
            disabled={admins.length === 0 || reportLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            {reportLoading ? <Spinner /> : <FiDownload className="w-4 h-4" />}
            {reportLoading ? 'Preparing…' : 'Download Report'}
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-5">
        <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          placeholder="Search by name, email, company or ID…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="org-search-input"
        />
      </div>

      {error && (
        <div className="org-error-banner">{error}</div>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="org-skeleton" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="org-empty-state">
          {search ? 'No admins match your search.' : 'No admins found.'}
        </div>
      ) : (
        <div className="org-table-wrap">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="org-table-head">
                  <th className="org-th">
                    <button
                      type="button"
                      onClick={() => setIdOrder((o) => (o === 'asc' ? 'desc' : 'asc'))}
                      className="flex items-center gap-1.5 hover:text-slate-900 dark:hover:text-white transition-colors"
                      title={idOrder === 'asc' ? 'Click for descending' : 'Click for ascending'}
                    >
                      ID
                      {idOrder === 'asc' ? <FiArrowUp className="w-3.5 h-3.5" /> : <FiArrowDown className="w-3.5 h-3.5" />}
                    </button>
                  </th>
                  <th className="org-th">Name</th>
                  <th className="org-th">Email</th>
                  <th className="org-th">Company</th>
                  <th className="org-th">Joined</th>
                  {canManageAdmins && <th className="org-th text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                {sortedAdmins.map((admin) => (
                  <tr key={admin.hrid} className="org-table-row">
                    <td className="px-4 py-3 font-mono text-xs text-amber-600 dark:text-amber-400">{admin.hrid}</td>
                    <td className="org-td-primary">{admin.full_name || '—'}</td>
                    <td className="org-td-secondary">{admin.email}</td>
                    <td className="org-td-secondary">{admin.company || '—'}</td>
                    <td className="org-td-muted">{formatDate(admin.created_at)}</td>
                    {canManageAdmins && (
                      <td className="px-4 py-3 text-right whitespace-nowrap w-[1%]">
                        <div className="inline-flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => openEditAdmin(admin)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[var(--ei-text-primary)] hover:bg-[var(--ei-surface-hover)] border border-[var(--ei-border-primary)] transition-all"
                          >
                            <FiEdit2 className="w-3.5 h-3.5" /> Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDelete(admin)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 border border-red-200 dark:border-red-500/30 hover:border-red-300 dark:hover:border-red-500/50 transition-all"
                          >
                            <FiTrash2 className="w-3.5 h-3.5" /> Delete
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </HeadHrLayout>
  )
}
