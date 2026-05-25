import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Database,
  FileText,
  Filter,
  Search,
  ShieldCheck,
  Trash2,
} from 'lucide-react'
import { deleteDocument, getCollections, getDocumentChunks, getDocuments, getStats } from '../lib/api'
import { useLang } from '../lib/LangContext'
import ConfirmDialog from '../components/ConfirmDialog'
import { cn, EmptyState, IconButton, MetricCard, ProgressBar, SectionHeader, StatusBadge, Surface } from '../components/ProductUI'

function chunkPreview(content = '') {
  return content.length > 420 ? `${content.slice(0, 420)}...` : content
}

function freshnessTone(status) {
  if (status === 'fresh') return 'emerald'
  if (status === 'aging') return 'amber'
  if (status === 'stale' || status === 'failed') return 'rose'
  return 'slate'
}

export default function DocumentsPage() {
  const { t } = useLang()
  const [collection, setCollection] = React.useState('HR-docs')
  const [selectedDoc, setSelectedDoc] = React.useState(null)
  const [chunkPage, setChunkPage] = React.useState(1)
  const [pendingDocDelete, setPendingDocDelete] = React.useState(null)
  const [query, setQuery] = React.useState('')
  const [sort, setSort] = React.useState('name')
  const [chunkFilter, setChunkFilter] = React.useState('')
  const queryClient = useQueryClient()

  const colls = useQuery({ queryKey: ['collections'], queryFn: getCollections })
  const stats = useQuery({ queryKey: ['stats'], queryFn: getStats, refetchInterval: 15000 })
  const docs = useQuery({ queryKey: ['documents', collection], queryFn: () => getDocuments(collection) })
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
  const collectionNames = colls.data?.collections || ['HR-docs', 'Legal-docs', 'Technical-docs']
  const selectedCollection = statsData.collections?.find((item) => item.name === collection)
  const filteredDocs = docList
    .filter((doc) => doc.document_name.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => {
      if (sort === 'chunks') return (b.chunk_count || 0) - (a.chunk_count || 0)
      if (sort === 'pages') return (b.pages || 0) - (a.pages || 0)
      return a.document_name.localeCompare(b.document_name)
    })
  const visibleChunks = (chunks.data?.chunks || []).filter((chunk) => {
    if (!chunkFilter.trim()) return true
    return chunk.content.toLowerCase().includes(chunkFilter.trim().toLowerCase())
  })
  const readiness = selectedCollection?.documents ? Math.min(100, selectedCollection.documents * 15) : 0

  return (
    <div className="h-full overflow-y-auto bg-slate-100">
      <div className="mx-auto max-w-screen-2xl space-y-6 px-4 py-6 sm:px-6">
        <SectionHeader
          eyebrow="Evidence library"
          title={t('nav.documents')}
          action={
            <select
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
              value={collection}
              onChange={(e) => {
                setCollection(e.target.value)
                setSelectedDoc(null)
                setChunkPage(1)
              }}
            >
              {collectionNames.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          }
        >
          Inspect indexed evidence, chunk coverage, and source readiness before teams rely on answers.
        </SectionHeader>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Total documents" value={statsData.total_documents || 0} meta="Across all collections" icon={FileText} tone="blue" />
          <MetricCard label="Indexed chunks" value={statsData.total_chunks || 0} meta="Retrieval units" icon={Database} tone="emerald" />
          <MetricCard label="Collections" value={statsData.collections?.length || collectionNames.length} meta="Permission scopes" icon={ShieldCheck} tone="violet" />
          <MetricCard label="Active collection" value={selectedCollection?.documents || docList.length} meta={`${collection} documents`} icon={BookOpen} tone="amber" />
        </div>

        {statsData.collections?.length > 0 && (
          <Surface className="p-3">
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              {statsData.collections.map((c) => {
                const active = collection === c.name
                return (
                  <button
                    key={c.name}
                    type="button"
                    className={cn(
                      'rounded-xl border p-3 text-left transition',
                      active ? 'border-blue-300 bg-blue-50 shadow-sm' : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-slate-50',
                    )}
                    onClick={() => {
                      setCollection(c.name)
                      setSelectedDoc(null)
                      setChunkPage(1)
                    }}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate text-sm font-bold text-slate-900">{c.name}</span>
                      <StatusBadge tone={c.documents ? 'emerald' : 'amber'}>{c.documents ? 'ready' : 'empty'}</StatusBadge>
                    </div>
                    <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                      <span>{c.documents} docs</span>
                      <span>{c.chunks} chunks</span>
                    </div>
                    <ProgressBar value={Math.min(100, c.documents * 15)} tone={active ? 'blue' : 'slate'} className="mt-2" />
                  </button>
                )
              })}
            </div>
          </Surface>
        )}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
          <Surface className="min-h-[34rem] overflow-hidden">
            <div className="border-b border-slate-200 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-slate-950">
                    {t('docs.title')} <span className="text-blue-700">{collection}</span>
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">{filteredDocs.length} visible documents</p>
                </div>
                <StatusBadge tone={readiness >= 60 ? 'emerald' : readiness > 0 ? 'amber' : 'rose'}>
                  {readiness >= 60 ? 'strong corpus' : readiness > 0 ? 'building corpus' : 'needs data'}
                </StatusBadge>
              </div>
              <div className="mt-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_9rem]">
                <label className="relative block">
                  <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
                  <input
                    type="search"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Search documents"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </label>
                <label className="relative block">
                  <Filter className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
                  <select
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                    value={sort}
                    onChange={(e) => setSort(e.target.value)}
                  >
                    <option value="name">Name</option>
                    <option value="chunks">Chunks</option>
                    <option value="pages">Pages</option>
                  </select>
                </label>
              </div>
            </div>

            <div className="max-h-[calc(100vh-25rem)] min-h-80 overflow-y-auto p-3">
              {filteredDocs.length === 0 ? (
                <EmptyState
                  icon={FileText}
                  title={docList.length ? 'No matching documents' : t('docs.noDocuments')}
                  body={docList.length ? 'Adjust the search query or sorting filter.' : 'Use Admin to ingest PDFs, DOCX, TXT, Markdown, or CSV files.'}
                />
              ) : (
                <div className="space-y-2">
                  {filteredDocs.map((d) => {
                    const active = selectedDoc === d.document_name
                    return (
                      <div
                        key={d.document_name}
                        className={cn(
                          'group rounded-xl border p-3 transition',
                          active ? 'border-blue-300 bg-blue-50 shadow-sm' : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-slate-50',
                        )}
                      >
                        <button
                          type="button"
                          className="block w-full text-left"
                          onClick={() => {
                            setSelectedDoc(d.document_name)
                            setChunkPage(1)
                            setChunkFilter('')
                          }}
                        >
                          <span className="block truncate text-sm font-bold text-slate-800">{d.document_name}</span>
                          <span className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                            <StatusBadge tone="slate">{d.chunk_count} {t('docs.chunks')}</StatusBadge>
                            <StatusBadge tone="blue">{d.pages} {t('docs.pages')}</StatusBadge>
                            {d.source?.freshness_status && (
                              <StatusBadge tone={freshnessTone(d.source.freshness_status)}>{d.source.freshness_status}</StatusBadge>
                            )}
                          </span>
                        </button>
                        <div className="mt-3 flex items-center justify-between gap-3">
                          <ProgressBar value={Math.min(100, (d.chunk_count || 0) * 4)} tone={active ? 'blue' : 'slate'} className="flex-1" />
                          <IconButton
                            label={t('docs.delete')}
                            className="h-8 w-8 opacity-100 text-rose-600 hover:border-rose-200 hover:text-rose-700 sm:opacity-0 sm:group-hover:opacity-100"
                            onClick={() => setPendingDocDelete(d.document_name)}
                          >
                            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                          </IconButton>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </Surface>

          <Surface className="min-h-[34rem] overflow-hidden">
            {selectedDoc && chunks.data ? (
              <>
                <div className="border-b border-slate-200 p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="min-w-0">
                      <h3 className="truncate text-base font-bold text-slate-950">{selectedDoc}</h3>
                      <p className="mt-1 text-xs text-slate-500">
                        {chunks.data.total_chunks} {t('docs.chunks')} indexed for retrieval
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="relative block">
                        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden="true" />
                        <input
                          type="search"
                          className="w-56 rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                          placeholder="Filter chunks"
                          value={chunkFilter}
                          onChange={(e) => setChunkFilter(e.target.value)}
                        />
                      </label>
                      <button type="button" className="text-sm font-medium text-slate-500 hover:text-slate-800" onClick={() => setSelectedDoc(null)}>
                        Close
                      </button>
                    </div>
                  </div>
                </div>

                <div className="max-h-[calc(100vh-21rem)] min-h-80 overflow-y-auto p-4">
                  {visibleChunks.length === 0 ? (
                    <EmptyState icon={Search} title="No matching chunks" body="Try a broader chunk filter." />
                  ) : (
                    <div className="space-y-3">
                      {visibleChunks.map((c) => (
                        <article key={c.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                          <div className="mb-3 flex flex-wrap gap-2 text-xs">
                            <StatusBadge tone="blue">{t('docs.page')} {c.page}</StatusBadge>
                            <StatusBadge tone="slate">Chunk #{c.chunk_index}</StatusBadge>
                            <StatusBadge tone="violet">{c.content_length} {t('docs.chars')}</StatusBadge>
                          </div>
                          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{chunkPreview(c.content)}</p>
                        </article>
                      ))}
                    </div>
                  )}
                </div>

                {chunks.data.total_chunks > chunks.data.per_page && (
                  <div className="flex items-center justify-center gap-3 border-t border-slate-200 p-3">
                    <IconButton
                      label={t('docs.previous')}
                      disabled={chunkPage <= 1}
                      onClick={() => setChunkPage((p) => p - 1)}
                    >
                      <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                    </IconButton>
                    <span className="text-xs font-medium text-slate-500">
                      {t('docs.page')} {chunkPage} {t('docs.of')} {Math.ceil(chunks.data.total_chunks / chunks.data.per_page)}
                    </span>
                    <IconButton
                      label={t('docs.next')}
                      disabled={chunkPage >= Math.ceil(chunks.data.total_chunks / chunks.data.per_page)}
                      onClick={() => setChunkPage((p) => p + 1)}
                    >
                      <ChevronRight className="h-4 w-4" aria-hidden="true" />
                    </IconButton>
                  </div>
                )}
              </>
            ) : (
              <div className="p-4">
                <EmptyState
                  icon={BookOpen}
                  title="Select a source document"
                  body="Review chunking, page coverage, and searchable evidence before relying on generated answers."
                  className="min-h-[30rem]"
                />
              </div>
            )}
          </Surface>
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
    </div>
  )
}
