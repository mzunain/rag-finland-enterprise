import React from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { getCollections, sendChat } from '../lib/api'
import Citations from '../components/Citations'

export default function ChatPage() {
  const [collection, setCollection] = React.useState('HR-docs')
  const [question, setQuestion] = React.useState('')
  const [answer, setAnswer] = React.useState(null)

  const collections = useQuery({
    queryKey: ['collections'],
    queryFn: getCollections,
  })

  const chat = useMutation({
    mutationFn: () => sendChat(question, collection),
    onSuccess: (data) => setAnswer(data),
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!question.trim()) return
    chat.mutate()
  }

  return (
    <div className="grid md:grid-cols-3 gap-6">
      <div className="md:col-span-2">
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Bilingual Chat</h2>

          <div className="flex gap-2 mb-3 flex-wrap">
            <button
              className="px-3 py-1 rounded bg-slate-100 text-sm text-slate-600 hover:bg-slate-200"
              onClick={() => setQuestion('Mitkä ovat yrityksen lomatiedot?')}
            >
              FI: Lomatiedot
            </button>
            <button
              className="px-3 py-1 rounded bg-slate-100 text-sm text-slate-600 hover:bg-slate-200"
              onClick={() => setQuestion('What are the company vacation policies?')}
            >
              EN: Vacation policy
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="flex gap-3 items-start">
              <select
                className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
                value={collection}
                onChange={(e) => setCollection(e.target.value)}
              >
                {(collections.data?.collections || ['HR-docs', 'Legal-docs', 'Technical-docs']).map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <textarea
              className="w-full border border-slate-300 rounded-lg p-3 mt-3 h-28 text-sm resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              placeholder="Ask a question in Finnish or English..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />

            <div className="flex items-center gap-3 mt-3">
              <button
                type="submit"
                disabled={chat.isPending || !question.trim()}
                className="px-5 py-2 rounded-lg bg-blue-600 text-white font-medium text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {chat.isPending ? 'Thinking...' : 'Ask'}
              </button>
              {chat.isError && (
                <p className="text-sm text-red-600">Error: {chat.error.message}</p>
              )}
            </div>
          </form>

          {answer && (
            <div className="mt-6 pt-6 border-t border-slate-200">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-medium px-2 py-1 rounded-full bg-slate-100 text-slate-600">
                  {answer.language === 'fi' ? 'Suomi' : 'English'}
                </span>
              </div>
              <div
                className="prose prose-slate max-w-none text-sm"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(marked.parse(answer.answer || '')),
                }}
              />
              <Citations citations={answer.citations} />
            </div>
          )}
        </div>
      </div>

      <div className="md:col-span-1">
        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="font-semibold text-slate-700 mb-3">How to use</h3>
          <ul className="text-sm text-slate-600 space-y-2">
            <li>1. Select a document collection</li>
            <li>2. Type your question in Finnish or English</li>
            <li>3. The system detects your language automatically</li>
            <li>4. Answers include source citations with relevance scores</li>
          </ul>
          <div className="mt-4 p-3 bg-blue-50 rounded-lg">
            <p className="text-xs text-blue-700">
              Finnish queries use Snowball stemming + lexical reranking for optimized retrieval.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
