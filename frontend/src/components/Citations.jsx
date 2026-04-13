import React from 'react'
import { useLang } from '../lib/LangContext'

export default function Citations({ citations }) {
  const { t } = useLang()

  if (!citations || citations.length === 0) return null

  return (
    <div className="mt-3">
      <h4 className="text-xs font-medium text-slate-500 mb-1">{t('citations.title')}</h4>
      <ul className="text-xs space-y-0.5" role="list" aria-label={t('citations.title')}>
        {citations.map((c) => (
          <li key={c.chunk_id} className="flex items-center gap-2 text-slate-500">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-400" />
            <span>{c.document}</span>
            <span>p.{c.page}</span>
            <span className="text-slate-400">{t('citations.relevance')}: {c.relevance}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
