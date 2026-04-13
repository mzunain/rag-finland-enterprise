import React from 'react'
import { useLang } from '../lib/LangContext'

export default function Citations({ citations }) {
  const { t } = useLang()
  const [expanded, setExpanded] = React.useState(false)

  if (!citations || citations.length === 0) return null

  const shown = expanded ? citations : citations.slice(0, 2)

  return (
    <div className="mt-2 pt-2 border-t border-slate-100">
      <button
        className="text-[10px] font-medium text-slate-400 hover:text-slate-600 transition-colors mb-1"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        {t('citations.title')} ({citations.length}) {expanded ? '−' : '+'}
      </button>
      <ul className="space-y-1" role="list" aria-label={t('citations.title')}>
        {shown.map((c) => {
          const pct = Math.round((c.relevance || 0) * 100)
          return (
            <li key={c.chunk_id} className="flex items-center gap-2 text-[11px] text-slate-500">
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${pct >= 40 ? 'bg-green-500' : pct >= 25 ? 'bg-yellow-500' : 'bg-slate-300'}`} />
              <span className="truncate flex-1 min-w-0" title={c.document}>{c.document}</span>
              <span className="flex-shrink-0 text-slate-400">p.{c.page}</span>
              <span className="flex-shrink-0 font-mono text-[10px]">{pct}%</span>
            </li>
          )
        })}
      </ul>
      {!expanded && citations.length > 2 && (
        <button className="text-[10px] text-blue-600 hover:text-blue-700 mt-1" onClick={() => setExpanded(true)}>
          +{citations.length - 2} more
        </button>
      )}
    </div>
  )
}
