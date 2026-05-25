import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity,
  CheckCircle2,
  Clock3,
  Clipboard,
  CloudCog,
  Database,
  FilePlus2,
  KeyRound,
  Link2,
  LockKeyhole,
  PlugZap,
  ServerCog,
  ShieldCheck,
  RefreshCw,
  Trash2,
  UploadCloud,
  UserPlus,
  Users,
  XCircle,
} from 'lucide-react'
import {
  createApiKey,
  createCollection,
  createUser,
  deleteCollection,
  getAiProviders,
  getApiKeys,
  getCollections,
  getJobs,
  getSources,
  getUsageDashboard,
  getUsers,
  importConnectorSources,
  syncDueSources,
  syncSource,
  uploadDocument,
} from '../lib/api'
import { useLang } from '../lib/LangContext'
import ConfirmDialog from '../components/ConfirmDialog'
import { cn, EmptyState, IconButton, MetricCard, ProgressBar, SectionHeader, StatusBadge, Surface } from '../components/ProductUI'

const connectorCards = [
  { id: 'generic', label: 'Secure URL', detail: 'Import controlled web or file endpoints', icon: Link2 },
  { id: 'confluence', label: 'Confluence', detail: 'Team spaces, product docs, runbooks', icon: PlugZap },
  { id: 'sharepoint', label: 'SharePoint', detail: 'Microsoft knowledge estates', icon: CloudCog },
]

function JobStatus({ status }) {
  const tone = status === 'completed' ? 'emerald' : status === 'failed' ? 'rose' : 'amber'
  return <StatusBadge tone={tone}>{status}</StatusBadge>
}

function freshnessTone(status) {
  if (status === 'fresh') return 'emerald'
  if (status === 'aging') return 'amber'
  if (status === 'stale' || status === 'failed') return 'rose'
  return 'slate'
}

