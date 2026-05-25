import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, BarChart3, Database, FileText, Flag, Languages, MessageSquareText, ShieldCheck, ThumbsUp, TrendingUp, Users } from 'lucide-react'
import { getAnalytics, getAiProviders, getUsageDashboard } from '../lib/api'
import { useLang } from '../lib/LangContext'
import { cn, EmptyState, MetricCard, ProgressBar, SectionHeader, StatusBadge, Surface } from '../components/ProductUI'

const langLabel = { fi: 'Suomi', en: 'English', sv: 'Svenska' }

function BarChart({ data, labelKey, valueKey, labelFn, tone = 'blue' }) {
  if (!data || data.length === 0) return <EmptyState icon={BarChart3} title="No data yet" body="Usage charts will appear after people start asking questions." />
  const max = Math.max(...data.map((d) => d[valueKey]), 1)
  return (
    <div className="space-y-3">
      {data.map((d, i) => {
        const value = d[valueKey] || 0
        const pct = Math.max((value / max) * 100, 8)
        return (
          <div key={`${d[labelKey]}-${i}`} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3">
              <span className="truncate text-sm font-semibold text-slate-700">{labelFn ? labelFn(d[labelKey]) : d[labelKey]}</span>
              <span className="text-xs font-bold text-slate-500">{value}</span>
            </div>
            <ProgressBar value={pct} tone={tone} />
          </div>
        )
      })}
    </div>
  )
}

function InsightRow({ label, value, detail, tone = 'blue' }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-bold text-slate-800">{label}</p>
        <StatusBadge tone={tone}>{value}</StatusBadge>
      </div>
      {detail && <p className="mt-2 text-xs leading-relaxed text-slate-500">{detail}</p>}
    </div>
  )
}

