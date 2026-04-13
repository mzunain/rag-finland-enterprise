import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getJobs, getCollections, uploadDocument, createCollection, deleteCollection } from '../lib/api'

export default function AdminPage() {
  const [collection, setCollection] = React.useState('HR-docs')
  const [newCollName, setNewCollName] = React.useState('')
  const [newCollDesc, setNewCollDesc] = React.useState('')
  const queryClient = useQueryClient()

  const colls = useQuery({
    queryKey: ['collections'],
    queryFn: getCollections,
  })

  const jobs = useQuery({
    queryKey: ['jobs'],
    queryFn: getJobs,
    refetchInterval: 3000,
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

  const handleFileChange = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    const fd = new FormData()
    fd.append('file', f)
    fd.append('collection', collection)
    upload.mutate(fd)
    e.target.value = ''
  }

  const collectionNames = colls.data?.collections || ['HR-docs', 'Legal-docs', 'Technical-docs']
  const collectionDetails = colls.data?.details || []
  const jobsList = jobs.data?.jobs || []
  const completed = jobsList.filter((j) => j.status === 'completed').length
  const failed = jobsList.filter((j) => j.status === 'failed').length
  const processing = jobsList.filter((j) => j.status === 'processing').length

  return (
    <div className="grid md:grid-cols-3 gap-6">
      <div className="md:col-span-1 space-y-4">
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Upload Documents</h2>

          <label className="block text-sm font-medium text-slate-600 mb-1">Collection</label>
          <select
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white w-full mb-4"
            value={collection}
            onChange={(e) => setCollection(e.target.value)}
          >
            {collectionNames.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          <label className="block text-sm font-medium text-slate-600 mb-1">File (PDF, DOCX, TXT, CSV)</label>
          <input
            type="file"
            accept=".pdf,.docx,.txt,.csv,.md"
            className="text-sm w-full"
            onChange={handleFileChange}
          />

          <div className="mt-3 text-sm">
            {upload.isPending && <p className="text-blue-600">Ingesting document...</p>}
            {upload.isError && <p className="text-red-600">Error: {upload.error.message}</p>}
            {upload.isSuccess && <p className="text-green-600">Document ingested successfully.</p>}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold text-slate-700 mb-3">Manage Collections</h3>
          <div className="space-y-2 mb-4">
            {collectionDetails.map((c) => (
              <div key={c.name} className="flex items-center justify-between p-2 border border-slate-200 rounded-lg">
                <div>
                  <p className="text-sm font-medium text-slate-700">{c.name}</p>
                  {c.description && <p className="text-xs text-slate-400">{c.description}</p>}
                </div>
                <button
                  className="text-xs text-red-500 hover:text-red-700"
                  onClick={() => {
                    if (confirm(`Delete collection "${c.name}" and ALL its documents?`)) {
                      delColl.mutate(c.name)
                    }
                  }}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
          <div className="border-t border-slate-200 pt-3">
            <input
              type="text"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-full mb-2"
              placeholder="New collection name"
              value={newCollName}
              onChange={(e) => setNewCollName(e.target.value)}
            />
            <input
              type="text"
              className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm w-full mb-2"
              placeholder="Description (optional)"
              value={newCollDesc}
              onChange={(e) => setNewCollDesc(e.target.value)}
            />
            <button
              className="w-full px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              disabled={!newCollName.trim() || addColl.isPending}
              onClick={() => addColl.mutate()}
            >
              {addColl.isPending ? 'Creating...' : 'Create Collection'}
            </button>
            {addColl.isError && <p className="text-xs text-red-600 mt-1">{addColl.error.message}</p>}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold text-slate-700 mb-3">Ingestion Stats</h3>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-green-50 rounded-lg p-3">
              <p className="text-2xl font-bold text-green-700">{completed}</p>
              <p className="text-xs text-green-600">Completed</p>
            </div>
            <div className="bg-yellow-50 rounded-lg p-3">
              <p className="text-2xl font-bold text-yellow-700">{processing}</p>
              <p className="text-xs text-yellow-600">Processing</p>
            </div>
            <div className="bg-red-50 rounded-lg p-3">
              <p className="text-2xl font-bold text-red-700">{failed}</p>
              <p className="text-xs text-red-600">Failed</p>
            </div>
          </div>
        </div>
      </div>

      <div className="md:col-span-2">
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Ingestion Jobs</h2>

          {jobsList.length === 0 ? (
            <p className="text-sm text-slate-500">No ingestion jobs yet. Upload a document to get started.</p>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="pb-2 pr-4">Document</th>
                    <th className="pb-2 pr-4">Collection</th>
                    <th className="pb-2 pr-4">Status</th>
                    <th className="pb-2 pr-4">Chunks</th>
                    <th className="pb-2">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {jobsList.map((j) => (
                    <tr key={j.id} className="border-b border-slate-100">
                      <td className="py-2 pr-4 font-medium text-slate-700">{j.document_name}</td>
                      <td className="py-2 pr-4 text-slate-600">{j.collection}</td>
                      <td className="py-2 pr-4">
                        <span
                          className={`text-xs font-medium px-2 py-1 rounded-full ${
                            j.status === 'completed'
                              ? 'bg-green-100 text-green-700'
                              : j.status === 'failed'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-yellow-100 text-yellow-700'
                          }`}
                        >
                          {j.status}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-slate-600">{j.chunks_created}</td>
                      <td className="py-2 text-red-500 text-xs max-w-xs truncate">{j.error || '\u2014'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
