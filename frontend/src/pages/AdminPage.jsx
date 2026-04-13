import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getJobs, uploadDocument } from '../lib/api'

export default function AdminPage() {
  const [collection, setCollection] = React.useState('HR-docs')
  const queryClient = useQueryClient()

  const jobs = useQuery({
    queryKey: ['jobs'],
    queryFn: getJobs,
    refetchInterval: 3000,
  })

  const upload = useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
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

  const jobsList = jobs.data?.jobs || []
  const completed = jobsList.filter((j) => j.status === 'completed').length
  const failed = jobsList.filter((j) => j.status === 'failed').length
  const processing = jobsList.filter((j) => j.status === 'processing').length

  return (
    <div className="grid md:grid-cols-3 gap-6">
      <div className="md:col-span-1">
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Upload Documents</h2>

          <label className="block text-sm font-medium text-slate-600 mb-1">Collection</label>
          <select
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white w-full mb-4"
            value={collection}
            onChange={(e) => setCollection(e.target.value)}
          >
            <option>HR-docs</option>
            <option>Legal-docs</option>
            <option>Technical-docs</option>
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

        <div className="bg-white rounded-xl shadow p-6 mt-4">
          <h3 className="font-semibold text-slate-700 mb-3">Stats</h3>
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
                      <td className="py-2 text-red-500 text-xs max-w-xs truncate">{j.error || '—'}</td>
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
