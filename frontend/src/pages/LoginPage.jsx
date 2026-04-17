import React from 'react'
import { useAuth } from '../lib/AuthContext'
import { useLang } from '../lib/LangContext'

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
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-lg">RF</span>
          </div>
          <h1 className="text-xl font-bold text-slate-800">RAG Finland Enterprise</h1>
          <p className="text-sm text-slate-500 mt-1">{t('login.subtitle')}</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white border border-slate-200 rounded-xl p-6 space-y-4 shadow-sm"
        >
          {displayError && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
              {displayError}
            </div>
          )}

          <div>
            <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-1">
              {t('login.username')}
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
              placeholder={t('login.usernamePlaceholder')}
              disabled={submitting}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">
              {t('login.password')}
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
              placeholder={t('login.passwordPlaceholder')}
              disabled={submitting}
            />
          </div>

          <button
            type="submit"
            disabled={submitting || !username.trim() || !password}
            className="w-full py-2 px-4 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? t('login.signingIn') : t('login.signIn')}
          </button>
        </form>

        <div className="flex justify-center mt-4">
          <fieldset className="flex bg-white border border-slate-200 rounded-lg p-0.5" role="radiogroup" aria-label="Language">
            {['en', 'fi', 'sv'].map((lang) => (
              <button
                key={lang}
                type="button"
                role="radio"
                aria-checked={locale === lang}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                  locale === lang ? 'bg-slate-100 text-slate-800' : 'text-slate-500 hover:text-slate-700'
                }`}
                onClick={() => switchLang(lang)}
              >
                {lang.toUpperCase()}
              </button>
            ))}
          </fieldset>
        </div>
      </div>
    </div>
  )
}