export default function AnalyticsPage() {
  const { t } = useLang()
  const analytics = useQuery({ queryKey: ['analytics'], queryFn: getAnalytics, refetchInterval: 15000 })
  const usage = useQuery({ queryKey: ['usage'], queryFn: getUsageDashboard, refetchInterval: 15000 })
  const providers = useQuery({ queryKey: ['ai-providers'], queryFn: getAiProviders, refetchInterval: 30000 })
  const data = analytics.data || {}
  const answerQuality = data.answer_quality || {}
  const answerFeedback = data.answer_feedback || {}
  const usageUsers = usage.data?.users || []
  const providerData = providers.data || {}
  const topCollection = [...(data.collection_usage || [])].sort((a, b) => (b.queries || 0) - (a.queries || 0))[0]
  const topLanguage = [...(data.language_breakdown || [])].sort((a, b) => (b.count || 0) - (a.count || 0))[0]
  const activeUsers = usageUsers.filter((u) => Number(u.used_this_month || 0) > 0).length
  const totalQuota = usageUsers.reduce((sum, u) => sum + Number(u.monthly_quota || 0), 0)
  const totalUsed = usageUsers.reduce((sum, u) => sum + Number(u.used_this_month || 0), 0)
  const quotaPct = totalQuota ? Math.round((totalUsed / totalQuota) * 100) : 0

  return (
    <div className="h-full overflow-y-auto bg-slate-100">
      <div className="mx-auto max-w-screen-2xl space-y-6 px-4 py-6 sm:px-6">
        <SectionHeader eyebrow="Operating intelligence" title={t('nav.analytics')}>
          Monitor adoption, corpus coverage, language demand, and governance signals for the enterprise RAG workspace.
        </SectionHeader>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard label="Sessions" value={data.total_sessions || 0} meta="Knowledge workflows" icon={MessageSquareText} tone="blue" />
          <MetricCard label="User queries" value={data.user_queries || 0} meta="Source-grounded asks" icon={Activity} tone="emerald" />
          <MetricCard label="Messages" value={data.total_messages || 0} meta="Conversation turns" icon={TrendingUp} tone="violet" />
          <MetricCard label="Documents" value={data.total_documents || 0} meta="Indexed sources" icon={FileText} tone="amber" />
          <MetricCard label="Chunks" value={data.total_chunks || 0} meta="Retrieval units" icon={Database} tone="slate" />
        </div>

        <Surface className="p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                <h3 className="text-sm font-bold text-slate-950">Answer reliability</h3>
              </div>
              <p className="mt-1 text-sm text-slate-500">
                Tracks grounded answer coverage from chat telemetry, including no-context outcomes and citation confidence.
              </p>
            </div>
            <StatusBadge tone={answerQuality.grounded_rate >= 80 ? 'emerald' : answerQuality.grounded_rate >= 50 ? 'amber' : 'rose'}>
              {answerQuality.grounded_rate || 0}% grounded
            </StatusBadge>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-700">Grounded rate</span>
                <span className="font-bold text-slate-950">{answerQuality.grounded_rate || 0}%</span>
              </div>
              <ProgressBar value={answerQuality.grounded_rate || 0} tone="emerald" className="mt-3" />
              <p className="mt-2 text-xs text-slate-500">{answerQuality.grounded_answers || 0} grounded answers</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-700">No-context rate</span>
                <span className="font-bold text-slate-950">{answerQuality.no_context_rate || 0}%</span>
              </div>
              <ProgressBar value={answerQuality.no_context_rate || 0} tone={answerQuality.no_context_rate > 25 ? 'rose' : 'blue'} className="mt-3" />
              <p className="mt-2 text-xs text-slate-500">{answerQuality.no_context_answers || 0} unanswered from corpus</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-700">Source confidence</span>
                <span className="font-bold text-slate-950">{Math.round((answerQuality.average_source_confidence || 0) * 100)}%</span>
              </div>
              <ProgressBar value={(answerQuality.average_source_confidence || 0) * 100} tone="blue" className="mt-3" />
              <p className="mt-2 text-xs text-slate-500">Average relevance signal</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-700">Avg citations</span>
                <span className="font-bold text-slate-950">{answerQuality.average_citations || 0}</span>
              </div>
              <ProgressBar value={Math.min(100, (answerQuality.average_citations || 0) * 20)} tone="violet" className="mt-3" />
              <p className="mt-2 text-xs text-slate-500">{answerQuality.total_chat_events || 0} chat events measured</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-700">Human feedback</span>
                <span className="font-bold text-slate-950">{answerFeedback.helpful_rate || 0}%</span>
              </div>
              <ProgressBar value={answerFeedback.helpful_rate || 0} tone="emerald" className="mt-3" />
              <p className="mt-2 text-xs text-slate-500">
                {answerFeedback.total_feedback || 0} ratings, {answerFeedback.review_rate || 0}% review signal
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-700">Stale-source answers</span>
                <span className="font-bold text-slate-950">{answerQuality.stale_source_rate || 0}%</span>
              </div>
              <ProgressBar value={answerQuality.stale_source_rate || 0} tone={answerQuality.stale_source_rate ? 'rose' : 'emerald'} className="mt-3" />
              <p className="mt-2 text-xs text-slate-500">{answerQuality.stale_source_answers || 0} answers used stale or failed sources</p>
            </div>
          </div>
          <div className="mt-5 grid gap-3 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                  <ThumbsUp className="h-4 w-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-slate-900">Useful answer rate</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {answerFeedback.helpful || 0} answers marked helpful out of {answerFeedback.total_feedback || 0} recorded feedback events.
                  </p>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
                  <Flag className="h-4 w-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-slate-900">Review queue signal</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {(answerFeedback.needs_review || 0) + (answerFeedback.not_helpful || 0)} answers need review or correction.
                  </p>
                </div>
              </div>
            </div>
          </div>
          {(answerQuality.by_collection || []).length > 0 && (
            <div className="mt-5 grid gap-3 lg:grid-cols-3">
              {answerQuality.by_collection.map((row) => (
                <div key={row.collection} className="rounded-xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-bold text-slate-900">{row.collection}</p>
                    <StatusBadge tone={row.grounded_rate >= 80 ? 'emerald' : row.grounded_rate >= 50 ? 'amber' : 'rose'}>
                      {row.grounded_rate}% grounded
                    </StatusBadge>
                  </div>
                  <ProgressBar value={row.grounded_rate} tone="emerald" className="mt-3" />
                  <p className="mt-2 text-xs text-slate-500">
                    {row.total} events, {row.no_context_rate}% no-context, {Math.round((row.average_source_confidence || 0) * 100)}% confidence
                  </p>
                </div>
              ))}
            </div>
          )}
        </Surface>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="grid gap-6 lg:grid-cols-2">
            <Surface className="p-5">
              <div className="mb-5 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-slate-950">Language demand</h3>
                  <p className="mt-1 text-xs text-slate-500">Useful for Finnish, Swedish, and English retrieval tuning.</p>
                </div>
                <Languages className="h-5 w-5 text-blue-600" aria-hidden="true" />
              </div>
              <BarChart data={data.language_breakdown || []} labelKey="language" valueKey="count" labelFn={(l) => langLabel[l] || l} tone="blue" />
            </Surface>

            <Surface className="p-5">
              <div className="mb-5 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-slate-950">Collection pull</h3>
                  <p className="mt-1 text-xs text-slate-500">Shows which governed corpus is driving adoption.</p>
                </div>
                <Database className="h-5 w-5 text-emerald-600" aria-hidden="true" />
              </div>
              <BarChart data={data.collection_usage || []} labelKey="collection" valueKey="queries" tone="emerald" />
            </Surface>

            <Surface className="p-5 lg:col-span-2">
              <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-950">Recent query stream</h3>
                  <p className="mt-1 text-xs text-slate-500">Fast audit trail of what users are asking and where the answer was grounded.</p>
                </div>
                <StatusBadge tone="blue">{(data.recent_queries || []).length} recent</StatusBadge>
              </div>
              {(data.recent_queries || []).length === 0 ? (
                <EmptyState icon={MessageSquareText} title="No queries yet" body="Ask a question in the chat workspace to populate this stream." />
              ) : (
                <div className="overflow-auto">
                  <table className="w-full min-w-[680px] text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left">
                        <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">Query</th>
                        <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">Lang</th>
                        <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">Collection</th>
                        <th className="pb-3 text-xs font-bold uppercase tracking-wide text-slate-500">Time</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {data.recent_queries.map((q, i) => (
                        <tr key={`${q.created_at}-${i}`} className="transition hover:bg-slate-50">
                          <td className="max-w-md py-3 pr-4 text-slate-700">
                            <span className="line-clamp-2">{q.content}</span>
                          </td>
                          <td className="py-3 pr-4">
                            <StatusBadge tone="slate">{(q.language || 'en').toUpperCase()}</StatusBadge>
                          </td>
                          <td className="py-3 pr-4 font-medium text-slate-600">{q.collection}</td>
                          <td className="py-3 text-xs text-slate-400">{q.created_at?.split('.')[0] || ''}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Surface>
          </div>

          <aside className="space-y-4">
            <Surface className="p-5">
              <h3 className="text-sm font-bold text-slate-950">Executive signal</h3>
              <div className="mt-4 space-y-3">
                <InsightRow
                  label="Top collection"
                  value={topCollection?.collection || 'none'}
                  detail={topCollection ? `${topCollection.queries} queries routed to this corpus.` : 'No routed queries yet.'}
                  tone={topCollection ? 'emerald' : 'amber'}
                />
                <InsightRow
                  label="Top language"
                  value={topLanguage ? (langLabel[topLanguage.language] || topLanguage.language) : 'none'}
                  detail={topLanguage ? `${topLanguage.count} requests in this language.` : 'No language data yet.'}
                  tone={topLanguage ? 'blue' : 'amber'}
                />
                <InsightRow
                  label="Active users"
                  value={activeUsers}
                  detail={`${usageUsers.length} users have quota profiles configured.`}
                  tone={activeUsers ? 'violet' : 'slate'}
                />
              </div>
            </Surface>

            <Surface className="p-5">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-bold text-slate-950">Quota posture</h3>
                <Users className="h-5 w-5 text-violet-600" aria-hidden="true" />
              </div>
              <div className="mt-4">
                <div className="flex items-center justify-between text-xs font-medium text-slate-500">
                  <span>{totalUsed} used</span>
                  <span>{totalQuota || 0} quota</span>
                </div>
                <ProgressBar value={quotaPct} tone={quotaPct > 80 ? 'rose' : quotaPct > 60 ? 'amber' : 'emerald'} className="mt-2" />
              </div>
              <div className="mt-4 max-h-48 space-y-2 overflow-y-auto">
                {usageUsers.length === 0 ? (
                  <p className="text-sm text-slate-400">No quota data yet.</p>
                ) : (
                  usageUsers.map((row) => {
                    const pct = Math.round((Number(row.used_this_month || 0) / Math.max(1, Number(row.monthly_quota || 0))) * 100)
                    return (
                      <div key={row.username} className="rounded-lg bg-slate-50 p-2">
                        <div className="mb-1 flex justify-between gap-2 text-xs">
                          <span className="truncate font-semibold text-slate-700">{row.username}</span>
                          <span className="text-slate-500">{pct}%</span>
                        </div>
                        <ProgressBar value={pct} tone={pct > 80 ? 'rose' : 'blue'} />
                      </div>
                    )
                  })
                )}
              </div>
            </Surface>

            <Surface className="p-5">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                <h3 className="text-sm font-bold text-slate-950">Governance snapshot</h3>
              </div>
              <div className="mt-4 space-y-2">
                {[
                  ['Provider', providerData.llm_provider || 'not configured'],
                  ['Embeddings', providerData.embedding_provider || 'not configured'],
                  ['Sovereignty mode', providerData.data_sovereignty_mode ? 'enabled' : 'hybrid'],
                  ['Finnish model', providerData.local_llm_model_fi || 'fallback'],
                ].map(([label, value]) => (
                  <div key={label} className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2 text-sm last:border-0 last:pb-0">
                    <span className="text-slate-500">{label}</span>
                    <span className={cn('max-w-40 truncate font-semibold text-slate-800', value === 'not configured' && 'text-amber-700')}>{value}</span>
                  </div>
                ))}
              </div>
            </Surface>
          </aside>
        </div>
      </div>
    </div>
  )
}
