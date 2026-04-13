import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAnalytics } from '../lib/api'
import { useLang } from '../lib/LangContext'

function StatCard({ label, value, color = 'blue' }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
    purple: 'bg-purple-50 text-purple-700',
    amber: 'bg-amber-50 text-amber-700',
    slate: 'bg-slate-50 text-slate-700',
  }
  return (
    <div className={`rounded-xl p-4 ${colors[color] || colors.blue}`}>
      <p className="text-3xl font-bold">{value}</p>
      <p className="text-xs mt-1 opacity-75">{label}</p>
    </div>
  )
}

function BarChart({ data, labelKey, valueKey, maxValue }) {
  if (!data || data.length === 0) return <p className="text-sm text-slate-400">No data yet.</p>
  const max = maxValue || Math.max(...data.map((d) => d[valueKey]))
  return (
    <div className="space-y-2">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="text-xs text-slate-600 w-24 text-right truncate">{d[labelKey]}</span>
          <div className="flex-1 bg-slate-100 rounded-full h-5 overflow-hidden">
            <div
              className="bg-blue-500 h-full rounded-full transition-all"
              style={{ width: `${max > 0 ? (d[valueKey] / max) * 100 : 0}%` }}
            />
          </div>
          <span className="text-xs text-slate-500 w-10">{d[valueKey]}</span>
        </div>
      ))}
    </div>
  )
}

export default function AnalyticsPage() {
  const { t } = useLang()

  const analytics = useQuery({
    queryKey: ['analytics'],
    queryFn: getAnalytics,
    refetchInterval: 15000,
  })

  const data = analytics.data || {}

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-slate-800">Analytics Dashboard</h2>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard label="Total Sessions" value={data.total_sessions || 0} color="blue" />
        <StatCard label="User Queries" value={data.user_queries || 0} color="green" />
        <StatCard label="Total Messages" value={data.total_messages || 0} color="purple" />
        <StatCard label="Documents" value={data.total_documents || 0} color="amber" />
        <StatCard label="Chunks" value={data.total_chunks || 0} color="slate" />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold text-slate-700 mb-4">Language Distribution</h3>
          <BarChart data={data.language_breakdown || []} labelKey="language" valueKey="count" />
          {(data.language_breakdown || []).length > 0 && (
            <div className="mt-3 flex gap-3">
              {data.language_breakdown.map((l) => (
                <span key={l.language} className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600">
                  {l.language === 'fi' ? 'Suomi' : l.language === 'en' ? 'English' : l.language}: {l.count}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold text-slate-700 mb-4">Collection Usage</h3>
          <BarChart data={data.collection_usage || []} labelKey="collection" valueKey="queries" />
        </div>
      </div>

      <div className="bg-white rounded-xl shadow p-6">
        <h3 className="font-semibold text-slate-700 mb-4">Recent Queries</h3>
        {(data.recent_queries || []).length === 0 ? (
          <p className="text-sm text-slate-400">No queries yet. Start chatting to see analytics.</p>
        ) : (
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="pb-2 pr-4">Query</th>
                  <th className="pb-2 pr-4">Language</th>
                  <th className="pb-2 pr-4">Collection</th>
                  <th className="pb-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_queries.map((q, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="py-2 pr-4 text-slate-700 max-w-md truncate">{q.content}</td>
                    <td className="py-2 pr-4">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                        {q.language === 'fi' ? 'FI' : 'EN'}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-slate-600">{q.collection}</td>
                    <td className="py-2 text-slate-400 text-xs">{q.created_at?.split('.')[0] || ''}</td>
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
