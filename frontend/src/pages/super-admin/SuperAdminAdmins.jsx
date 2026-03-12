import React, { useEffect, useState } from 'react'
import { apiRequest } from '../../utils/api.js'
import { tokenService } from '../../utils/tokenService.js'
import { useApp } from '../../context/AppContext.jsx'
import SuperAdminLayout from './SuperAdminLayout.jsx'
import { FiTrash2, FiRefreshCw, FiUsers, FiSearch, FiDownload, FiPlus } from 'react-icons/fi'
import { generateAdminsPdf } from '../../utils/pdfReportUtils.js'

function formatDate(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function SuperAdminAdmins() {
  const { auth } = useApp()
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
  const isSuperAdmin = auth?.role === 'super_admin'

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const token = tokenService.getToken()
      const data = await apiRequest('/api/super-admin/admins', { method: 'GET', token })
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
      await apiRequest('/api/super-admin/admins', {
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
      await apiRequest(`/api/super-admin/admins/${hrid}`, { method: 'DELETE', token })
      setAdmins((prev) => prev.filter((a) => a.hrid !== hrid))
      showToast('Admin deleted successfully')
    } catch (err) {
      showToast(err?.message || 'Failed to delete admin', 'error')
    } finally {
      setDeleting(null)
      setConfirmDelete(null)
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

  return (
    <SuperAdminLayout>
      {/* Toast */}
      {toast && (
        <div
          className={`fixed top-20 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-xl text-sm font-medium transition-all ${
            toast.type === 'error'
              ? 'bg-red-500/20 border border-red-500/30 text-red-300'
              : 'bg-green-500/20 border border-green-500/30 text-green-300'
          }`}
        >
          {toast.msg}
        </div>
      )}

      {/* Create admin modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-md rounded-2xl bg-zinc-900 border border-zinc-700 p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-white">Create Admin Account</h3>
            <p className="mt-1 text-sm text-zinc-400">New HR admin can log in and create jobs, manage candidates.</p>
            <form onSubmit={handleCreateAdmin} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Email</label>
                <input
                  type="email"
                  value={createForm.email}
                  onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder:text-zinc-500 focus:outline-none focus:border-white/40 text-sm"
                  placeholder="hr@company.com"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Full name</label>
                <input
                  type="text"
                  value={createForm.fullName}
                  onChange={(e) => setCreateForm((f) => ({ ...f, fullName: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder:text-zinc-500 focus:outline-none focus:border-white/40 text-sm"
                  placeholder="Jane Doe"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Company</label>
                <input
                  type="text"
                  value={createForm.company}
                  onChange={(e) => setCreateForm((f) => ({ ...f, company: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder:text-zinc-500 focus:outline-none focus:border-white/40 text-sm"
                  placeholder="Acme Inc"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Password (min 6 characters)</label>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-white placeholder:text-zinc-500 focus:outline-none focus:border-white/40 text-sm"
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

      {/* Confirm dialog */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
          <div className="w-full max-w-sm rounded-2xl bg-zinc-900 border border-zinc-700 p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-white">Delete Admin?</h3>
            <p className="mt-2 text-sm text-zinc-400">
              This will permanently delete admin{' '}
              <span className="text-white font-medium">{confirmDelete.full_name}</span> ({confirmDelete.hrid}). Their jobs and login data will also be removed.
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
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <FiUsers className="w-5 h-5 text-zinc-300" /> HR Admins
          </h1>
          <p className="mt-0.5 text-sm text-zinc-400">{admins.length} admin{admins.length !== 1 ? 's' : ''} registered</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 transition-colors border border-emerald-500/30"
          >
            <FiPlus className="w-4 h-4" /> Create Admin
          </button>
          <button
            onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-white bg-zinc-800 hover:bg-zinc-700 transition-colors border border-zinc-700"
          >
            <FiRefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button
            onClick={() => generateAdminsPdf(filtered.length ? filtered : admins)}
            disabled={admins.length === 0}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
          >
            <FiDownload className="w-4 h-4" /> Download Report
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-5">
        <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
        <input
          type="text"
          placeholder="Search by name, email, company or ID…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-white/40 transition-colors"
        />
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">{error}</div>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-zinc-900/60 border border-zinc-800 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-zinc-500 text-sm">
          {search ? 'No admins match your search.' : 'No admins found.'}
        </div>
      ) : (
        <div className="rounded-2xl border border-zinc-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/80">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">ID</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Name</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Email</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Company</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Joined</th>
                  {isSuperAdmin && <th className="text-right px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {filtered.map((admin) => (
                  <tr key={admin.hrid} className="bg-zinc-900/30 hover:bg-zinc-800/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-amber-400">{admin.hrid}</td>
                    <td className="px-4 py-3 text-zinc-100 font-medium">{admin.full_name || '—'}</td>
                    <td className="px-4 py-3 text-zinc-400">{admin.email}</td>
                    <td className="px-4 py-3 text-zinc-400">{admin.company || '—'}</td>
                    <td className="px-4 py-3 text-zinc-500">{formatDate(admin.created_at)}</td>
                    {isSuperAdmin && (
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setConfirmDelete(admin)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 hover:bg-red-500/10 hover:text-red-300 border border-red-500/20 hover:border-red-500/40 transition-all"
                        >
                          <FiTrash2 className="w-3.5 h-3.5" /> Delete
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </SuperAdminLayout>
  )
}
