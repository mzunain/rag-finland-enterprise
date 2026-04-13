import React from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useLang } from '../lib/LangContext'

export default function Layout() {
  const { t, locale, switchLang } = useLang()

  React.useEffect(() => {
    const html = document.getElementById('html-root')
    if (html) html.setAttribute('lang', locale)
  }, [locale])

  return (
    <div className="min-h-screen bg-slate-50">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-3 focus:bg-blue-600 focus:text-white"
      >
        Skip to main content
      </a>
      <header className="bg-white border-b border-slate-200 shadow-sm" role="banner">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <h1 className="text-lg font-bold text-slate-800">{t('header.title')}</h1>
          <div className="flex items-center gap-4">
            <nav aria-label="Main navigation" className="flex gap-2 text-sm">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `px-3 py-1 rounded ${isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`
                }
                aria-current={({ isActive }) => (isActive ? 'page' : undefined)}
              >
                {t('nav.chat')}
              </NavLink>
              <NavLink
                to="/documents"
                className={({ isActive }) =>
                  `px-3 py-1 rounded ${isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`
                }
              >
                {t('nav.documents')}
              </NavLink>
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `px-3 py-1 rounded ${isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`
                }
              >
                {t('nav.admin')}
              </NavLink>
              <NavLink
                to="/analytics"
                className={({ isActive }) =>
                  `px-3 py-1 rounded ${isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`
                }
              >
                {t('nav.analytics')}
              </NavLink>
            </nav>
            <fieldset className="flex gap-1 border border-slate-200 rounded-lg p-0.5" role="radiogroup" aria-label="Language">
              <button
                role="radio"
                aria-checked={locale === 'en'}
                className={`px-2 py-1 text-xs rounded ${locale === 'en' ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-100'}`}
                onClick={() => switchLang('en')}
              >
                EN
              </button>
              <button
                role="radio"
                aria-checked={locale === 'fi'}
                className={`px-2 py-1 text-xs rounded ${locale === 'fi' ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-slate-100'}`}
                onClick={() => switchLang('fi')}
              >
                FI
              </button>
            </fieldset>
          </div>
        </div>
      </header>
      <main id="main-content" className="max-w-6xl mx-auto p-6" role="main">
        <Outlet />
      </main>
    </div>
  )
}
