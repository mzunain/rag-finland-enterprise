import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  Gauge,
  Play,
  PlugZap,
  RefreshCw,
  Rocket,
  Save,
  ServerCog,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import {
  getEvalSchedule,
  getLaunchConnectors,
  getLaunchDeployChecklist,
  getLaunchReadiness,
  runDueEvalSchedule,
  seedDemoWorkspace,
  updateEvalSchedule,
} from '../lib/api'
import { cn, MetricCard, ProgressBar, SectionHeader, StatusBadge, Surface } from '../components/ProductUI'

function scoreTone(score) {
  if (score >= 80) return 'emerald'
  if (score >= 55) return 'amber'
  return 'rose'
}

function statusTone(status) {
  if (status === 'ok' || status === 'available' || status === 'passed') return 'emerald'
  if (status === 'error' || status === 'failed') return 'rose'
  if (status === 'planned') return 'violet'
  return 'amber'
}

function formatDate(value) {
  if (!value) return 'Not scheduled'
  return String(value).split('.')[0]
}

function CheckRow({ item, compact = false }) {
  const Icon = item.status === 'ok' ? CheckCircle2 : AlertTriangle
  return (
    <div className={cn('flex items-start gap-3 rounded-xl border p-3', item.status === 'ok' ? 'border-emerald-100 bg-emerald-50/60' : 'border-amber-100 bg-amber-50/70')}>
      <div className={cn('mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-white', item.status === 'ok' ? 'text-emerald-700' : 'text-amber-700')}>
        <Icon className="h-4 w-4" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-bold text-slate-900">{item.title}</p>
          <StatusBadge tone={statusTone(item.status)}>{item.status}</StatusBadge>
        </div>
        <p className={cn('mt-1 text-sm leading-relaxed text-slate-600', compact && 'line-clamp-2')}>{item.detail}</p>
        {!compact && <p className="mt-2 text-xs font-semibold text-slate-500">{item.action}</p>}
      </div>
    </div>
  )
}

function ConnectorCard({ item }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-slate-950">{item.label}</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">{item.coverage}</p>
        </div>
        <StatusBadge tone={statusTone(item.status)}>{item.status}</StatusBadge>
      </div>
      <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">{item.setup}</p>
    </div>
  )
}

const competitiveMoves = [
  {
    competitor: 'Glean style enterprise search',
    expectation: 'Connectors, source-aware answers, and permission boundaries.',
    response: 'Connector catalog, source ACL capture, freshness tracking, and cited retrieval.',
    tone: 'emerald',
  },
  {
    competitor: 'Microsoft Copilot style governance',
    expectation: 'Security posture, admin controls, and enterprise readiness.',
    response: 'Launch score, deployment gate, auth checks, and EU/on-prem runbooks.',
    tone: 'blue',
  },
  {
    competitor: 'Chatbot builder tools',
    expectation: 'Fast demo setup, answer feedback, and simple operational visibility.',
    response: 'One-click demo seed, Review Center, eval promotion, and scheduled regression checks.',
    tone: 'violet',
  },
]

