import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { getCollections, sendChatStream, getChatSessions, getChatHistory, deleteChatSession } from '../lib/api'
import { useLang } from '../lib/LangContext'
import Citations from '../components/Citations'

const langLabel = { fi: 'Suomi', en: 'English', sv: 'Svenska' }

export default function ChatPage() {
  const { t } = useLang()
  const [collection, setCollection] = React.useState('HR-docs')
  const [question, setQuestion] = React.useState('')
  const [sessionId, setSessionId] = React.useState('')
  const [messages, setMessages] = React.useState([])
  const queryClient = useQueryClient()
  const messagesEndRef = React.useRef(null)
  const inputRef = React.useRef(null)

  const collections = useQuery({ queryKey: ['collections'], queryFn: getCollections })
  const sessions = useQuery({ queryKey: ['chat-sessions'], queryFn: getChatSessions, refetchInterval: 10000 })

  const [isStreaming, setIsStreaming] = React.useState(false)
  const [streamError, setStreamError] = React.useState(null)

  const handleSend = async () => {
    if (!question.trim() || isStreaming) return
    setIsStreaming(true)
    setStreamError(null)
    const userMsg = question
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    setQuestion('')
    inputRef.current?.focus()
    const assistantIdx = { current: -1 }

    try {
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
    } finally {
      setIsStreaming(false)
    }
  }

  const loadSession = useMutation({
    mutationFn: getChatHistory,
    onSuccess: (data) => {
      setSessionId(data.session_id)
      setMessages(data.messages)
      if (data.messages.length > 0) setCollection(data.messages[0].collection || 'HR-docs')
    },
  })

  const deleteSession = useMutation({
    mutationFn: deleteChatSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      if (sessionId === deleteSession.variables) startNewChat()
    },
  })

  const startNewChat = () => { setSessionId(''); setMessages([]); setQuestion('') }

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e) => { e.preventDefault(); handleSend() }

  const sessionList = sessions.data?.sessions || []
  const collectionNames = collections.data?.collections || ['HR-docs', 'Legal-docs', 'Technical-docs']

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0 border-r border-slate-200 bg-white flex flex-col">
        <div className="p-3 border-b border-slate-200">
          <button className="w-full px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors" onClick={startNewChat}>
            + {t('chat.newChat')}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {sessionList.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-8">{t('chat.noConversations')}</p>
          ) : (
            <div className="space-y-0.5">
              {sessionList.map((s) => (
                <div
                  key={s.session_id}
                  className={`px-3 py-2.5 rounded-lg cursor-pointer text-xs group transition-colors ${
                    sessionId === s.session_id ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-50'
                  }`}
                  onClick={() => loadSession.mutate(s.session_id)}
                >
                  <div className="flex justify-between items-start gap-1">
                    <p className="font-medium line-clamp-2 leading-relaxed flex-1">{s.preview || 'Empty'}</p>
                    <button
                      className="text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0"
                      onClick={(e) => { e.stopPropagation(); deleteSession.mutate(s.session_id) }}
                      aria-label="Delete session"
                    >
                      &times;
                    </button>
                  </div>
                  <p className="text-slate-400 mt-1">{s.collection} &middot; {s.message_count} {t('chat.msgs')}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 bg-slate-50">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto" role="log" aria-label="Chat messages" aria-live="polite">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-md px-6">
                <h3 className="text-lg font-semibold text-slate-700 mb-1">{t('chat.title')}</h3>
                <p className="text-sm text-slate-400 mb-6">{t('chat.emptyChat')}</p>
                <div className="flex gap-2 justify-center">
                  <button className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs text-slate-600 hover:bg-slate-50 transition-colors" onClick={() => setQuestion('Mitkä ovat yrityksen lomatiedot?')}>
                    {t('chat.fiSample')}
                  </button>
                  <button className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs text-slate-600 hover:bg-slate-50 transition-colors" onClick={() => setQuestion('What are the company vacation policies?')}>
                    {t('chat.enSample')}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
              {messages.map((msg, i) => (
                <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                  {msg.role === 'assistant' && (
                    <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0 text-xs font-bold text-slate-500 mt-0.5">AI</div>
                  )}
                  <div className={`max-w-[75%] min-w-0 ${msg.role === 'user' ? '' : ''}`}>
                    {msg.role === 'assistant' && msg.language && (
                      <span className="text-[10px] text-slate-400 mb-1 block">{langLabel[msg.language] || msg.language}</span>
                    )}
                    <div className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white rounded-br-md'
                        : 'bg-white border border-slate-200 text-slate-700 rounded-bl-md'
                    }`}>
                      {msg.role === 'assistant' ? (
                        <>
                          {msg.content ? (
                            <div
                              className="prose prose-sm prose-slate max-w-none [&>p]:mb-2 [&>p:last-child]:mb-0"
                              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(msg.content || '')) }}
                            />
                          ) : (
                            <div className="flex gap-1 py-1">
                              <div className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse" />
                              <div className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse [animation-delay:0.2s]" />
                              <div className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse [animation-delay:0.4s]" />
                            </div>
                          )}
                          <Citations citations={msg.citations} />
                        </>
                      ) : (
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      )}
                    </div>
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 text-xs font-bold text-white mt-0.5">U</div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="flex-shrink-0 border-t border-slate-200 bg-white px-4 py-3">
          {streamError && (
            <p className="text-xs text-red-600 mb-2">Error: {streamError}</p>
          )}
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex items-center gap-2" aria-label="Chat input">
            <select
              className="flex-shrink-0 border border-slate-200 rounded-lg px-2.5 py-2 text-sm bg-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 outline-none"
              value={collection}
              onChange={(e) => setCollection(e.target.value)}
              aria-label={t('admin.collection')}
            >
              {collectionNames.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input
              ref={inputRef}
              type="text"
              className="flex-1 min-w-0 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 outline-none"
              placeholder={t('chat.placeholder')}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={isStreaming}
            />
            <button
              type="submit"
              disabled={isStreaming || !question.trim()}
              aria-label={t('chat.send')}
              className="flex-shrink-0 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {isStreaming ? '...' : t('chat.send')}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
