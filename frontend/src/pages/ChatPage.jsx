import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { getCollections, sendChatStream, getChatSessions, getChatHistory, deleteChatSession } from '../lib/api'
import { useLang } from '../lib/LangContext'
import Citations from '../components/Citations'

export default function ChatPage() {
  const { t } = useLang()
  const [collection, setCollection] = React.useState('HR-docs')
  const [question, setQuestion] = React.useState('')
  const [sessionId, setSessionId] = React.useState('')
  const [messages, setMessages] = React.useState([])
  const queryClient = useQueryClient()
  const messagesEndRef = React.useRef(null)

  const collections = useQuery({
    queryKey: ['collections'],
    queryFn: getCollections,
  })

  const sessions = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: getChatSessions,
    refetchInterval: 10000,
  })

  const [isStreaming, setIsStreaming] = React.useState(false)
  const [streamError, setStreamError] = React.useState(null)

  const handleSend = async () => {
    if (!question.trim() || isStreaming) return
    setIsStreaming(true)
    setStreamError(null)

    const userMsg = question
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    setQuestion('')

    const assistantIdx = { current: -1 }

    await sendChatStream(userMsg, collection, sessionId, {
      onMetadata: (meta) => {
        if (meta.session_id && !sessionId) setSessionId(meta.session_id)
        setMessages((prev) => {
          assistantIdx.current = prev.length
          return [...prev, { role: 'assistant', content: '', language: meta.language, citations: meta.citations }]
        })
      },
      onToken: (token) => {
        setMessages((prev) => {
          const updated = [...prev]
          const idx = assistantIdx.current
          if (idx >= 0 && updated[idx]) {
            updated[idx] = { ...updated[idx], content: updated[idx].content + token }
          }
          return updated
        })
      },
      onDone: () => {
        setIsStreaming(false)
        queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      },
      onError: (err) => {
        setStreamError(err.message)
        setIsStreaming(false)
      },
    })
  }

  const loadSession = useMutation({
    mutationFn: getChatHistory,
    onSuccess: (data) => {
      setSessionId(data.session_id)
      setMessages(data.messages)
      if (data.messages.length > 0) {
        setCollection(data.messages[0].collection || 'HR-docs')
      }
    },
  })

  const deleteSession = useMutation({
    mutationFn: deleteChatSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      if (sessionId === deleteSession.variables) {
        startNewChat()
      }
    },
  })

  const startNewChat = () => {
    setSessionId('')
    setMessages([])
    setQuestion('')
  }

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e) => {
    e.preventDefault()
    handleSend()
  }

  const sessionList = sessions.data?.sessions || []

  return (
    <div className="grid md:grid-cols-4 gap-6">
      <div className="md:col-span-1">
        <div className="bg-white rounded-xl shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-slate-700 text-sm">{t('chat.history')}</h3>
            <button
              className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700"
              onClick={startNewChat}
            >
              {t('chat.newChat')}
            </button>
          </div>

          {sessionList.length === 0 ? (
            <p className="text-xs text-slate-400">{t('chat.noConversations')}</p>
          ) : (
            <div className="space-y-1 max-h-96 overflow-auto">
              {sessionList.map((s) => (
                <div
                  key={s.session_id}
                  className={`p-2 rounded cursor-pointer text-xs group ${
                    sessionId === s.session_id ? 'bg-blue-50 border border-blue-200' : 'hover:bg-slate-50'
                  }`}
                  onClick={() => loadSession.mutate(s.session_id)}
                >
                  <div className="flex justify-between items-start">
                    <p className="text-slate-700 truncate flex-1 font-medium">{s.preview || 'Empty session'}</p>
                    <button
                      className="text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100 ml-1"
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteSession.mutate(s.session_id)
                      }}
                    >
                      x
                    </button>
                  </div>
                  <p className="text-slate-400 mt-0.5">{s.collection} &middot; {s.message_count} {t('chat.msgs')}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="md:col-span-3">
        <div className="bg-white rounded-xl shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-800">{t('chat.title')}</h2>
            <div className="flex gap-2">
              <button
                className="px-3 py-1 rounded bg-slate-100 text-xs text-slate-600 hover:bg-slate-200"
                onClick={() => setQuestion('Mitkä ovat yrityksen lomatiedot?')}
              >
                {t('chat.fiSample')}
              </button>
              <button
                className="px-3 py-1 rounded bg-slate-100 text-xs text-slate-600 hover:bg-slate-200"
                onClick={() => setQuestion('What are the company vacation policies?')}
              >
                {t('chat.enSample')}
              </button>
            </div>
          </div>

          <div className="border border-slate-200 rounded-lg mb-4 max-h-96 overflow-auto p-4 bg-slate-50 min-h-[200px]" role="log" aria-label="Chat messages" aria-live="polite">
            {messages.length === 0 ? (
              <p className="text-sm text-slate-400 text-center mt-16">
                {t('chat.emptyChat')}
              </p>
            ) : (
              <div className="space-y-4">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[80%] rounded-lg p-3 text-sm ${
                        msg.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-white border border-slate-200 text-slate-700'
                      }`}
                    >
                      {msg.role === 'assistant' ? (
                        <>
                          {msg.language && (
                            <span className="text-xs text-slate-400 block mb-1">
                              {msg.language === 'fi' ? 'Suomi' : 'English'}
                            </span>
                          )}
                          <div
                            className="prose prose-sm max-w-none"
                            dangerouslySetInnerHTML={{
                              __html: DOMPurify.sanitize(marked.parse(msg.content || '')),
                            }}
                          />
                          <Citations citations={msg.citations} />
                        </>
                      ) : (
                        <p>{msg.content}</p>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit} className="flex gap-3" aria-label="Chat input">
            <select
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
              value={collection}
              onChange={(e) => setCollection(e.target.value)}
              aria-label={t('admin.collection')}
            >
              {(collections.data?.collections || ['HR-docs', 'Legal-docs', 'Technical-docs']).map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <input
              type="text"
              className="flex-1 border border-slate-300 rounded-lg px-4 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              placeholder={t('chat.placeholder')}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button
              type="submit"
              disabled={isStreaming || !question.trim()}
              aria-label={t('chat.send')}
              className="px-5 py-2 rounded-lg bg-blue-600 text-white font-medium text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isStreaming ? t('chat.thinking') : t('chat.send')}
            </button>
          </form>
          {streamError && (
            <p className="text-sm text-red-600 mt-2">Error: {streamError}</p>
          )}
        </div>
      </div>
    </div>
  )
}
