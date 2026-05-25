import React from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  BarChart3,
  Bot,
  Database,
  FileText,
  Globe2,
  LockKeyhole,
  LogOut,
  Menu,
  MessageSquareWarning,
  ServerCog,
  ShieldCheck,
  X,
} from 'lucide-react'
import { useLang } from '../lib/LangContext'
import { useAuth } from '../lib/AuthContext'
import { cn, StatusBadge } from './ProductUI'

const navItems = [
  { to: '/', end: true, key: 'chat', icon: Bot, meta: 'Ask and verify' },
  { to: '/documents', key: 'documents', icon: FileText, meta: 'Evidence library' },
  { to: '/admin', key: 'admin', icon: ServerCog, meta: 'Governance' },
  { to: '/reviews', key: 'reviews', icon: MessageSquareWarning, meta: 'Review queue' },
  { to: '/analytics', key: 'analytics', icon: BarChart3, meta: 'Usage quality' },
]

function BrandMark() {
  return (
    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-950 text-white shadow-sm">
      <ShieldCheck className="h-5 w-5" aria-hidden="true" />
    </div>
  )
}

function NavList({ t, onNavigate }) {
  return (
    <nav aria-label="Main navigation" className="space-y-1.5">
      {navItems.map((item) => {
        const Icon = item.icon
        return (
          <NavLink
            key={item.key}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition',
                isActive
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950',
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={cn(
                    'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg',
                    isActive ? 'bg-white/15 text-white' : 'bg-white text-slate-500 ring-1 ring-slate-200 group-hover:text-blue-700',
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="min-w-0">
                  <span className="block font-semibold">{t(`nav.${item.key}`)}</span>
                  <span className={cn('block truncate text-xs', isActive ? 'text-blue-100' : 'text-slate-400')}>
                    {item.meta}
                  </span>
                </span>
              </>
            )}
          </NavLink>
        )
      })}
    </nav>
  )
}

export default function Layout() {
  const { t, locale, switchLang } = useLang()
  const { user, logout } = useAuth()
  const [mobileNavOpen, setMobileNavOpen] = React.useState(false)

  React.useEffect(() => {
    const html = document.getElementById('html-root')
    if (html) html.setAttribute('lang', locale)
  }, [locale])

  return (
    <div className="flex h-screen overflow-hidden bg-slate-100 text-slate-950">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded-lg focus:bg-blue-600 focus:p-3 focus:text-white"
      >
        Skip to main content
      </a>

      <aside className="hidden w-72 flex-shrink-0 border-r border-slate-200 bg-white/95 px-4 py-4 lg:flex lg:flex-col">
        <div className="flex items-center gap-3 px-2">
          <BrandMark />
          <div className="min-w-0">
            <p className="text-sm font-bold text-slate-950">RAG Finland</p>
            <p className="text-xs text-slate-500">Sovereign enterprise search</p>
          </div>
        </div>

        <div className="mt-7">
          <NavList t={t} />
        </div>

        <div className="mt-auto space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
            <LockKeyhole className="h-4 w-4 text-emerald-600" aria-hidden="true" />
            Permission-aware workspace
          </div>
          <div className="grid grid-cols-2 gap-2">
            <StatusBadge tone="emerald" className="justify-center">
              EU-ready
            </StatusBadge>
            <StatusBadge tone="blue" className="justify-center">
              Citations
            </StatusBadge>
            <StatusBadge tone="violet" className="justify-center">
              FI/SV/EN
            </StatusBadge>
            <StatusBadge tone="slate" className="justify-center">
              On-prem
            </StatusBadge>
          </div>
        </div>
      </aside>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/40 lg:hidden" role="dialog" aria-modal="true">
          <div className="h-full w-80 max-w-[85vw] bg-white p-4 shadow-xl">
            <div className="mb-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <BrandMark />
                <div>
                  <p className="text-sm font-bold text-slate-950">RAG Finland</p>
                  <p className="text-xs text-slate-500">Enterprise workspace</p>
                </div>
              </div>
              <button
                type="button"
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600"
                onClick={() => setMobileNavOpen(false)}
                aria-label="Close navigation"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <NavList t={t} onNavigate={() => setMobileNavOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 flex-shrink-0 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6" role="banner">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 lg:hidden"
              onClick={() => setMobileNavOpen(true)}
              aria-label="Open navigation"
            >
              <Menu className="h-4 w-4" aria-hidden="true" />
            </button>
            <div className="hidden min-w-0 items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600 sm:flex">
              <Database className="h-3.5 w-3.5 text-blue-600" aria-hidden="true" />
              Source-grounded answers
            </div>
            <div className="hidden min-w-0 items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-600 md:flex">
              <Globe2 className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
              Finland-first multilingual retrieval
            </div>
          </div>

          <div className="flex flex-shrink-0 items-center gap-2">
            <fieldset className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5" role="radiogroup" aria-label="Language">
              {['en', 'fi', 'sv'].map((lang) => (
                <button
                  key={lang}
                  type="button"
                  role="radio"
                  aria-checked={locale === lang}
                  className={cn(
                    'rounded-md px-2.5 py-1 text-xs font-semibold transition',
                    locale === lang ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-700',
                  )}
                  onClick={() => switchLang(lang)}
                >
                  {lang.toUpperCase()}
                </button>
              ))}
            </fieldset>
            {user && (
              <div className="ml-1 flex items-center gap-2 border-l border-slate-200 pl-3">
                <div className="hidden text-right sm:block">
                  <p className="text-xs font-semibold text-slate-800">{user.username}</p>
                  <p className="text-[11px] text-slate-400">{user.role || 'user'}</p>
                </div>
                <button
                  type="button"
                  onClick={logout}
                  className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-rose-200 hover:text-rose-600"
                  aria-label={t('login.signOut')}
                  title={t('login.signOut')}
                >
                  <LogOut className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            )}
          </div>
        </header>

        <main id="main-content" className="min-h-0 flex-1 overflow-hidden" role="main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
