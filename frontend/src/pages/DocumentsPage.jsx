import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getDocuments, deleteDocument, getDocumentChunks, getStats, getCollections } from '../lib/api'
import { useLang } from '../lib/LangContext'
import ConfirmDialog from '../components/ConfirmDialog'

export default function DocumentsPage() {
  const { t } = useLang()
  const [collection, setCollection] = React.useState('HR-docs')
  const [selectedDoc, setSelectedDoc] = React.useState(null)
  const [chunkPage, setChunkPage] = React.useState(1)
  const [pendingDocDelete, setPendingDocDelete] = React.useState(null)
  const queryClient = useQueryClient()

  const colls = useQuery({ queryKey: ['collections'], queryFn: getCollections })
  const stats = useQuery({ queryKey: ['stats'], queryFn: getStats })
  const docs = useQuery({ queryKey: ['documents', collection], queryFn: () => getDocuments(collection) })
  const chunks = useQuery({
    queryKey: ['chunks', collection, selectedDoc, chunkPage],
    queryFn: () => getDocumentChunks(selectedDoc, collection, chunkPage),
    enabled: !!selectedDoc,
  })

  const deleteMut = useMutation({
    mutationFn: (docName) => deleteDocument(docName, collection),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['documents', collection] }); queryClient.invalidateQueries({ queryKey: ['stats'] }); setSelectedDoc(null) },
  })

  const docList = docs.data?.documents || []
  const statsData = stats.data || {}
  const collectionNames = colls.data?.collections || ['HR-docs', 'Legal-docs', 'Technical-docs']

  return (
    <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-800">{t('nav.documents')}</h2>
          <p className="text-sm text-slate-500 mt-0.5">Browse and inspect document collections</p>
        </div>
        <select
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-blue-500/20"
          value={collection}
          onChange={(e) => { setCollection(e.target.value); setSelectedDoc(null) }}
        >
          {collectionNames.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* Collection tabs */}
      {statsData.collections?.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {statsData.collections.map((c) => (
            <button
              key={c.name}
              className={`px-4 py-2 rounded-lg text-sm transition-colors border ${
                collection === c.name
                  ? 'bg-blue-50 border-blue-200 text-blue-700 font-medium'
                  : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
              onClick={() => { setCollection(c.name); setSelectedDoc(null) }}
            >
              {c.name} <span className="text-xs opacity-60">{c.documents} docs</span>
            </button>
          ))}
        </div>
      )}

      <div className="grid lg:grid-cols-5 gap-6">
        {/* Document list */}
        <div className="lg:col-span-2">
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-semibold text-slate-800 text-sm mb-3">
              {t('docs.title')} <span className="text-blue-600">{collection}</span>
            </h3>

            {docList.length === 0 ? (
              <p className="text-sm text-slate-400 py-6 text-center">{t('docs.noDocuments')}</p>
            ) : (
              <div className="space-y-1.5">
                {docList.map((d) => (
                  <div
                    key={d.document_name}
                    className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer group transition-colors ${
                      selectedDoc === d.document_name ? 'bg-blue-50 border border-blue-200' : 'hover:bg-slate-50 border border-transparent'
                    }`}
                    onClick={() => { setSelectedDoc(d.document_name); setChunkPage(1) }}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-700 truncate">{d.document_name}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{d.chunk_count} {t('docs.chunks')} &middot; {d.pages} {t('docs.pages')}</p>
                    </div>
                    <button
                      className="text-xs text-red-500 hover:text-red-700 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                      onClick={(e) => {
                        e.stopPropagation()
                        setPendingDocDelete(d.document_name)
                      }}
                    >
                      {t('docs.delete')}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Chunk viewer */}
        <div className="lg:col-span-3">
          {selectedDoc && chunks.data ? (
            <div className="bg-white border border-slate-200 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-slate-800 text-sm truncate">{selectedDoc}</h3>
                  <p className="text-xs text-slate-400">{chunks.data.total_chunks} {t('docs.chunks')}</p>
                </div>
                <button className="text-xs text-slate-500 hover:text-slate-700" onClick={() => setSelectedDoc(null)}>Close</button>
              </div>

              <div className="space-y-3">
                {chunks.data.chunks.map((c) => (
                  <div key={c.id} className="bg-slate-50 border border-slate-100 rounded-lg p-3">
                    <div className="flex gap-2 mb-2 text-xs">
                      <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 font-medium">{t('docs.page')} {c.page}</span>
                      <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">#{c.chunk_index}</span>
                      <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">{c.content_length} {t('docs.chars')}</span>
                    </div>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{c.content}</p>
                  </div>
                ))}
              </div>

              {chunks.data.total_chunks > chunks.data.per_page && (
                <div className="flex items-center justify-center gap-3 mt-4 pt-3 border-t border-slate-200">
                  <button className="px-3 py-1 rounded-lg text-sm bg-slate-100 hover:bg-slate-200 disabled:opacity-40" disabled={chunkPage <= 1} onClick={() => setChunkPage((p) => p - 1)}>
                    {t('docs.previous')}
                  </button>
                  <span className="text-xs text-slate-500">
                    {t('docs.page')} {chunkPage} {t('docs.of')} {Math.ceil(chunks.data.total_chunks / chunks.data.per_page)}
                  </span>
                  <button className="px-3 py-1 rounded-lg text-sm bg-slate-100 hover:bg-slate-200 disabled:opacity-40" disabled={chunkPage >= Math.ceil(chunks.data.total_chunks / chunks.data.per_page)} onClick={() => setChunkPage((p) => p + 1)}>
                    {t('docs.next')}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl p-5 flex items-center justify-center py-20">
              <div className="text-center">
                <p className="text-sm text-slate-500 font-medium">Select a document</p>
                <p className="text-xs text-slate-400 mt-1">Click on a document to inspect its chunks</p>
              </div>
            </div>
          )}
        </div>
      </div>
      <ConfirmDialog
        open={!!pendingDocDelete}
        title={t('docs.delete')}
        message={pendingDocDelete ? `Delete "${pendingDocDelete}"?` : ''}
        confirmLabel={t('docs.delete')}
        cancelLabel="Cancel"
        onCancel={() => setPendingDocDelete(null)}
        onConfirm={() => {
          if (pendingDocDelete) {
            deleteMut.mutate(pendingDocDelete)
            setPendingDocDelete(null)
          }
        }}
      />
    </div>
  )
}
