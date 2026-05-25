import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clipboard,
  Database,
  Download,
  ExternalLink,
  Flag,
  Inbox,
  MessageSquareWarning,
  Play,
  RotateCcw,
  Search,
  ShieldCheck,
  XCircle,
} from 'lucide-react'
import { exportEvalCases, getAnswerReviews, getCollections, getEvalCases, getEvalRuns, promoteReviewToEval, runEvalCases, updateAnswerReview } from '../lib/api'
import { useLang } from '../lib/LangContext'
import { EmptyState, MetricCard, ProgressBar, SectionHeader, StatusBadge, Surface } from '../components/ProductUI'

const statusOptions = [
  { id: 'open', label: 'Open' },
  { id: 'resolved', label: 'Resolved' },
  { id: 'dismissed', label: 'Dismissed' },
  { id: 'all', label: 'All' },
]

const ratingOptions = [
  { id: 'all', label: 'All ratings' },
  { id: 'needs_review', label: 'Needs review' },
  { id: 'not_helpful', label: 'Not helpful' },
  { id: 'helpful', label: 'Helpful' },
]

function ratingTone(rating) {
  if (rating === 'helpful') return 'emerald'
  if (rating === 'not_helpful') return 'rose'
  return 'amber'
}

function statusTone(status) {
  if (status === 'resolved') return 'emerald'
  if (status === 'dismissed') return 'slate'
  return 'amber'
}

