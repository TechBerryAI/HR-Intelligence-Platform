import React from 'react'
import { Outlet } from 'react-router-dom'
import Navbar from '../components/Navbar.jsx'
import { PageContainer } from '../components/PageContainer.jsx'

/**
 * Layout for admin/head-hr pages with sidebar.
 * Uses same page container for content area.
 */
export default function AdminLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Navbar />
      <main className="flex-1">
        <PageContainer>
          <Outlet />
        </PageContainer>
      </main>
      <footer className="py-6 text-center text-sm text-slate-500 border-t border-slate-200">
        © {new Date().getFullYear()} Job Portal
      </footer>
    </div>
  )
}
