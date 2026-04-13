import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAnalytics } from '../lib/api'
import { useLang } from '../lib/LangContext'

const langLabel = { fi: 'Suomi', en: 'English', sv: 'Svenska' }

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4">
      <p className="text-2xl font-bold text-slate-800">{value}</p>
      <p className="text-xs text-slate-500 mt-1">{label}</p>
      {sub && <p className="text-[10px] text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}

function BarChart({ data, labelKey, valueKey, labelFn }) {
  if (!data || data.length === 0) return <p className="text-sm text-slate-400 py-4 text-center">No data yet.</p>
  const max = Math.max(...data.map((d) => d[valueKey]), 1)
  return (
    <div className="space-y-2">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="text-xs text-slate-600 w-24 text-right truncate font-medium">
            {labelFn ? labelFn(d[labelKey]) : d[labelKey]}
          </span>
          <div className="flex-1 bg-slate-100 rounded-full h-6 overflow-hidden">
            <div
              className="bg-blue-500 h-full rounded-full transition-all duration-500 flex items-center justify-end pr-2"
              style={{ width: `${Math.max((d[valueKey] / max) * 100, 8)}%` }}
            >
              <span className="text-[10px] font-bold text-white">{d[valueKey]}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function AnalyticsPage() {
  const { t } = useLang()
  const analytics = useQuery({ queryKey: ['analytics'], queryFn: getAnalytics, refetchInterval: 15000 })
  const data = analytics.data || {}

  return (
    <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-800">{t('nav.analytics')}</h2>
        <p className="text-sm text-slate-500 mt-0.5">Usage statistics and query analytics</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatCard label="Total Sessions" value={data.total_sessions || 0} />
        <StatCard label="User Queries" value={data.user_queries || 0} />
        <StatCard label="Total Messages" value={data.total_messages || 0} />
        <StatCard label="Documents" value={data.total_documents || 0} />
        <StatCard label="Chunks" value={data.total_chunks || 0} />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-700 mb-4 text-sm">Language Distribution</h3>
          <BarChart
            data={data.language_breakdown || []}
            labelKey="language"
            valueKey="count"
            labelFn={(l) => langLabel[l] || l}
          />
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-700 mb-4 text-sm">Collection Usage</h3>
          <BarChart data={data.collection_usage || []} labelKey="collection" valueKey="queries" />
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5">
        <h3 className="font-semibold text-slate-700 mb-4 text-sm">Recent Queries</h3>
        {(data.recent_queries || []).length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-6">No queries yet.</p>
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="pb-2 pr-4 text-xs font-medium text-slate-500 uppercase tracking-wider">Query</th>
                  <th className="pb-2 pr-4 text-xs font-medium text-slate-500 uppercase tracking-wider">Lang</th>
                  <th className="pb-2 pr-4 text-xs font-medium text-slate-500 uppercase tracking-wider">Collection</th>
                  <th className="pb-2 text-xs font-medium text-slate-500 uppercase tracking-wider">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.recent_queries.map((q, i) => (
                  <tr key={i} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 pr-4 text-slate-700 max-w-md truncate">{q.content}</td>
                    <td className="py-2.5 pr-4">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
                        {(q.language || 'en').toUpperCase()}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-slate-600">{q.collection}</td>
                    <td className="py-2.5 text-slate-400 text-xs">{q.created_at?.split('.')[0] || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
