import React from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useLang } from '../lib/LangContext'
import { useAuth } from '../lib/AuthContext'

const navItems = [
  { to: '/', end: true, key: 'chat' },
  { to: '/documents', key: 'documents' },
  { to: '/admin', key: 'admin' },
  { to: '/analytics', key: 'analytics' },
]

export default function Layout() {
  const { t, locale, switchLang } = useLang()
  const { user, logout } = useAuth()

  React.useEffect(() => {
    const html = document.getElementById('html-root')
    if (html) html.setAttribute('lang', locale)
  }, [locale])

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-3 focus:bg-blue-600 focus:text-white focus:rounded-lg focus:m-2"
      >
        Skip to main content
      </a>

      <header className="flex-shrink-0 bg-white border-b border-slate-200 z-40" role="banner">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
                <span className="text-white font-bold text-xs">RF</span>
              </div>
              <span className="text-sm font-bold text-slate-800 hidden sm:block">RAG Finland</span>
            </div>

            <nav aria-label="Main navigation" className="flex items-center gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.key}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'
                    }`
                  }
                >
                  {t(`nav.${item.key}`)}
                </NavLink>
              ))}
            </nav>

            <div className="flex items-center gap-2">
              <fieldset className="flex bg-slate-100 rounded-lg p-0.5" role="radiogroup" aria-label="Language">
                {['en', 'fi', 'sv'].map((lang) => (
                  <button
                    key={lang}
                    role="radio"
                    aria-checked={locale === lang}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                      locale === lang ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                    }`}
                    onClick={() => switchLang(lang)}
                  >
                    {lang.toUpperCase()}
                  </button>
                ))}
              </fieldset>
              {user && (
                <div className="flex items-center gap-2 ml-2 pl-2 border-l border-slate-200">
                  <span className="text-xs text-slate-500">{user.username}</span>
                  <button
                    onClick={logout}
                    className="text-xs text-slate-400 hover:text-red-600 transition-colors"
                  >
                    {t('login.signOut')}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <main id="main-content" className="flex-1 overflow-hidden" role="main">
        <Outlet />
      </main>
    </div>
  )
}
