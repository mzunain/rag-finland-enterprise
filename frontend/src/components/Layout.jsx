import React from 'react'
import { NavLink, Outlet } from 'react-router-dom'

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <h1 className="text-lg font-bold text-slate-800">RAG Finland Enterprise</h1>
          <nav className="flex gap-4 text-sm">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `px-3 py-1 rounded ${isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`
              }
            >
              Chat
            </NavLink>
            <NavLink
              to="/documents"
              className={({ isActive }) =>
                `px-3 py-1 rounded ${isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`
              }
            >
              Documents
            </NavLink>
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                `px-3 py-1 rounded ${isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`
              }
            >
              Admin
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto p-6">
        <Outlet />
      </main>
    </div>
  )
}
