import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider, useMutation, useQuery } from '@tanstack/react-query'
import { marked } from 'marked'
import './index.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const queryClient = new QueryClient()

function App() {
  const [collection, setCollection] = React.useState('HR-docs')
  const [question, setQuestion] = React.useState('Mitkä ovat yrityksen lomatiedot?')
  const [answer, setAnswer] = React.useState(null)

  const jobs = useQuery({
    queryKey: ['jobs'],
    queryFn: async () => (await fetch(`${API}/admin/jobs`)).json(),
    refetchInterval: 3000,
  })

  const upload = useMutation({
    mutationFn: async (formData) => {
      const res = await fetch(`${API}/admin/upload`, { method: 'POST', body: formData })
      if (!res.ok) throw new Error(await res.text())
      return res.json()
    },
    onSuccess: () => jobs.refetch(),
  })

  const chat = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, collection }),
      })
      if (!res.ok) throw new Error(await res.text())
      return res.json()
    },
    onSuccess: (data) => setAnswer(data),
  })

  return (
    <div className="max-w-6xl mx-auto p-6 grid md:grid-cols-3 gap-4">
      <section className="bg-white p-4 rounded-xl shadow md:col-span-1">
        <h2 className="font-semibold mb-2">Admin Dashboard</h2>
        <select className="border rounded p-2 w-full mb-3" value={collection} onChange={(e) => setCollection(e.target.value)}>
          <option>HR-docs</option>
          <option>Legal-docs</option>
          <option>Technical-docs</option>
        </select>
        <input
          type="file"
          className="mb-2"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (!f) return
            const fd = new FormData()
            fd.append('file', f)
            fd.append('collection', collection)
            upload.mutate(fd)
          }}
        />
        <p className="text-sm text-slate-600 mb-2">{upload.isPending ? 'Ingesting...' : 'Upload a file to ingest.'}</p>

        <h3 className="font-medium mt-4">Ingestion Status</h3>
        <ul className="text-sm space-y-1 mt-2 max-h-56 overflow-auto">
          {(jobs.data?.jobs || []).map((j) => (
            <li key={j.id} className="border-b pb-1">
              <span className="font-medium">{j.document_name}</span> [{j.collection}] - {j.status} ({j.chunks_created} chunks)
            </li>
          ))}
        </ul>
      </section>

      <section className="bg-white p-4 rounded-xl shadow md:col-span-2">
        <h2 className="font-semibold mb-2">Bilingual Chat</h2>
        <div className="flex gap-2 mb-3">
          <button className="px-3 py-1 rounded bg-slate-200" onClick={() => setQuestion('Mitkä ovat yrityksen lomatiedot?')}>
            FI sample
          </button>
          <button className="px-3 py-1 rounded bg-slate-200" onClick={() => setQuestion('What are the company vacation policies?')}>
            EN sample
          </button>
        </div>
        <textarea
          className="w-full border rounded p-2 h-24"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="mt-2 px-4 py-2 rounded bg-blue-600 text-white" onClick={() => chat.mutate()}>
          Ask
        </button>

        {answer && (
          <div className="mt-4">
            <p className="text-xs uppercase text-slate-500">Detected language: {answer.language}</p>
            <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: marked.parse(answer.answer || '') }} />

            <h3 className="font-medium mt-4">Source Citations</h3>
            <ul className="text-sm list-disc pl-5">
              {answer.citations.map((c) => (
                <li key={c.chunk_id}>
                  {c.document} - page {c.page} (relevance: {c.relevance})
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
)
