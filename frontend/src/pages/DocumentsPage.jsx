import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getDocuments, deleteDocument, getDocumentChunks, getStats } from '../lib/api'

export default function DocumentsPage() {
  const [collection, setCollection] = React.useState('HR-docs')
  const [selectedDoc, setSelectedDoc] = React.useState(null)
  const [chunkPage, setChunkPage] = React.useState(1)
  const queryClient = useQueryClient()

  const stats = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
  })

  const docs = useQuery({
    queryKey: ['documents', collection],
    queryFn: () => getDocuments(collection),
  })

  const chunks = useQuery({
    queryKey: ['chunks', collection, selectedDoc, chunkPage],
    queryFn: () => getDocumentChunks(selectedDoc, collection, chunkPage),
    enabled: !!selectedDoc,
  })

  const deleteMut = useMutation({
    mutationFn: (docName) => deleteDocument(docName, collection),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', collection] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      setSelectedDoc(null)
    },
  })

  const docList = docs.data?.documents || []
  const statsData = stats.data || {}

  return (
    <div className="grid md:grid-cols-3 gap-6">
      <div className="md:col-span-1 space-y-4">
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Collections Overview</h2>
          {statsData.collections?.length > 0 ? (
            <div className="space-y-2">
              {statsData.collections.map((c) => (
                <div
                  key={c.name}
                  className={`p-3 rounded-lg border cursor-pointer ${
                    collection === c.name ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:bg-slate-50'
                  }`}
                  onClick={() => { setCollection(c.name); setSelectedDoc(null) }}
                >
                  <p className="font-medium text-sm text-slate-700">{c.name}</p>
                  <p className="text-xs text-slate-500">{c.documents} docs, {c.chunks} chunks</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">No documents ingested yet.</p>
          )}
          <div className="mt-4 pt-4 border-t border-slate-200">
            <p className="text-xs text-slate-500">
              Total: {statsData.total_documents || 0} documents, {statsData.total_chunks || 0} chunks
            </p>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow p-6">
          <label className="block text-sm font-medium text-slate-600 mb-2">Browse collection</label>
          <select
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white w-full"
            value={collection}
            onChange={(e) => { setCollection(e.target.value); setSelectedDoc(null) }}
          >
            <option>HR-docs</option>
            <option>Legal-docs</option>
            <option>Technical-docs</option>
          </select>
        </div>
      </div>

      <div className="md:col-span-2 space-y-4">
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">
            Documents in {collection}
          </h2>

          {docList.length === 0 ? (
            <p className="text-sm text-slate-500">No documents in this collection. Go to Admin to upload.</p>
          ) : (
            <div className="space-y-2">
              {docList.map((d) => (
                <div
                  key={d.document_name}
                  className={`flex items-center justify-between p-3 rounded-lg border ${
                    selectedDoc === d.document_name ? 'border-blue-500 bg-blue-50' : 'border-slate-200'
                  }`}
                >
                  <div
                    className="flex-1 cursor-pointer"
                    onClick={() => { setSelectedDoc(d.document_name); setChunkPage(1) }}
                  >
                    <p className="font-medium text-sm text-slate-700">{d.document_name}</p>
                    <p className="text-xs text-slate-500">
                      {d.chunk_count} chunks, {d.pages} pages
                      {d.created_at && ` \u00B7 ${d.created_at.split('T')[0]}`}
                    </p>
                  </div>
                  <button
                    className="text-xs text-red-500 hover:text-red-700 px-2 py-1"
                    onClick={() => {
                      if (confirm(`Delete "${d.document_name}" and all its chunks?`)) {
                        deleteMut.mutate(d.document_name)
                      }
                    }}
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {selectedDoc && chunks.data && (
          <div className="bg-white rounded-xl shadow p-6">
            <h3 className="font-semibold text-slate-700 mb-3">
              Chunks: {selectedDoc}
              <span className="text-xs font-normal text-slate-400 ml-2">
                ({chunks.data.total_chunks} total)
              </span>
            </h3>
            <div className="space-y-3">
              {chunks.data.chunks.map((c) => (
                <div key={c.id} className="border border-slate-200 rounded-lg p-3">
                  <div className="flex gap-3 text-xs text-slate-500 mb-2">
                    <span>Page {c.page}</span>
                    <span>Chunk #{c.chunk_index}</span>
                    <span>{c.content_length} chars</span>
                  </div>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{c.content}</p>
                </div>
              ))}
            </div>

            {chunks.data.total_chunks > chunks.data.per_page && (
              <div className="flex gap-2 mt-4 justify-center">
                <button
                  className="px-3 py-1 rounded text-sm bg-slate-100 hover:bg-slate-200 disabled:opacity-50"
                  disabled={chunkPage <= 1}
                  onClick={() => setChunkPage((p) => p - 1)}
                >
                  Previous
                </button>
                <span className="text-sm text-slate-500 py-1">
                  Page {chunkPage} of {Math.ceil(chunks.data.total_chunks / chunks.data.per_page)}
                </span>
                <button
                  className="px-3 py-1 rounded text-sm bg-slate-100 hover:bg-slate-200 disabled:opacity-50"
                  disabled={chunkPage >= Math.ceil(chunks.data.total_chunks / chunks.data.per_page)}
                  onClick={() => setChunkPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
