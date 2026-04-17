import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getJobs,
  getCollections,
  uploadDocument,
  createCollection,
  deleteCollection,
  getUsers,
  createUser,
  getApiKeys,
  createApiKey,
  getUsageDashboard,
  getAiProviders,
  importConnectorSources,
} from '../lib/api'
import { useLang } from '../lib/LangContext'
import ConfirmDialog from '../components/ConfirmDialog'

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
  const queryClient = useQueryClient()
  const fileInputRef = React.useRef(null)

  const colls = useQuery({ queryKey: ['collections'], queryFn: getCollections })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: getJobs, refetchInterval: 3000 })
  const users = useQuery({ queryKey: ['users'], queryFn: getUsers })
  const apiKeys = useQuery({ queryKey: ['api-keys'], queryFn: getApiKeys })
  const usage = useQuery({ queryKey: ['usage'], queryFn: getUsageDashboard, refetchInterval: 10000 })
  const aiProviders = useQuery({ queryKey: ['ai-providers'], queryFn: getAiProviders, refetchInterval: 15000 })

  const upload = useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const addColl = useMutation({
    mutationFn: () => createCollection(newCollName.trim(), newCollDesc.trim()),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['collections'] }); setNewCollName(''); setNewCollDesc('') },
  })

  const delColl = useMutation({
    mutationFn: deleteCollection,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['collections'] }); queryClient.invalidateQueries({ queryKey: ['stats'] }) },
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
    },
  })

  const handleFiles = (files) => {
    if (!files?.length) return
    const fd = new FormData()
    fd.append('file', files[0])
    fd.append('collection', collection)
    upload.mutate(fd)
  }

  const collectionNames = colls.data?.collections || ['HR-docs', 'Legal-docs', 'Technical-docs']
  const collectionDetails = colls.data?.details || []
  const jobsList = jobs.data?.jobs || []
  const usersList = users.data?.users || []
  const apiKeyList = apiKeys.data?.api_keys || []
  const usageUsers = usage.data?.users || []
  const aiProviderData = aiProviders.data || {}
  const connectorSummary = connectorImport.data || null
  const completed = jobsList.filter((j) => j.status === 'completed').length
  const failed = jobsList.filter((j) => j.status === 'failed').length
  const processing = jobsList.filter((j) => j.status === 'processing').length

  return (
    <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-800">{t('nav.admin')}</h2>
        <p className="text-sm text-slate-500 mt-0.5">Manage documents, collections, and ingestion</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="space-y-5">
          {/* Upload */}
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-semibold text-slate-800 text-sm mb-3">{t('admin.upload')}</h3>

            <label className="block text-xs font-medium text-slate-500 mb-1">{t('admin.collection')}</label>
            <select
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white mb-3 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
              value={collection}
              onChange={(e) => setCollection(e.target.value)}
            >
              {collectionNames.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>

            <div
              className="border-2 border-dashed border-slate-200 rounded-xl p-6 text-center cursor-pointer hover:border-blue-300 hover:bg-blue-50/30 transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt,.csv,.md"
                className="hidden"
                aria-label={t('admin.fileLabel')}
                onChange={(e) => { handleFiles(e.target.files); e.target.value = '' }}
              />
              <p className="text-sm text-slate-600 font-medium">Click to upload</p>
              <p className="text-xs text-slate-400 mt-1">{t('admin.fileLabel')}</p>
            </div>

            {upload.isPending && <p className="text-sm text-blue-600 mt-2">{t('admin.ingesting')}</p>}
            {upload.isError && <p className="text-xs text-red-600 mt-2">{upload.error.message}</p>}
            {upload.isSuccess && <p className="text-xs text-green-600 mt-2">{t('admin.uploadSuccess')}</p>}
          </div>

          {/* Collections */}
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-semibold text-slate-800 text-sm mb-3">{t('admin.manageCollections')}</h3>
            <div className="space-y-2 mb-4">
              {collectionDetails.map((c) => (
                <div key={c.name} className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100 group">
                  <div>
                    <p className="text-sm font-medium text-slate-700">{c.name}</p>
                    {c.description && <p className="text-xs text-slate-400">{c.description}</p>}
                  </div>
                  <button
                    className="text-xs text-red-500 hover:text-red-700 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => setPendingCollectionDelete(c.name)}
                  >
                    {t('docs.delete')}
                  </button>
                </div>
              ))}
            </div>
            <div className="border-t border-slate-200 pt-3 space-y-2">
              <input type="text" className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/20" placeholder={t('admin.newCollName')} value={newCollName} onChange={(e) => setNewCollName(e.target.value)} />
              <input type="text" className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/20" placeholder={t('admin.description')} value={newCollDesc} onChange={(e) => setNewCollDesc(e.target.value)} />
              <button
                className="w-full px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors"
                disabled={!newCollName.trim() || addColl.isPending}
                onClick={() => addColl.mutate()}
              >
                {addColl.isPending ? t('admin.creating') : t('admin.createCollection')}
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-semibold text-slate-800 text-sm mb-3">{t('admin.ingestionStats')}</h3>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-green-50 rounded-lg p-3">
                <p className="text-xl font-bold text-green-700">{completed}</p>
                <p className="text-[10px] text-green-600 font-medium">{t('admin.completed')}</p>
              </div>
              <div className="bg-yellow-50 rounded-lg p-3">
                <p className="text-xl font-bold text-yellow-700">{processing}</p>
                <p className="text-[10px] text-yellow-600 font-medium">{t('admin.processing')}</p>
              </div>
              <div className="bg-red-50 rounded-lg p-3">
                <p className="text-xl font-bold text-red-700">{failed}</p>
                <p className="text-[10px] text-red-600 font-medium">{t('admin.failed')}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Jobs Table */}
        <div className="lg:col-span-2">
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-semibold text-slate-800 text-sm mb-4">{t('admin.ingestionJobs')}</h3>
            {jobsList.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-8">{t('admin.noJobs')}</p>
            ) : (
              <div className="overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left">
                      <th className="pb-2 pr-4 text-xs font-medium text-slate-500">{t('admin.document')}</th>
                      <th className="pb-2 pr-4 text-xs font-medium text-slate-500">{t('admin.collection')}</th>
                      <th className="pb-2 pr-4 text-xs font-medium text-slate-500">{t('admin.status')}</th>
                      <th className="pb-2 pr-4 text-xs font-medium text-slate-500">Chunks</th>
                      <th className="pb-2 text-xs font-medium text-slate-500">{t('admin.error')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {jobsList.map((j) => (
                      <tr key={j.id} className="hover:bg-slate-50">
                        <td className="py-2 pr-4 text-slate-700 font-medium max-w-[180px] truncate">{j.document_name}</td>
                        <td className="py-2 pr-4 text-slate-600">{j.collection}</td>
                        <td className="py-2 pr-4">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                            j.status === 'completed' ? 'bg-green-100 text-green-700' : j.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
                          }`}>{j.status}</span>
                        </td>
                        <td className="py-2 pr-4 text-slate-600">{j.chunks_created}</td>
                        <td className="py-2 text-red-500 text-xs max-w-[150px] truncate">{j.error || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
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

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-800 text-sm mb-3">Enterprise: Create User</h3>
          <div className="space-y-2">
            <input
              type="text"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Username"
              value={newUser.username}
              onChange={(e) => setNewUser((prev) => ({ ...prev, username: e.target.value }))}
            />
            <input
              type="password"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Password"
              value={newUser.password}
              onChange={(e) => setNewUser((prev) => ({ ...prev, password: e.target.value }))}
            />
            <select
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
              value={newUser.role}
              onChange={(e) => setNewUser((prev) => ({ ...prev, role: e.target.value }))}
            >
              <option value="viewer">viewer</option>
              <option value="editor">editor</option>
              <option value="admin">admin</option>
            </select>
            <input
              type="text"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Collections (comma separated)"
              value={newUser.collections}
              onChange={(e) => setNewUser((prev) => ({ ...prev, collections: e.target.value }))}
            />
            <button
              className="w-full px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-40"
              disabled={!newUser.username || !newUser.password || addUser.isPending}
              onClick={() => {
                const collectionValues = newUser.collections
                  .split(',')
                  .map((item) => item.trim())
                  .filter(Boolean)
                const payload = {
                  username: newUser.username.trim(),
                  password: newUser.password,
                  role: newUser.role,
                  collections: collectionValues,
                  write_collections: newUser.role === 'editor' ? collectionValues : [],
                }
                addUser.mutate(payload)
              }}
            >
              {addUser.isPending ? 'Creating user...' : 'Create User'}
            </button>
            {addUser.isError && <p className="text-xs text-red-600">{addUser.error.message}</p>}
          </div>
          <div className="mt-4 border-t border-slate-200 pt-3">
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-2">Users</p>
            <div className="space-y-1 max-h-44 overflow-auto">
              {usersList.map((user) => (
                <div key={user.username} className="text-xs text-slate-600 flex items-center justify-between bg-slate-50 rounded px-2 py-1">
                  <span>{user.username}</span>
                  <span className="text-slate-500">{user.role}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-800 text-sm mb-3">Enterprise: API Keys</h3>
          <div className="space-y-2">
            <input
              type="text"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Owner username"
              value={newKey.owner_username}
              onChange={(e) => setNewKey((prev) => ({ ...prev, owner_username: e.target.value }))}
            />
            <input
              type="text"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Key name"
              value={newKey.name}
              onChange={(e) => setNewKey((prev) => ({ ...prev, name: e.target.value }))}
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
                placeholder="Expires days"
                value={newKey.expires_in_days}
                onChange={(e) => setNewKey((prev) => ({ ...prev, expires_in_days: e.target.value }))}
              />
              <input
                type="number"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
                placeholder="Monthly quota"
                value={newKey.monthly_quota}
                onChange={(e) => setNewKey((prev) => ({ ...prev, monthly_quota: e.target.value }))}
              />
            </div>
            <button
              className="w-full px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-40"
              disabled={!newKey.owner_username || !newKey.name || addApiKey.isPending}
              onClick={() => {
                addApiKey.mutate({
                  owner_username: newKey.owner_username.trim(),
                  name: newKey.name.trim(),
                  expires_in_days: Number(newKey.expires_in_days) || null,
                  monthly_quota: Number(newKey.monthly_quota) || 5000,
                })
              }}
            >
              {addApiKey.isPending ? 'Creating key...' : 'Create API Key'}
            </button>
            {addApiKey.isError && <p className="text-xs text-red-600">{addApiKey.error.message}</p>}
            {latestApiKey && (
              <div className="text-xs bg-emerald-50 border border-emerald-200 rounded-lg px-2 py-2 text-emerald-700 break-all">
                New key: {latestApiKey}
              </div>
            )}
          </div>
          <div className="mt-4 border-t border-slate-200 pt-3">
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-2">Existing Keys</p>
            <div className="space-y-1 max-h-44 overflow-auto">
              {apiKeyList.map((item) => (
                <div key={item.id} className="text-xs text-slate-600 bg-slate-50 rounded px-2 py-1">
                  <div className="flex items-center justify-between">
                    <span>{item.name}</span>
                    <span>{item.key_preview}</span>
                  </div>
                  <p className="text-[11px] text-slate-500">{item.owner_username}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-800 text-sm mb-3">Enterprise: Quota Usage</h3>
          <div className="space-y-2 max-h-72 overflow-auto">
            {usageUsers.length === 0 && <p className="text-sm text-slate-400">No usage data yet</p>}
            {usageUsers.map((row) => (
              <div key={row.username} className="border border-slate-200 rounded-lg p-2">
                <div className="flex items-center justify-between text-xs text-slate-700 mb-1">
                  <span className="font-medium">{row.username}</span>
                  <span>{row.used_this_month} / {row.monthly_quota}</span>
                </div>
                <div className="w-full h-2 rounded bg-slate-100 overflow-hidden">
                  <div
                    className="h-full bg-blue-500"
                    style={{ width: `${Math.min(100, (row.used_this_month / Math.max(1, row.monthly_quota)) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-800 text-sm mb-3">Phase 4: AI Provider Profile</h3>
          <div className="space-y-2 text-xs text-slate-600">
            <div className="flex items-center justify-between border-b border-slate-100 pb-1">
              <span>LLM provider</span>
              <span className="font-medium text-slate-800">{aiProviderData.llm_provider || '—'}</span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-100 pb-1">
              <span>Embedding provider</span>
              <span className="font-medium text-slate-800">{aiProviderData.embedding_provider || '—'}</span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-100 pb-1">
              <span>Sovereignty mode</span>
              <span className="font-medium text-slate-800">{String(aiProviderData.data_sovereignty_mode ?? false)}</span>
            </div>
            <div className="flex items-center justify-between border-b border-slate-100 pb-1">
              <span>Finnish model</span>
              <span className="font-medium text-slate-800">{aiProviderData.local_llm_model_fi || '—'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>TurkuNLP endpoint</span>
              <span className="font-medium text-slate-800">{String(aiProviderData.turkunlp_embedding_configured ?? false)}</span>
            </div>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="font-semibold text-slate-800 text-sm mb-3">Phase 4: Connector Import</h3>
          <div className="space-y-2">
            <select
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
              value={connectorType}
              onChange={(e) => setConnectorType(e.target.value)}
            >
              <option value="generic">generic</option>
              <option value="confluence">confluence</option>
              <option value="sharepoint">sharepoint</option>
            </select>
            <select
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
              value={connectorCollection}
              onChange={(e) => setConnectorCollection(e.target.value)}
            >
              {collectionNames.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <textarea
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm min-h-24"
              placeholder="One source URL per line"
              value={connectorUrls}
              onChange={(e) => setConnectorUrls(e.target.value)}
            />
            <input
              type="password"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Optional bearer token"
              value={connectorToken}
              onChange={(e) => setConnectorToken(e.target.value)}
            />
            <button
              className="w-full px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-40"
              disabled={!connectorUrls.trim() || connectorImport.isPending}
              onClick={() => {
                const source_urls = connectorUrls
                  .split('\n')
                  .map((line) => line.trim())
                  .filter(Boolean)
                connectorImport.mutate({
                  connector: connectorType,
                  collection: connectorCollection,
                  source_urls,
                  access_token: connectorToken.trim() || null,
                })
              }}
            >
              {connectorImport.isPending ? 'Importing...' : 'Import Sources'}
            </button>
            {connectorImport.isError && <p className="text-xs text-red-600">{connectorImport.error.message}</p>}
          </div>
          {connectorSummary && (
            <div className="mt-3 text-xs border-t border-slate-200 pt-2 space-y-1">
              <p className="text-slate-700">Imported: {connectorSummary.imported?.length || 0}</p>
              <p className="text-slate-700">Failed: {connectorSummary.failed?.length || 0}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
