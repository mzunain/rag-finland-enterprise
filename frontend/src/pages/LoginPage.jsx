import React from 'react'
import { Database, Globe2, LockKeyhole, ShieldCheck } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'
import { useLang } from '../lib/LangContext'
import { cn, StatusBadge, Surface } from '../components/ProductUI'

export default function LoginPage() {
  const { login, error } = useAuth()
  const { t, locale, switchLang } = useLang()
  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [localError, setLocalError] = React.useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    setSubmitting(true)
    setLocalError('')
    try {
      await login(username.trim(), password)
    } catch (err) {
      setLocalError(err.message || 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  const displayError = localError || error

  return (
    <div className="min-h-screen bg-slate-100 px-4 py-8">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl items-center gap-8 lg:grid-cols-[minmax(0,1fr)_26rem]">
        <section className="hidden lg:block">
          <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-sm">
            <ShieldCheck className="h-7 w-7" aria-hidden="true" />
          </div>
          <p className="text-xs font-bold uppercase tracking-wide text-blue-700">RAG Finland Enterprise</p>
          <h1 className="mt-3 max-w-2xl text-4xl font-bold leading-tight text-slate-950">
            Sovereign knowledge search for Finnish and EU teams.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-7 text-slate-600">
            Source-grounded answers, role-scoped collections, citations, multilingual retrieval, and deployment paths for regulated workspaces.
          </p>
          <div className="mt-8 grid max-w-2xl gap-3 sm:grid-cols-3">
            {[
              [Database, 'Cited sources', 'Every supported answer keeps evidence visible.'],
              [LockKeyhole, 'RBAC ready', 'Collection permissions and quotas are enforced by the API.'],
              [Globe2, 'FI/SV/EN', 'Built for Finnish-first enterprise knowledge.'],
            ].map(([Icon, title, detail]) => (
              <Surface key={title} className="p-4">
                <Icon className="h-5 w-5 text-blue-600" aria-hidden="true" />
                <p className="mt-3 text-sm font-bold text-slate-900">{title}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p>
              </Surface>
            ))}
          </div>
        </section>

        <div className="w-full">
          <div className="mb-5 text-center lg:hidden">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-950 text-white">
              <ShieldCheck className="h-6 w-6" aria-hidden="true" />
            </div>
            <h1 className="text-xl font-bold text-slate-950">RAG Finland Enterprise</h1>
            <p className="mt-1 text-sm text-slate-500">Sovereign enterprise search</p>
          </div>

          <Surface className="p-6 shadow-md">
            <div className="mb-6">
              <StatusBadge tone="emerald">Secure workspace</StatusBadge>
              <h2 className="mt-4 text-2xl font-bold text-slate-950">{t('login.subtitle')}</h2>
              <p className="mt-1 text-sm text-slate-500">Use your local admin, JWT, or configured enterprise identity flow.</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {displayError && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">
                  {displayError}
                </div>
              )}

              <div>
                <label htmlFor="username" className="mb-1 block text-sm font-semibold text-slate-700">
                  {t('login.username')}
                </label>
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                  placeholder={t('login.usernamePlaceholder')}
                  disabled={submitting}
                />
              </div>

              <div>
                <label htmlFor="password" className="mb-1 block text-sm font-semibold text-slate-700">
                  {t('login.password')}
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                  placeholder={t('login.passwordPlaceholder')}
                  disabled={submitting}
                />
              </div>

              <button
                type="submit"
                disabled={submitting || !username.trim() || !password}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <LockKeyhole className="h-4 w-4" aria-hidden="true" />
                {submitting ? t('login.signingIn') : t('login.signIn')}
              </button>
            </form>

            <div className="mt-5 flex justify-center border-t border-slate-200 pt-4">
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
            </div>
          </Surface>
        </div>
      </div>
    </div>
  )
}
