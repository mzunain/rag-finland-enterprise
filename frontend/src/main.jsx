import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LangProvider } from './lib/LangContext'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import ChatPage from './pages/ChatPage'
import AdminPage from './pages/AdminPage'
import DocumentsPage from './pages/DocumentsPage'
import './index.css'

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <LangProvider>
        <ErrorBoundary>
          <BrowserRouter>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<ChatPage />} />
                <Route path="admin" element={<AdminPage />} />
                <Route path="documents" element={<DocumentsPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ErrorBoundary>
      </LangProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