export default function LaunchPage() {
  const queryClient = useQueryClient()
  const readiness = useQuery({ queryKey: ['launch-readiness'], queryFn: getLaunchReadiness, refetchInterval: 20000 })
  const connectors = useQuery({ queryKey: ['launch-connectors'], queryFn: getLaunchConnectors, staleTime: 60000 })
  const deploy = useQuery({ queryKey: ['launch-deploy-checklist'], queryFn: getLaunchDeployChecklist, refetchInterval: 30000 })
  const scheduleQuery = useQuery({ queryKey: ['launch-eval-schedule'], queryFn: getEvalSchedule, refetchInterval: 30000 })

  const [scheduleForm, setScheduleForm] = React.useState({
    enabled: false,
    interval_hours: 24,
    collection: '',
    alert_email: '',
  })

  React.useEffect(() => {
    const schedule = scheduleQuery.data?.schedule
    if (!schedule) return
    setScheduleForm({
      enabled: Boolean(schedule.enabled),
      interval_hours: Number(schedule.interval_hours || 24),
      collection: schedule.collection || '',
      alert_email: schedule.alert_email || '',
    })
  }, [scheduleQuery.data?.schedule])

  const invalidateLaunch = () => {
    queryClient.invalidateQueries({ queryKey: ['launch-readiness'] })
    queryClient.invalidateQueries({ queryKey: ['launch-eval-schedule'] })
    queryClient.invalidateQueries({ queryKey: ['launch-deploy-checklist'] })
    queryClient.invalidateQueries({ queryKey: ['eval-cases'] })
    queryClient.invalidateQueries({ queryKey: ['eval-runs'] })
  }

  const seedDemo = useMutation({
    mutationFn: seedDemoWorkspace,
    onSuccess: invalidateLaunch,
  })
  const saveSchedule = useMutation({
    mutationFn: () =>
      updateEvalSchedule({
        enabled: scheduleForm.enabled,
        interval_hours: Number(scheduleForm.interval_hours || 24),
        collection: scheduleForm.collection,
        alert_email: scheduleForm.alert_email,
      }),
    onSuccess: invalidateLaunch,
  })
  const runDue = useMutation({
    mutationFn: () => runDueEvalSchedule(true),
    onSuccess: invalidateLaunch,
  })

  const readinessData = readiness.data || {}
  const deployData = deploy.data || {}
  const schedule = scheduleQuery.data?.schedule || {}
  const checks = readinessData.checks || []
  const metrics = readinessData.metrics || {}
  const connectorRows = connectors.data?.connectors || []
  const availableConnectors = connectors.data?.available || 0
  const plannedConnectors = connectors.data?.planned || 0
  const readinessScore = Number(readinessData.score || 0)
  const deployScore = Number(deployData.score || 0)
  const scheduleLabel = schedule.enabled ? schedule.last_status || 'scheduled' : 'paused'

  return (
    <div className="h-full overflow-y-auto bg-slate-100">
      <div className="mx-auto max-w-screen-2xl space-y-6 px-4 py-6 sm:px-6">
        <SectionHeader
          eyebrow="Launch Center"
          title="Production launch control"
          action={
            <button
              type="button"
              onClick={() => readiness.refetch()}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-700 shadow-sm transition hover:border-blue-200 hover:text-blue-700"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Refresh
            </button>
          }
        >
          Turn a strong demo into a controlled enterprise product: seed data, verify readiness, schedule evals, and track competitor-critical launch gaps.
        </SectionHeader>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard label="Readiness" value={`${readinessScore}%`} meta={`${checks.filter((item) => item.status === 'ok').length}/${checks.length || 0} checks green`} icon={Gauge} tone={scoreTone(readinessScore)} />
          <MetricCard label="Demo corpus" value={metrics.active_eval_cases || 0} meta={`${metrics.chunks || 0} chunks indexed`} icon={Database} tone="blue" />
          <MetricCard label="Connectors" value={`${availableConnectors}/${availableConnectors + plannedConnectors || 0}`} meta="Available now" icon={PlugZap} tone="emerald" />
          <MetricCard label="Eval schedule" value={schedule.enabled ? 'On' : 'Off'} meta={formatDate(schedule.next_run_at)} icon={Clock3} tone={schedule.enabled ? 'violet' : 'slate'} />
          <MetricCard label="Deploy gate" value={`${deployScore}%`} meta="Production checklist" icon={ServerCog} tone={scoreTone(deployScore)} />
        </div>

        <Surface className="overflow-hidden border-slate-900 bg-slate-950 text-white">
          <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_27rem]">
            <div className="p-5 sm:p-6">
              <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                <div className="max-w-3xl">
                  <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs font-bold text-blue-100">
                    <Rocket className="h-3.5 w-3.5" aria-hidden="true" />
                    Operator cockpit
                  </div>
                  <h3 className="mt-4 text-2xl font-bold tracking-normal text-white sm:text-3xl">Standout readiness for demos, pilots, and production reviews.</h3>
                  <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">
                    The product now exposes the same control surfaces enterprise buyers expect: governed connectors, eval gates, deployment checks, and a repeatable demo seed.
                  </p>
                </div>
                <div className="w-full rounded-xl border border-white/10 bg-white/10 p-4 lg:w-64">
                  <div className="flex items-end justify-between gap-3">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wide text-slate-300">Launch score</p>
                      <p className="mt-1 text-4xl font-bold">{readinessScore}%</p>
                    </div>
                    <StatusBadge tone={scoreTone(readinessScore)}>{readinessScore >= 80 ? 'ready' : 'needs work'}</StatusBadge>
                  </div>
                  <ProgressBar value={readinessScore} tone={scoreTone(readinessScore)} className="mt-4 bg-white/10" />
                </div>
              </div>

              <div className="mt-6 grid gap-3 md:grid-cols-3">
                {competitiveMoves.map((move) => (
                  <div key={move.competitor} className="rounded-xl border border-white/10 bg-white/[0.07] p-4">
                    <StatusBadge tone={move.tone}>{move.competitor}</StatusBadge>
                    <p className="mt-3 text-sm font-semibold text-white">{move.expectation}</p>
                    <p className="mt-2 text-xs leading-relaxed text-slate-300">{move.response}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-white/10 bg-white/[0.06] p-5 xl:border-l xl:border-t-0">
              <p className="text-xs font-bold uppercase tracking-wide text-slate-300">Fast path</p>
              <div className="mt-4 space-y-3">
                {[
                  ['Seed', 'Load demo docs, eval cases, and review signals.', Database],
                  ['Verify', 'Resolve warnings before a customer walk-through.', ShieldCheck],
                  ['Schedule', 'Keep retrieval quality from drifting after changes.', Clock3],
                  ['Ship', 'Use the deploy gate as the go/no-go checklist.', Rocket],
                ].map(([title, body, Icon]) => (
                  <div key={title} className="flex items-start gap-3 rounded-xl bg-white/10 p-3">
                    <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-white text-slate-950">
                      <Icon className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white">{title}</p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-300">{body}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Surface>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(24rem,0.85fr)]">
          <div className="space-y-6">
            <Surface className="p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                    <h3 className="text-sm font-bold text-slate-950">Readiness checks</h3>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">Actionable launch blockers across auth, provider setup, demo data, eval coverage, and freshness.</p>
                </div>
                <button
                  type="button"
                  onClick={() => seedDemo.mutate()}
                  disabled={seedDemo.isPending}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                  {seedDemo.isPending ? 'Seeding demo' : 'Seed demo workspace'}
                </button>
              </div>

              {seedDemo.data && (
                <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm font-semibold text-emerald-800">
                  Demo seed completed. New records: {seedDemo.data.total_created || 0}.
                </div>
              )}
              {seedDemo.isError && (
                <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                  {seedDemo.error?.message || 'Demo seed failed.'}
                </div>
              )}

              <div className="mt-5 grid gap-3 lg:grid-cols-2">
                {(checks.length ? checks : [{ status: 'warning', title: 'Loading readiness', detail: 'Waiting for launch checks.', action: 'Refresh if this persists.' }]).map((item) => (
                  <CheckRow key={`${item.title}-${item.status}`} item={item} />
                ))}
              </div>
            </Surface>

            <Surface className="p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <PlugZap className="h-5 w-5 text-violet-600" aria-hidden="true" />
                    <h3 className="text-sm font-bold text-slate-950">Connector coverage</h3>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">Enterprise buyers compare connector breadth first, then permission and freshness controls.</p>
                </div>
                <div className="flex gap-2">
                  <StatusBadge tone="emerald">{availableConnectors} available</StatusBadge>
                  <StatusBadge tone="violet">{plannedConnectors} planned</StatusBadge>
                </div>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {connectorRows.map((item) => (
                  <ConnectorCard key={item.id} item={item} />
                ))}
              </div>
            </Surface>
          </div>

          <div className="space-y-6">
            <Surface className="p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <Clock3 className="h-5 w-5 text-blue-600" aria-hidden="true" />
                    <h3 className="text-sm font-bold text-slate-950">Eval automation</h3>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">Keep promoted review cases running as a regression gate.</p>
                </div>
                <div className="flex flex-wrap gap-2 sm:justify-end">
                  <StatusBadge tone={statusTone(scheduleLabel)}>{scheduleLabel}</StatusBadge>
                  <StatusBadge tone="slate">every {schedule.scheduler_poll_seconds || 60}s</StatusBadge>
                </div>
              </div>

              <div className="mt-5 space-y-4">
                <label className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <span className="min-w-0">
                    <span className="block text-sm font-bold text-slate-900">Scheduled evals</span>
                    <span className="block text-xs text-slate-500">{formatDate(schedule.next_run_at)}</span>
                  </span>
                  <input
                    type="checkbox"
                    className="h-5 w-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    checked={scheduleForm.enabled}
                    onChange={(event) => setScheduleForm((current) => ({ ...current, enabled: event.target.checked }))}
                  />
                </label>

                <label className="block">
                  <span className="text-xs font-bold uppercase tracking-wide text-slate-500">Interval hours</span>
                  <input
                    type="number"
                    min="1"
                    max="720"
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                    value={scheduleForm.interval_hours}
                    onChange={(event) => setScheduleForm((current) => ({ ...current, interval_hours: Number(event.target.value || 1) }))}
                  />
                </label>

                <label className="block">
                  <span className="text-xs font-bold uppercase tracking-wide text-slate-500">Collection filter</span>
                  <input
                    type="text"
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="All collections"
                    value={scheduleForm.collection}
                    onChange={(event) => setScheduleForm((current) => ({ ...current, collection: event.target.value }))}
                  />
                </label>

                <label className="block">
                  <span className="text-xs font-bold uppercase tracking-wide text-slate-500">Alert email</span>
                  <input
                    type="email"
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="ops@example.com"
                    value={scheduleForm.alert_email}
                    onChange={(event) => setScheduleForm((current) => ({ ...current, alert_email: event.target.value }))}
                  />
                </label>

                <div className="grid gap-2 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => saveSchedule.mutate()}
                    disabled={saveSchedule.isPending}
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Save className="h-4 w-4" aria-hidden="true" />
                    {saveSchedule.isPending ? 'Saving' : 'Save schedule'}
                  </button>
                  <button
                    type="button"
                    onClick={() => runDue.mutate()}
                    disabled={runDue.isPending}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm transition hover:border-blue-200 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Play className="h-4 w-4" aria-hidden="true" />
                    {runDue.isPending ? 'Running' : 'Run now'}
                  </button>
                </div>

                {(saveSchedule.data || runDue.data?.run) && (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm font-semibold text-emerald-800">
                    {runDue.data?.run ? `Eval run ${runDue.data.run.run_id} completed.` : 'Schedule updated.'}
                  </div>
                )}
                {runDue.data?.error && (
                  <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                    Eval run failed: {runDue.data.error}
                  </div>
                )}
                {schedule.last_error && (
                  <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                    Last scheduler error: {schedule.last_error}
                  </div>
                )}
                {(saveSchedule.isError || runDue.isError) && (
                  <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                    {saveSchedule.error?.message || runDue.error?.message || 'Eval automation failed.'}
                  </div>
                )}
              </div>
            </Surface>

            <Surface className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <ServerCog className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                    <h3 className="text-sm font-bold text-slate-950">Deploy checklist</h3>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">Go/no-go signals for demos, pilots, and production deployments.</p>
                </div>
                <StatusBadge tone={scoreTone(deployScore)}>{deployScore}%</StatusBadge>
              </div>
              <ProgressBar value={deployScore} tone={scoreTone(deployScore)} className="mt-4" />
              <div className="mt-5 space-y-3">
                {(deployData.items || []).map((item) => (
                  <CheckRow key={`${item.title}-${item.status}`} item={item} compact />
                ))}
              </div>
            </Surface>
          </div>
        </div>
      </div>
    </div>
  )
}
