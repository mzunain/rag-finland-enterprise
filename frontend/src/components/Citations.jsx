import React from 'react'

export default function Citations({ citations }) {
  if (!citations || citations.length === 0) return null

  return (
    <div className="mt-4">
      <h3 className="font-medium text-slate-700 mb-2">Source Citations</h3>
      <ul className="text-sm space-y-1">
        {citations.map((c) => (
          <li key={c.chunk_id} className="flex items-center gap-2 text-slate-600">
            <span className="inline-block w-2 h-2 rounded-full bg-blue-400" />
            <span className="font-medium">{c.document}</span>
            <span>p.{c.page}</span>
            <span className="text-slate-400">relevance: {c.relevance}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
