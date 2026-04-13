import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getJobs, getCollections, uploadDocument, createCollection, deleteCollection } from '../lib/api'
import { useLang } from '../lib/LangContext'

export default function AdminPage() {
  const { t } = useLang()
  const [collection, setCollection] = React.useState('HR-docs')
  const [newCollName, setNewCollName] = React.useState('')
  const [newCollDesc, setNewCollDesc] = React.useState('')
  const queryClient = useQueryClient()
  const fileInputRef = React.useRef(null)

  const colls = useQuery({ queryKey: ['collections'], queryFn: getCollections })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: getJobs, refetchInterval: 3000 })

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
                    onClick={() => { if (confirm(t('admin.deleteConfirm').replace('$1', c.name))) delColl.mutate(c.name) }}
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
    </div>
  )
}