function percent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`
}

function evalCaseDraft(review) {
  return {
    id: `review-${review.id}`,
    language: review.language || 'en',
    collection: review.collection,
    question: review.question,
    expectation: 'answer',
    required_citations: (review.citations || [])
      .filter((citation) => citation.document)
      .map((citation) => ({
        document: citation.document,
        ...(citation.page ? { page: citation.page } : {}),
        ...(citation.chunk_id ? { chunk_id: citation.chunk_id } : {}),
      })),
    notes: {
      rating: review.rating,
      reason: review.reason,
      answer_excerpt: review.answer_excerpt,
      source_confidence: review.source_confidence,
    },
  }
}

export default function ReviewPage() {
  const { t } = useLang()
  const queryClient = useQueryClient()
  const [status, setStatus] = React.useState('open')
  const [rating, setRating] = React.useState('all')
  const [collection, setCollection] = React.useState('')
  const [query, setQuery] = React.useState('')
  const [notes, setNotes] = React.useState({})
  const [copiedId, setCopiedId] = React.useState(null)
  const [promotedId, setPromotedId] = React.useState(null)

  const collections = useQuery({ queryKey: ['collections'], queryFn: getCollections })
  const reviews = useQuery({
    queryKey: ['answer-reviews', status, rating, collection],
    queryFn: () => getAnswerReviews({ status, rating, collection }),
    refetchInterval: 15000,
  })
  const evalCases = useQuery({
    queryKey: ['eval-cases', collection],
    queryFn: () => getEvalCases({ collection, status: 'active' }),
    refetchInterval: 30000,
  })
  const evalRuns = useQuery({
    queryKey: ['eval-runs', collection],
    queryFn: () => getEvalRuns({ collection, status: 'all', limit: 20 }),
    refetchInterval: 30000,
  })
  const updateReview = useMutation({
    mutationFn: ({ id, payload }) => updateAnswerReview(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['answer-reviews'] })
      queryClient.invalidateQueries({ queryKey: ['analytics'] })
    },
  })
  const promoteEval = useMutation({
    mutationFn: (reviewId) => promoteReviewToEval(reviewId),
    onSuccess: (data) => {
      setPromotedId(data.eval_case?.case_id || null)
      queryClient.invalidateQueries({ queryKey: ['answer-reviews'] })
      queryClient.invalidateQueries({ queryKey: ['eval-cases'] })
      window.setTimeout(() => setPromotedId(null), 2200)
    },
  })
  const runEval = useMutation({
    mutationFn: () => runEvalCases({ collection, limit: 50 }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['eval-runs'] })
    },
  })

  const collectionNames = collections.data?.collections || []
  const reviewList = reviews.data?.reviews || []
  const summary = reviews.data?.summary || {}
  const evalCaseTotal = evalCases.data?.summary?.total || 0
  const latestRun = runEval.data?.run || evalRuns.data?.summary?.latest
  const latestReport = latestRun?.report || {}
  const failedCases = (latestReport.cases || []).filter((item) => !item.passed).slice(0, 4)
  const trend = evalRuns.data?.summary?.trend || []
  const filteredReviews = reviewList.filter((review) => {
    const needle = query.trim().toLowerCase()
    if (!needle) return true
    return [review.question, review.answer_excerpt, review.reason, review.collection]
      .join(' ')
      .toLowerCase()
      .includes(needle)
  })

  const submitUpdate = (review, nextStatus) => {
    updateReview.mutate({
      id: review.id,
      payload: {
        status: nextStatus,
        reviewer_note: notes[review.id] ?? review.reviewer_note ?? '',
      },
    })
  }

  const copyEvalCase = async (review) => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(evalCaseDraft(review), null, 2))
      setCopiedId(review.id)
      window.setTimeout(() => setCopiedId(null), 1800)
    } catch {
      setCopiedId(null)
    }
  }

  const downloadEvalExport = async () => {
    const payload = await exportEvalCases({ collection })
    const blobUrl = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = blobUrl
    anchor.download = `retrieval-eval-cases-${collection || 'all'}.json`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(blobUrl)
  }

  return (
    <div className="h-full overflow-y-auto bg-slate-100">
      <div className="mx-auto max-w-screen-2xl space-y-6 px-4 py-6 sm:px-6">
        <SectionHeader
          eyebrow="Quality operations"
          title={t('nav.reviews')}
          action={
            <select
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
              value={collection}
              onChange={(event) => setCollection(event.target.value)}
            >
              <option value="">All collections</option>
              {collectionNames.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          }
        >
          Triage flagged answers, resolve review work, and promote weak answers into retrieval evaluation cases.
        </SectionHeader>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <MetricCard label="Open" value={summary.open || 0} meta="Needs action" icon={MessageSquareWarning} tone="amber" />
          <MetricCard label="Resolved" value={summary.resolved || 0} meta={`${summary.resolution_rate || 0}% closure`} icon={CheckCircle2} tone="emerald" />
          <MetricCard label="Dismissed" value={summary.dismissed || 0} meta="Not actionable" icon={XCircle} tone="slate" />
          <MetricCard label="Review signal" value={summary.needs_review || 0} meta="Flagged by users" icon={Flag} tone="rose" />
          <MetricCard label="Matching" value={reviews.data?.pagination?.total || 0} meta="Current filters" icon={Inbox} tone="blue" />
          <MetricCard label="Eval cases" value={evalCaseTotal} meta="Promoted golden cases" icon={Database} tone="violet" />
        </div>

        <Surface className="p-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_13rem_13rem_auto]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
              <input
                type="search"
                className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                placeholder="Search review queue"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <select
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              {statusOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
            <select
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
              value={rating}
              onChange={(event) => setRating(event.target.value)}
            >
              {ratingOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 transition hover:border-blue-200 hover:text-blue-700"
              onClick={downloadEvalExport}
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              Export evals
            </button>
          </div>
        </Surface>

        <Surface className="overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-slate-200 bg-white p-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-bold text-slate-950">Live retrieval eval</h3>
                {latestRun ? (
                  <StatusBadge tone={latestRun.passed ? 'emerald' : 'rose'}>
                    {latestRun.passed ? 'passing' : 'failing'}
                  </StatusBadge>
                ) : (
                  <StatusBadge tone="slate">not run</StatusBadge>
                )}
              </div>
              <p className="mt-1 text-sm text-slate-500">
                {latestRun ? `Latest run ${latestRun.run_id} tested ${latestRun.total_cases || 0} promoted cases.` : 'Run promoted cases against current retrieval.'}
              </p>
            </div>
            <button
              type="button"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-950 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={runEval.isPending || evalCaseTotal === 0}
              onClick={() => runEval.mutate()}
            >
              <Play className="h-4 w-4" aria-hidden="true" />
              {runEval.isPending ? 'Running eval' : 'Run eval'}
            </button>
          </div>
          <div className="grid gap-0 divide-y divide-slate-200 lg:grid-cols-[minmax(0,1fr)_23rem] lg:divide-x lg:divide-y-0">
            <div className="p-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-semibold text-slate-700">Pass rate</span>
                    <span className="font-bold text-slate-950">{percent(latestRun?.case_pass_rate)}</span>
                  </div>
                  <ProgressBar value={(latestRun?.case_pass_rate || 0) * 100} tone={latestRun?.passed ? 'emerald' : 'rose'} className="mt-3" />
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-semibold text-slate-700">Citation recall</span>
                    <span className="font-bold text-slate-950">{percent(latestRun?.citation_recall)}</span>
                  </div>
                  <ProgressBar value={(latestRun?.citation_recall || 0) * 100} tone="blue" className="mt-3" />
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-semibold text-slate-700">Cases passed</span>
                    <span className="font-bold text-slate-950">{latestRun ? `${latestRun.passed_cases}/${latestRun.total_cases}` : '0/0'}</span>
                  </div>
                  <ProgressBar value={latestRun?.total_cases ? (latestRun.passed_cases / latestRun.total_cases) * 100 : 0} tone="violet" className="mt-3" />
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-semibold text-slate-700">Failures</span>
                    <span className="font-bold text-slate-950">{(latestReport.failures || []).length}</span>
                  </div>
                  <ProgressBar value={Math.min(100, ((latestReport.failures || []).length) * 25)} tone={(latestReport.failures || []).length ? 'rose' : 'emerald'} className="mt-3" />
                </div>
              </div>

              {runEval.isError && (
                <div className="mt-3 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
                  <span>{runEval.error?.message || 'Evaluation run failed.'}</span>
                </div>
              )}

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-blue-600" aria-hidden="true" />
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Run trend</p>
                  </div>
                  {trend.length === 0 ? (
                    <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">No run history yet.</p>
                  ) : (
                    <div className="space-y-2">
                      {trend.map((row) => (
                        <div key={row.run_id} className="rounded-lg border border-slate-200 bg-white p-3">
                          <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                            <span className="truncate font-semibold text-slate-700">{row.run_id}</span>
                            <span className={row.passed ? 'font-bold text-emerald-700' : 'font-bold text-rose-700'}>{percent(row.case_pass_rate)}</span>
                          </div>
                          <ProgressBar value={(row.case_pass_rate || 0) * 100} tone={row.passed ? 'emerald' : 'rose'} />
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <Activity className="h-4 w-4 text-rose-600" aria-hidden="true" />
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Failed cases</p>
                  </div>
                  {failedCases.length === 0 ? (
                    <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                      {latestRun ? 'No failed cases in the latest run.' : 'Run evals to populate case-level results.'}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {failedCases.map((item) => (
                        <div key={item.case_id} className="rounded-lg border border-rose-100 bg-rose-50 p-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="truncate text-sm font-bold text-rose-950">{item.case_id}</p>
                            <StatusBadge tone="rose">{Math.round((item.citation_recall || 0) * 100)}% recall</StatusBadge>
                          </div>
                          <p className="mt-1 text-xs text-rose-800">
                            {item.collection} - {item.matched_required_citations || 0}/{item.required_citations || 0} required citations matched
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="bg-slate-50 p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Recent runs</p>
              <div className="mt-3 max-h-72 space-y-2 overflow-y-auto">
                {(evalRuns.data?.runs || []).length === 0 ? (
                  <p className="text-sm text-slate-500">No saved runs.</p>
                ) : (
                  evalRuns.data.runs.map((run) => (
                    <div key={run.run_id} className="rounded-lg border border-slate-200 bg-white p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-sm font-bold text-slate-900">{run.run_id}</p>
                        <StatusBadge tone={run.passed ? 'emerald' : 'rose'}>{percent(run.case_pass_rate)}</StatusBadge>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {run.collection} - {run.passed_cases}/{run.total_cases} cases - {run.started_at?.split('.')[0] || ''}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </Surface>

        {filteredReviews.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title={reviews.isLoading ? 'Loading review queue' : 'No reviews match'}
            body={reviews.isLoading ? 'Review records are loading.' : 'Change filters or wait for answer feedback to arrive.'}
          />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {filteredReviews.map((review) => {
              const confidence = Math.round((Number(review.source_confidence) || 0) * 100)
              const note = notes[review.id] ?? review.reviewer_note ?? ''
              return (
                <Surface key={review.id} className="overflow-hidden">
                  <div className="border-b border-slate-200 bg-white p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge tone={statusTone(review.status)}>{review.status}</StatusBadge>
                      <StatusBadge tone={ratingTone(review.rating)}>{review.rating.replace('_', ' ')}</StatusBadge>
                      {review.promoted_eval_case_id && <StatusBadge tone="violet">eval {review.promoted_eval_case_id}</StatusBadge>}
                      <StatusBadge tone="slate">{review.collection}</StatusBadge>
                      <span className="text-xs font-medium text-slate-400">{review.created_at?.split('.')[0] || ''}</span>
                    </div>
                    <h3 className="mt-3 line-clamp-2 text-base font-bold text-slate-950">{review.question || 'No question captured'}</h3>
                    <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-slate-600">{review.answer_excerpt || 'No answer excerpt captured.'}</p>
                  </div>

                  <div className="space-y-4 p-4">
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs font-semibold text-slate-500">Confidence</p>
                        <p className="mt-1 text-lg font-bold text-slate-950">{confidence}%</p>
                        <ProgressBar value={confidence} tone={confidence >= 55 ? 'emerald' : confidence >= 35 ? 'amber' : 'rose'} className="mt-2" />
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs font-semibold text-slate-500">Citations</p>
                        <p className="mt-1 text-lg font-bold text-slate-950">{review.citation_count || 0}</p>
                        <p className="mt-2 text-xs text-slate-500">{review.confidence_label || 'unlabeled'}</p>
                      </div>
                      <div className="rounded-xl bg-slate-50 p-3">
                        <p className="text-xs font-semibold text-slate-500">Submitted by</p>
                        <p className="mt-1 truncate text-sm font-bold text-slate-950">{review.created_by || 'unknown'}</p>
                        <p className="mt-2 text-xs text-slate-500">{(review.language || 'en').toUpperCase()}</p>
                      </div>
                    </div>

                    {review.reason && (
                      <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                        <span className="font-bold">Feedback:</span> {review.reason}
                      </div>
                    )}

                    <label className="block">
                      <span className="mb-1 block text-xs font-bold uppercase tracking-wide text-slate-500">Reviewer note</span>
                      <textarea
                        className="min-h-20 w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                        value={note}
                        onChange={(event) => setNotes((prev) => ({ ...prev, [review.id]: event.target.value }))}
                      />
                    </label>

                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
                      <button
                        type="button"
                        className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 transition hover:border-blue-200 hover:text-blue-700"
                        onClick={() => copyEvalCase(review)}
                      >
                        <Clipboard className="h-4 w-4" aria-hidden="true" />
                        {copiedId === review.id ? 'Copied case' : 'Copy eval case'}
                      </button>
                      <button
                        type="button"
                        className="inline-flex items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm font-semibold text-violet-700 transition hover:border-violet-300 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={promoteEval.isPending}
                        onClick={() => promoteEval.mutate(review.id)}
                      >
                        <Database className="h-4 w-4" aria-hidden="true" />
                        {promotedId === `review-${review.id}` || review.promoted_eval_case_id ? 'Promoted' : 'Promote to eval'}
                      </button>

                      <div className="flex flex-wrap gap-2">
                        {review.status !== 'open' && (
                          <button
                            type="button"
                            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 transition hover:border-blue-200 hover:text-blue-700"
                            disabled={updateReview.isPending}
                            onClick={() => submitUpdate(review, 'open')}
                          >
                            <RotateCcw className="h-4 w-4" aria-hidden="true" />
                            Reopen
                          </button>
                        )}
                        {review.status !== 'dismissed' && (
                          <button
                            type="button"
                            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 transition hover:border-slate-300"
                            disabled={updateReview.isPending}
                            onClick={() => submitUpdate(review, 'dismissed')}
                          >
                            <XCircle className="h-4 w-4" aria-hidden="true" />
                            Dismiss
                          </button>
                        )}
                        {review.status !== 'resolved' && (
                          <button
                            type="button"
                            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
                            disabled={updateReview.isPending}
                            onClick={() => submitUpdate(review, 'resolved')}
                          >
                            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                            Resolve
                          </button>
                        )}
                      </div>
                    </div>

                    {review.session_id && (
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                        <span className="truncate">Session {review.session_id}</span>
                      </div>
                    )}
                  </div>
                </Surface>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
