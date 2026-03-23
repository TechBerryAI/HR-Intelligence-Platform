import React from 'react'
import { Outlet } from 'react-router-dom'
import Navbar from '../components/Navbar.jsx'

export default function MainLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Navbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="py-8 text-center text-sm text-slate-500 border-t border-slate-200">
        © {new Date().getFullYear()} Job Portal
      </footer>
    </div>
  )
}
