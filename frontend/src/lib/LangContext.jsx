import React from 'react'
import { createI18n } from './i18n'

const LangContext = React.createContext(null)

export function LangProvider({ children }) {
  const [locale, setLocale] = React.useState(() => {
    return localStorage.getItem('rag-lang') || 'en'
  })

  const i18n = React.useMemo(() => createI18n(locale), [locale])

  const switchLang = (newLocale) => {
    setLocale(newLocale)
    localStorage.setItem('rag-lang', newLocale)
  }

  return (
    <LangContext.Provider value={{ ...i18n, locale, switchLang }}>
      {children}
    </LangContext.Provider>
  )
}

export function useLang() {
  const ctx = React.useContext(LangContext)
  if (!ctx) throw new Error('useLang must be used within LangProvider')
  return ctx
}