export default function AdminPage() {
  const { t } = useLang()
  const [collection, setCollection] = React.useState('HR-docs')
  const [newCollName, setNewCollName] = React.useState('')
  const [newCollDesc, setNewCollDesc] = React.useState('')
  const [pendingCollectionDelete, setPendingCollectionDelete] = React.useState(null)
  const [newUser, setNewUser] = React.useState({
    username: '',
    password: '',
    role: 'viewer',
    collections: 'HR-docs',
  })
  const [newKey, setNewKey] = React.useState({
    owner_username: '',
    name: 'integration-key',
    expires_in_days: '30',
    monthly_quota: '5000',
  })
  const [latestApiKey, setLatestApiKey] = React.useState('')
  const [connectorType, setConnectorType] = React.useState('generic')
  const [connectorCollection, setConnectorCollection] = React.useState('HR-docs')
  const [connectorUrls, setConnectorUrls] = React.useState('')
  const [connectorToken, setConnectorToken] = React.useState('')
  const [connectorAllowedUsers, setConnectorAllowedUsers] = React.useState('')
  const [connectorAllowedGroups, setConnectorAllowedGroups] = React.useState('')
  const [sourceCollection, setSourceCollection] = React.useState('')
  const [sourceFreshness, setSourceFreshness] = React.useState('all')
  const queryClient = useQueryClient()
  const fileInputRef = React.useRef(null)

  const colls = useQuery({ queryKey: ['collections'], queryFn: getCollections })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: getJobs, refetchInterval: 3000 })
  const users = useQuery({ queryKey: ['users'], queryFn: getUsers })
  const apiKeys = useQuery({ queryKey: ['api-keys'], queryFn: getApiKeys })
  const usage = useQuery({ queryKey: ['usage'], queryFn: getUsageDashboard, refetchInterval: 10000 })
  const aiProviders = useQuery({ queryKey: ['ai-providers'], queryFn: getAiProviders, refetchInterval: 15000 })
  const sources = useQuery({
    queryKey: ['sources', sourceCollection, sourceFreshness],
    queryFn: () => getSources({ collection: sourceCollection, freshness: sourceFreshness }),
    refetchInterval: 15000,
  })

  const upload = useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const addColl = useMutation({
    mutationFn: () => createCollection(newCollName.trim(), newCollDesc.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      setNewCollName('')
      setNewCollDesc('')
    },
  })

  const delColl = useMutation({
    mutationFn: deleteCollection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  const addUser = useMutation({
    mutationFn: (payload) => createUser(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      queryClient.invalidateQueries({ queryKey: ['usage'] })
      setNewUser({ username: '', password: '', role: 'viewer', collections: 'HR-docs' })
    },
  })

  const addApiKey = useMutation({
    mutationFn: (payload) => createApiKey(payload),
    onSuccess: (data) => {
      setLatestApiKey(data.api_key || '')
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
      queryClient.invalidateQueries({ queryKey: ['usage'] })
      setNewKey({
        owner_username: '',
        name: 'integration-key',
        expires_in_days: '30',
        monthly_quota: '5000',
      })
    },
  })

  const connectorImport = useMutation({
    mutationFn: (payload) => importConnectorSources(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      setConnectorUrls('')
      setConnectorToken('')
      setConnectorAllowedUsers('')
      setConnectorAllowedGroups('')
    },
  })
  const syncOne = useMutation({
    mutationFn: syncSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
  const syncDue = useMutation({
    mutationFn: () => syncDueSources(10),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const handleFiles = (files) => {
    if (!files?.length) return
    const fd = new FormData()
    fd.append('file', files[0])
    fd.append('collection', collection)
    upload.mutate(fd)
  }

  const createNewUser = () => {
    const collectionValues = newUser.collections
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    addUser.mutate({
      username: newUser.username.trim(),
      password: newUser.password,
      role: newUser.role,
      collections: collectionValues,
      write_collections: newUser.role === 'editor' ? collectionValues : [],
    })
  }

  const createNewApiKey = () => {
    addApiKey.mutate({
      owner_username: newKey.owner_username.trim(),
      name: newKey.name.trim(),
      expires_in_days: Number(newKey.expires_in_days) || null,
      monthly_quota: Number(newKey.monthly_quota) || 5000,
    })
  }

  const importConnector = () => {
    const source_urls = connectorUrls
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
    const allowed_users = connectorAllowedUsers
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    const allowed_groups = connectorAllowedGroups
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    const default_acl = allowed_users.length || allowed_groups.length ? { allowed_users, allowed_groups } : null
    connectorImport.mutate({
      connector: connectorType,
      collection: connectorCollection,
      source_urls,
      access_token: connectorToken.trim() || null,
      default_acl,
    })
  }

  const copyLatestKey = async () => {
    try {
      await navigator.clipboard.writeText(latestApiKey)
    } catch {
      // The generated key remains visible for manual selection if clipboard is unavailable.
    }
  }

  const collectionNames = colls.data?.collections || ['HR-docs', 'Legal-docs', 'Technical-docs']
  const collectionDetails = colls.data?.details || []
  const jobsList = jobs.data?.jobs || []
  const usersList = users.data?.users || []
  const apiKeyList = apiKeys.data?.api_keys || []
  const usageUsers = usage.data?.users || []
  const aiProviderData = aiProviders.data || {}
  const sourceList = sources.data?.sources || []
  const sourceSummary = sources.data?.summary || {}
  const connectorSummary = connectorImport.data || null
  const completed = jobsList.filter((j) => j.status === 'completed').length
  const failed = jobsList.filter((j) => j.status === 'failed').length
  const processing = jobsList.filter((j) => j.status === 'processing').length
  const totalQuota = usageUsers.reduce((sum, row) => sum + Number(row.monthly_quota || 0), 0)
  const totalUsed = usageUsers.reduce((sum, row) => sum + Number(row.used_this_month || 0), 0)
  const quotaPct = totalQuota ? Math.round((totalUsed / totalQuota) * 100) : 0
  const sourceRisk = (sourceSummary.stale || 0) + (sourceSummary.failed || 0)

  return (
    <div className="h-full overflow-y-auto bg-slate-100">
      <div className="mx-auto max-w-screen-2xl space-y-6 px-4 py-6 sm:px-6">
        <SectionHeader eyebrow="Governance command center" title={t('nav.admin')}>
          Ingest sources, control access, issue integration keys, monitor quotas, and keep model/provider posture visible.
        </SectionHeader>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <MetricCard label="Completed jobs" value={completed} meta="Ready sources" icon={CheckCircle2} tone="emerald" />
          <MetricCard label="Processing" value={processing} meta="Ingestion pipeline" icon={Activity} tone="amber" />
          <MetricCard label="Failed jobs" value={failed} meta="Needs attention" icon={XCircle} tone={failed ? 'rose' : 'slate'} />
          <MetricCard label="Users" value={usersList.length} meta="RBAC identities" icon={Users} tone="blue" />
          <MetricCard label="API keys" value={apiKeyList.length} meta="Integrations" icon={KeyRound} tone="violet" />
          <MetricCard label="Source risk" value={sourceRisk} meta={`${sourceSummary.due_for_sync || 0} sync due`} icon={Clock3} tone={sourceRisk ? 'rose' : 'emerald'} />
        </div>

        <div className="grid gap-6 xl:grid-cols-[24rem_minmax(0,1fr)_22rem]">
          <div className="space-y-6">
            <Surface className="p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-slate-950">{t('admin.upload')}</h3>
                  <p className="mt-1 text-xs text-slate-500">PDF, DOCX, TXT, Markdown, and CSV become searchable chunks.</p>
                </div>
                <UploadCloud className="h-5 w-5 text-blue-600" aria-hidden="true" />
              </div>

              <label className="mt-4 block text-xs font-bold uppercase tracking-wide text-slate-500">{t('admin.collection')}</label>
              <select
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                value={collection}
                onChange={(e) => setCollection(e.target.value)}
              >
                {collectionNames.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>

              <div
                className="mt-4 cursor-pointer rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 p-6 text-center transition hover:border-blue-300 hover:bg-blue-50"
                onClick={() => fileInputRef.current?.click()}
                onDrop={(e) => {
                  e.preventDefault()
                  handleFiles(e.dataTransfer.files)
                }}
                onDragOver={(e) => e.preventDefault()}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click()
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,.csv,.md"
                  className="hidden"
                  aria-label={t('admin.fileLabel')}
                  onChange={(e) => {
                    handleFiles(e.target.files)
                    e.target.value = ''
                  }}
                />
                <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-white text-blue-600 shadow-sm">
                  <FilePlus2 className="h-5 w-5" aria-hidden="true" />
                </div>
                <p className="mt-3 text-sm font-bold text-slate-800">Drop a source file or click to upload</p>
                <p className="mt-1 text-xs text-slate-500">{t('admin.fileLabel')}</p>
              </div>

              {upload.isPending && <p className="mt-3 rounded-lg bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700">{t('admin.ingesting')}</p>}
              {upload.isError && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{upload.error.message}</p>}
              {upload.isSuccess && <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700">{t('admin.uploadSuccess')}</p>}
            </Surface>

            <Surface className="p-5">
              <h3 className="text-sm font-bold text-slate-950">{t('admin.manageCollections')}</h3>
              <div className="mt-4 space-y-2">
                {collectionDetails.length === 0 ? (
                  <p className="text-sm text-slate-400">No collections yet.</p>
                ) : (
                  collectionDetails.map((c) => (
                    <div key={c.name} className="group rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-bold text-slate-800">{c.name}</p>
                          {c.description && <p className="mt-1 text-xs text-slate-500">{c.description}</p>}
                        </div>
                        <IconButton
                          label={t('docs.delete')}
                          className="h-8 w-8 text-rose-600 opacity-100 hover:border-rose-200 hover:text-rose-700 sm:opacity-0 sm:group-hover:opacity-100"
                          onClick={() => setPendingCollectionDelete(c.name)}
                        >
                          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                        </IconButton>
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div className="mt-4 space-y-2 border-t border-slate-200 pt-4">
                <input
                  type="text"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                  placeholder={t('admin.newCollName')}
                  value={newCollName}
                  onChange={(e) => setNewCollName(e.target.value)}
                />
                <input
                  type="text"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                  placeholder={t('admin.description')}
                  value={newCollDesc}
                  onChange={(e) => setNewCollDesc(e.target.value)}
                />
                <button
                  type="button"
                  className="w-full rounded-xl bg-blue-600 px-3 py-2 text-sm font-bold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!newCollName.trim() || addColl.isPending}
                  onClick={() => addColl.mutate()}
                >
                  {addColl.isPending ? t('admin.creating') : t('admin.createCollection')}
                </button>
              </div>
            </Surface>
          </div>

          <Surface className="overflow-hidden">
            <div className="border-b border-slate-200 p-5">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-950">{t('admin.ingestionJobs')}</h3>
                  <p className="mt-1 text-xs text-slate-500">Live job queue for source ingestion, chunking, and embedding.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusBadge tone="emerald">{completed} completed</StatusBadge>
                  <StatusBadge tone="amber">{processing} processing</StatusBadge>
                  <StatusBadge tone={failed ? 'rose' : 'slate'}>{failed} failed</StatusBadge>
                </div>
              </div>
            </div>
            <div className="max-h-[36rem] overflow-auto p-5">
              {jobsList.length === 0 ? (
                <EmptyState icon={Activity} title={t('admin.noJobs')} body="Upload a file or import connector sources to start the pipeline." />
              ) : (
                <table className="w-full min-w-[760px] text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left">
                      <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">{t('admin.document')}</th>
                      <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">{t('admin.collection')}</th>
                      <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">{t('admin.status')}</th>
                      <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">Chunks</th>
                      <th className="pb-3 text-xs font-bold uppercase tracking-wide text-slate-500">{t('admin.error')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {jobsList.map((j) => (
                      <tr key={j.id} className="transition hover:bg-slate-50">
                        <td className="max-w-[220px] truncate py-3 pr-4 font-semibold text-slate-800">{j.document_name}</td>
                        <td className="py-3 pr-4 text-slate-600">{j.collection}</td>
                        <td className="py-3 pr-4"><JobStatus status={j.status} /></td>
                        <td className="py-3 pr-4 text-slate-600">{j.chunks_created}</td>
                        <td className="max-w-[220px] truncate py-3 text-xs text-rose-600">{j.error || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Surface>

          <div className="space-y-6">
            <Surface className="p-5">
              <div className="flex items-center gap-2">
                <PlugZap className="h-5 w-5 text-blue-600" aria-hidden="true" />
                <h3 className="text-sm font-bold text-slate-950">Connector launchpad</h3>
              </div>
              <div className="mt-4 grid gap-2">
                {connectorCards.map((item) => {
                  const Icon = item.icon
                  const active = connectorType === item.id
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={cn(
                        'flex items-start gap-3 rounded-xl border p-3 text-left transition',
                        active ? 'border-blue-300 bg-blue-50 text-blue-800' : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-200',
                      )}
                      onClick={() => setConnectorType(item.id)}
                    >
                      <span className={cn('flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg', active ? 'bg-blue-600 text-white' : 'bg-white text-slate-500')}>
                        <Icon className="h-4 w-4" aria-hidden="true" />
                      </span>
                      <span>
                        <span className="block text-sm font-bold">{item.label}</span>
                        <span className="block text-xs opacity-70">{item.detail}</span>
                      </span>
                    </button>
                  )
                })}
              </div>
              <div className="mt-4 space-y-2">
                <select
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                  value={connectorCollection}
                  onChange={(e) => setConnectorCollection(e.target.value)}
                >
                  {collectionNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <textarea
                  className="min-h-28 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="One source URL per line"
                  value={connectorUrls}
                  onChange={(e) => setConnectorUrls(e.target.value)}
                />
                <input
                  type="password"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="Optional bearer token"
                  value={connectorToken}
                  onChange={(e) => setConnectorToken(e.target.value)}
                />
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <input
                    type="text"
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Allowed users, comma separated"
                    value={connectorAllowedUsers}
                    onChange={(e) => setConnectorAllowedUsers(e.target.value)}
                  />
                  <input
                    type="text"
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Allowed groups, comma separated"
                    value={connectorAllowedGroups}
                    onChange={(e) => setConnectorAllowedGroups(e.target.value)}
                  />
                </div>
                <button
                  type="button"
                  className="w-full rounded-xl bg-blue-600 px-3 py-2 text-sm font-bold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!connectorUrls.trim() || connectorImport.isPending}
                  onClick={importConnector}
                >
                  {connectorImport.isPending ? 'Importing...' : 'Import Sources'}
                </button>
                {connectorImport.isError && <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{connectorImport.error.message}</p>}
              </div>
              {connectorSummary && (
                <div className="mt-4 grid grid-cols-2 gap-2 border-t border-slate-200 pt-4">
                  <div className="rounded-lg bg-emerald-50 p-3 text-center">
                    <p className="text-xl font-bold text-emerald-700">{connectorSummary.imported?.length || 0}</p>
                    <p className="text-xs text-emerald-700">Imported</p>
                  </div>
                  <div className="rounded-lg bg-rose-50 p-3 text-center">
                    <p className="text-xl font-bold text-rose-700">{connectorSummary.failed?.length || 0}</p>
                    <p className="text-xs text-rose-700">Failed</p>
                  </div>
                </div>
              )}
            </Surface>

            <Surface className="p-5">
              <div className="flex items-center gap-2">
                <ServerCog className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                <h3 className="text-sm font-bold text-slate-950">AI provider profile</h3>
              </div>
              <div className="mt-4 space-y-3 text-sm">
                {[
                  ['LLM provider', aiProviderData.llm_provider || '-'],
                  ['Embedding provider', aiProviderData.embedding_provider || '-'],
                  ['Sovereignty mode', String(aiProviderData.data_sovereignty_mode ?? false)],
                  ['Finnish model', aiProviderData.local_llm_model_fi || '-'],
                  ['TurkuNLP endpoint', String(aiProviderData.turkunlp_embedding_configured ?? false)],
                ].map(([label, value]) => (
                  <div key={label} className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2 last:border-0 last:pb-0">
                    <span className="text-slate-500">{label}</span>
                    <span className="max-w-40 truncate font-semibold text-slate-800">{value}</span>
                  </div>
                ))}
              </div>
            </Surface>
          </div>
        </div>

        <Surface className="overflow-hidden">
          <div className="border-b border-slate-200 p-5">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Clock3 className="h-5 w-5 text-blue-600" aria-hidden="true" />
                  <h3 className="text-sm font-bold text-slate-950">Source freshness SLA</h3>
                </div>
                <p className="mt-1 text-xs text-slate-500">Track stale sources before they appear in citations or evidence packs.</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge tone="emerald">{sourceSummary.fresh || 0} fresh</StatusBadge>
                <StatusBadge tone="amber">{sourceSummary.aging || 0} aging</StatusBadge>
                <StatusBadge tone="rose">{(sourceSummary.stale || 0) + (sourceSummary.failed || 0)} at risk</StatusBadge>
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50"
                  disabled={syncDue.isPending || !(sourceSummary.due_for_sync || 0)}
                  onClick={() => syncDue.mutate()}
                >
                  <RefreshCw className={cn('h-4 w-4', syncDue.isPending && 'animate-spin')} aria-hidden="true" />
                  Sync due
                </button>
              </div>
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-[14rem_12rem]">
              <select
                className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                value={sourceCollection}
                onChange={(e) => setSourceCollection(e.target.value)}
              >
                <option value="">All collections</option>
                {collectionNames.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <select
                className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                value={sourceFreshness}
                onChange={(e) => setSourceFreshness(e.target.value)}
              >
                <option value="all">All statuses</option>
                <option value="fresh">Fresh</option>
                <option value="aging">Aging</option>
                <option value="stale">Stale</option>
                <option value="failed">Failed</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
          </div>
          <div className="overflow-auto p-5">
            {sourceList.length === 0 ? (
              <EmptyState icon={Clock3} title="No source records" body="Upload documents or import connector sources to start freshness tracking." />
            ) : (
              <table className="w-full min-w-[920px] text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left">
                    <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">Document</th>
                    <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">Collection</th>
                    <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">Freshness</th>
                    <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">Sync</th>
                    <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">Last synced</th>
                    <th className="pb-3 pr-4 text-xs font-bold uppercase tracking-wide text-slate-500">Next sync</th>
                    <th className="pb-3 text-xs font-bold uppercase tracking-wide text-slate-500">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sourceList.map((source) => (
                    <tr key={source.id} className="transition hover:bg-slate-50">
                      <td className="max-w-[260px] py-3 pr-4">
                        <p className="truncate font-semibold text-slate-800">{source.document_name}</p>
                        <p className="truncate text-xs text-slate-400">{source.source_url || source.connector}</p>
                      </td>
                      <td className="py-3 pr-4 text-slate-600">{source.collection}</td>
                      <td className="py-3 pr-4"><StatusBadge tone={freshnessTone(source.freshness_status)}>{source.freshness_status}</StatusBadge></td>
                      <td className="py-3 pr-4"><StatusBadge tone={source.sync_status === 'failed' ? 'rose' : source.sync_status === 'syncing' ? 'amber' : 'slate'}>{source.sync_status}</StatusBadge></td>
                      <td className="py-3 pr-4 text-xs text-slate-500">{source.last_synced_at?.split('.')[0] || '-'}</td>
                      <td className="py-3 pr-4 text-xs text-slate-500">{source.next_sync_at?.split('.')[0] || '-'}</td>
                      <td className="py-3">
                        <button
                          type="button"
                          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-blue-200 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
                          disabled={!source.source_url || syncOne.isPending}
                          onClick={() => syncOne.mutate(source.id)}
                        >
                          <RefreshCw className={cn('h-3.5 w-3.5', syncOne.isPending && 'animate-spin')} aria-hidden="true" />
                          Sync now
                        </button>
                        {source.last_sync_error && <p className="mt-1 max-w-[220px] truncate text-xs text-rose-600">{source.last_sync_error}</p>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Surface>

        <div className="grid gap-6 xl:grid-cols-3">
          <Surface className="p-5">
            <div className="flex items-center gap-2">
              <UserPlus className="h-5 w-5 text-blue-600" aria-hidden="true" />
              <h3 className="text-sm font-bold text-slate-950">Identity and access</h3>
            </div>
            <div className="mt-4 space-y-2">
              <input
                type="text"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                placeholder="Username"
                value={newUser.username}
                onChange={(e) => setNewUser((prev) => ({ ...prev, username: e.target.value }))}
              />
              <input
                type="password"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                placeholder="Password"
                value={newUser.password}
                onChange={(e) => setNewUser((prev) => ({ ...prev, password: e.target.value }))}
              />
              <div className="grid grid-cols-2 gap-2">
                <select
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                  value={newUser.role}
                  onChange={(e) => setNewUser((prev) => ({ ...prev, role: e.target.value }))}
                >
                  <option value="viewer">viewer</option>
                  <option value="editor">editor</option>
                  <option value="admin">admin</option>
                </select>
                <input
                  type="text"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Collections"
                  value={newUser.collections}
                  onChange={(e) => setNewUser((prev) => ({ ...prev, collections: e.target.value }))}
                />
              </div>
              <button
                type="button"
                className="w-full rounded-xl bg-blue-600 px-3 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-40"
                disabled={!newUser.username || !newUser.password || addUser.isPending}
                onClick={createNewUser}
              >
                {addUser.isPending ? 'Creating user...' : 'Create User'}
              </button>
              {addUser.isError && <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{addUser.error.message}</p>}
            </div>
            <div className="mt-5 border-t border-slate-200 pt-4">
              <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Users</p>
              <div className="max-h-56 space-y-2 overflow-auto">
                {usersList.map((user) => (
                  <div key={user.username} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <span className="truncate font-semibold text-slate-700">{user.username}</span>
                    <StatusBadge tone={user.role === 'admin' ? 'violet' : user.role === 'editor' ? 'blue' : 'slate'}>{user.role}</StatusBadge>
                  </div>
                ))}
              </div>
            </div>
          </Surface>

          <Surface className="p-5">
            <div className="flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-violet-600" aria-hidden="true" />
              <h3 className="text-sm font-bold text-slate-950">API key vault</h3>
            </div>
            <div className="mt-4 space-y-2">
              <input
                type="text"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                placeholder="Owner username"
                value={newKey.owner_username}
                onChange={(e) => setNewKey((prev) => ({ ...prev, owner_username: e.target.value }))}
              />
              <input
                type="text"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                placeholder="Key name"
                value={newKey.name}
                onChange={(e) => setNewKey((prev) => ({ ...prev, name: e.target.value }))}
              />
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="number"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Expires days"
                  value={newKey.expires_in_days}
                  onChange={(e) => setNewKey((prev) => ({ ...prev, expires_in_days: e.target.value }))}
                />
                <input
                  type="number"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Monthly quota"
                  value={newKey.monthly_quota}
                  onChange={(e) => setNewKey((prev) => ({ ...prev, monthly_quota: e.target.value }))}
                />
              </div>
              <button
                type="button"
                className="w-full rounded-xl bg-blue-600 px-3 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-40"
                disabled={!newKey.owner_username || !newKey.name || addApiKey.isPending}
                onClick={createNewApiKey}
              >
                {addApiKey.isPending ? 'Creating key...' : 'Create API Key'}
              </button>
              {addApiKey.isError && <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{addApiKey.error.message}</p>}
              {latestApiKey && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-xs font-bold uppercase tracking-wide text-emerald-700">New key</span>
                    <IconButton label="Copy API key" className="h-8 w-8 text-emerald-700 hover:border-emerald-200" onClick={copyLatestKey}>
                      <Clipboard className="h-3.5 w-3.5" aria-hidden="true" />
                    </IconButton>
                  </div>
                  <p className="break-all font-mono text-xs text-emerald-800">{latestApiKey}</p>
                </div>
              )}
            </div>
            <div className="mt-5 border-t border-slate-200 pt-4">
              <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Existing keys</p>
              <div className="max-h-56 space-y-2 overflow-auto">
                {apiKeyList.map((item) => (
                  <div key={item.id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate font-semibold text-slate-700">{item.name}</span>
                      <span className="font-mono text-xs text-slate-500">{item.key_preview}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{item.owner_username}</p>
                  </div>
                ))}
              </div>
            </div>
          </Surface>

          <Surface className="p-5">
            <div className="flex items-center gap-2">
              <LockKeyhole className="h-5 w-5 text-emerald-600" aria-hidden="true" />
              <h3 className="text-sm font-bold text-slate-950">Quota usage</h3>
            </div>
            <div className="mt-4 rounded-xl bg-slate-50 p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-700">Monthly consumption</span>
                <span className="font-bold text-slate-950">{quotaPct}%</span>
              </div>
              <ProgressBar value={quotaPct} tone={quotaPct > 80 ? 'rose' : quotaPct > 60 ? 'amber' : 'emerald'} className="mt-3" />
              <p className="mt-2 text-xs text-slate-500">{totalUsed} used of {totalQuota || 0} configured quota.</p>
            </div>
            <div className="mt-4 max-h-72 space-y-2 overflow-auto">
              {usageUsers.length === 0 && <p className="text-sm text-slate-400">No usage data yet</p>}
              {usageUsers.map((row) => {
                const pct = Math.round((Number(row.used_this_month || 0) / Math.max(1, Number(row.monthly_quota || 0))) * 100)
                return (
                  <div key={row.username} className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="mb-2 flex items-center justify-between text-xs text-slate-700">
                      <span className="font-bold">{row.username}</span>
                      <span>{row.used_this_month} / {row.monthly_quota}</span>
                    </div>
                    <ProgressBar value={pct} tone={pct > 80 ? 'rose' : 'blue'} />
                  </div>
                )
              })}
            </div>
          </Surface>
        </div>

        <ConfirmDialog
          open={!!pendingCollectionDelete}
          title={t('docs.delete')}
          message={pendingCollectionDelete ? t('admin.deleteConfirm').replace('$1', pendingCollectionDelete) : ''}
          confirmLabel={t('docs.delete')}
          cancelLabel="Cancel"
          onCancel={() => setPendingCollectionDelete(null)}
          onConfirm={() => {
            if (pendingCollectionDelete) {
              delColl.mutate(pendingCollectionDelete)
              setPendingCollectionDelete(null)
            }
          }}
        />
      </div>
    </div>
  )
}
