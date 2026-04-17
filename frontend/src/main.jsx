import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LangProvider } from './lib/LangContext'
import { AuthProvider, useAuth } from './lib/AuthContext'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import ErrorBoundary from './components/ErrorBoundary'
import './index.css'

const queryClient = new QueryClient()
const ChatPage = React.lazy(() => import('./pages/ChatPage'))
const AdminPage = React.lazy(() => import('./pages/AdminPage'))
const DocumentsPage = React.lazy(() => import('./pages/DocumentsPage'))
const AnalyticsPage = React.lazy(() => import('./pages/AnalyticsPage'))

function PageFallback() {
  return (
    <div className="h-full w-full flex items-center justify-center bg-slate-50">
      <div className="w-72 space-y-2">
        <div className="h-4 rounded bg-slate-200 animate-pulse" />
        <div className="h-4 rounded bg-slate-200 animate-pulse" />
        <div className="h-4 rounded bg-slate-200 animate-pulse" />
      </div>
    </div>
  )
}

function AuthGate() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-slate-50">
        <div className="w-72 space-y-2">
          <div className="h-4 rounded bg-slate-200 animate-pulse" />
          <div className="h-4 rounded bg-slate-200 animate-pulse" />
        </div>
      </div>
    )
  }

  if (!user) return <LoginPage />

  return (
    <BrowserRouter>
      <React.Suspense fallback={<PageFallback />}>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<ChatPage />} />
            <Route path="admin" element={<AdminPage />} />
            <Route path="documents" element={<DocumentsPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
          </Route>
        </Routes>
      </React.Suspense>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <LangProvider>
        <ErrorBoundary>
          <AuthProvider>
            <AuthGate />
          </AuthProvider>
        </ErrorBoundary>
      </LangProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
