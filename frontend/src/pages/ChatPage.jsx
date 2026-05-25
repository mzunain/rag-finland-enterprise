import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import {
  ArrowUp,
  BookOpenCheck,
  Brain,
  CheckCircle2,
  Clipboard,
  Download,
  Flag,
  FileSearch,
  Languages,
  MessageSquarePlus,
  Scale,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  ThumbsUp,
  Trash2,
} from 'lucide-react'
import {
  deleteChatSession,
  getAiProviders,
  getChatHistory,
  getChatSessions,
  getCollections,
  getStats,
  sendChatFeedback,
  sendChatStream,
} from '../lib/api'
import { useLang } from '../lib/LangContext'
import Citations from '../components/Citations'
import { cn, EmptyState, IconButton, ProgressBar, StatusBadge, Surface } from '../components/ProductUI'

const langLabel = { fi: 'Suomi', en: 'English', sv: 'Svenska' }

const answerModes = [
  {
    id: 'answer',
    label: 'Answer',
    helper: 'Direct cited answer',
    icon: BookOpenCheck,
    instruction: '',
  },
  {
    id: 'brief',
    label: 'Brief',
    helper: 'Executive summary',
    icon: Sparkles,
    instruction: 'Return a concise executive brief with decisions, source-backed facts, and open questions.',
  },
  {
    id: 'risk',
    label: 'Risk',
    helper: 'Compliance lens',
    icon: Scale,
    instruction: 'Evaluate policy, legal, and operational risk. Separate confirmed facts from missing evidence.',
  },
  {
    id: 'compare',
    label: 'Compare',
    helper: 'Source comparison',
    icon: FileSearch,
    instruction: 'Compare the cited sources, call out conflicts, and name which document is strongest evidence.',
  },
]

const promptTemplates = [
  'Summarize the policy and list the exact source pages.',
  'What changed between the cited documents, and what should a manager do next?',
  'Find missing or ambiguous compliance requirements in this collection.',
  'Answer in Finnish and include only claims that are supported by citations.',
]

function citationQuality(citations = [], answerQuality = null) {
  if (answerQuality?.confidence_label) {
    const score = Math.round((Number(answerQuality.source_confidence) || 0) * 100)
    const labels = {
      high: 'High source confidence',
      medium: 'Review recommended',
      low: 'Low retrieval signal',
      no_context: 'No supporting context',
    }
    const tones = { high: 'emerald', medium: 'amber', low: 'rose', no_context: 'rose' }
    return {
      score,
      label: labels[answerQuality.confidence_label] || 'Review recommended',
      tone: tones[answerQuality.confidence_label] || 'amber',
    }
  }
  if (!citations.length) return { score: 0, label: 'No citations', tone: 'rose' }
  const avg = citations.reduce((sum, item) => sum + (Number(item.relevance) || 0), 0) / citations.length
  const score = Math.max(0, Math.min(100, Math.round(avg * 100)))
  if (score >= 55) return { score, label: 'High source confidence', tone: 'emerald' }
  if (score >= 35) return { score, label: 'Review recommended', tone: 'amber' }
  return { score, label: 'Low retrieval signal', tone: 'rose' }
}

function tableCell(value) {
  return String(value ?? '')
    .replace(/\|/g, '\\|')
    .replace(/\s+/g, ' ')
    .trim()
}

function evidenceFileName(collection, question) {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  const topic = tableCell(question || 'answer').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 48)
  return `evidence-${collection || 'collection'}-${topic || 'answer'}-${stamp}.md`
}

function buildEvidencePack({ msg, question, collection, sessionId }) {
  const citations = Array.isArray(msg.citations) ? msg.citations : []
  const quality = citationQuality(citations, msg.answer_quality)
  const qualityDetails = msg.answer_quality || {}
  const citationRows = citations.map((citation) =>
    [
      tableCell(citation.document || 'Unknown'),
      tableCell(citation.page || ''),
      tableCell(citation.relevance != null ? `${Math.round(Number(citation.relevance) * 100)}%` : ''),
      tableCell(citation.source_freshness || ''),
      tableCell(citation.last_synced_at || ''),
      tableCell(citation.chunk_id || ''),
    ].join(' | '),
  )

  return [
    '# RAG evidence pack',
    '',
    `Generated: ${new Date().toISOString()}`,
    `Collection: ${collection || msg.collection || 'Unknown'}`,
    `Session: ${sessionId || 'unsaved'}`,
    `Language: ${msg.language || 'unknown'}`,
    `Answer mode: ${msg.mode_context || 'standard'}`,
    '',
    '## Question',
    '',
    question || 'Unknown question',
    '',
    '## Answer',
    '',
    msg.content || 'No answer text available.',
    '',
    '## Source confidence',
    '',
    `- Label: ${quality.label}`,
    `- Score: ${quality.score}%`,
    `- Outcome: ${qualityDetails.outcome || (citations.length ? 'grounded' : 'no_context')}`,
    `- Required review: ${qualityDetails.requires_review ? 'yes' : 'no'}`,
    '',
    '## Citations',
    '',
    citations.length
      ? ['Document | Page | Relevance | Freshness | Last synced | Chunk', '--- | --- | --- | --- | --- | ---', ...citationRows].join('\n')
      : 'No citations were returned for this answer.',
  ].join('\n')
}

function MessageBubble({ msg, messageIndex, onCopy, onExport, onFeedback, feedbackPending }) {
  const isAssistant = msg.role === 'assistant'
  const quality = citationQuality(msg.citations, msg.answer_quality)

  return (
    <article className={cn('flex gap-3', msg.role === 'user' && 'justify-end')}>
      {isAssistant && (
        <div className="mt-1 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-slate-950 text-white shadow-sm">
          <Brain className="h-4 w-4" aria-hidden="true" />
        </div>
      )}
      <div className={cn('min-w-0 max-w-[88%] md:max-w-[78%]', msg.role === 'user' && 'order-first')}>
        {isAssistant && (
          <div className="mb-1.5 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
            {msg.language && <StatusBadge tone="slate">{langLabel[msg.language] || msg.language}</StatusBadge>}
            <StatusBadge tone={quality.tone}>{quality.label}</StatusBadge>
            {msg.citations?.length > 0 && <span>{msg.citations.length} sources</span>}
          </div>
        )}
        <div
          className={cn(
            'rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm',
            msg.role === 'user'
              ? 'rounded-br-md bg-blue-600 text-white'
              : 'rounded-bl-md border border-slate-200 bg-white text-slate-700',
          )}
        >
          {isAssistant ? (
            <>
              {msg.content ? (
                <div
                  className="prose prose-sm prose-slate max-w-none [&>ol]:my-2 [&>p]:mb-2 [&>p:last-child]:mb-0 [&>ul]:my-2"
                  dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(msg.content || '')) }}
                />
              ) : (
                <div className="flex items-center gap-2 py-1 text-slate-500">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
                  <span className="h-2 w-2 animate-pulse rounded-full bg-blue-400 [animation-delay:0.2s]" />
                  <span className="h-2 w-2 animate-pulse rounded-full bg-blue-300 [animation-delay:0.4s]" />
                  <span className="text-xs font-medium">Retrieving source-grounded answer</span>
                </div>
              )}
              {msg.citations?.length > 0 && (
                <div className="mt-3 rounded-lg bg-slate-50 p-2">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="text-[11px] font-semibold text-slate-500">Source confidence</span>
                    <span className="text-[11px] font-semibold text-slate-700">{quality.score}%</span>
                  </div>
                  <ProgressBar value={quality.score} tone={quality.tone} />
                </div>
              )}
              <Citations citations={msg.citations} />
              {msg.content && (
                <div className="mt-2 flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pt-2">
                  {msg.feedback_rating ? (
                    <StatusBadge tone={msg.feedback_rating === 'helpful' ? 'emerald' : 'amber'}>Feedback captured</StatusBadge>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 transition hover:text-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={feedbackPending}
                        onClick={() => onFeedback(msg, 'helpful', messageIndex)}
                      >
                        <ThumbsUp className="h-3.5 w-3.5" aria-hidden="true" />
                        Helpful
                      </button>
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 transition hover:text-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={feedbackPending}
                        onClick={() => onFeedback(msg, 'needs_review', messageIndex)}
                      >
                        <Flag className="h-3.5 w-3.5" aria-hidden="true" />
                        Needs review
                      </button>
                    </>
                  )}
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 transition hover:text-blue-700"
                    onClick={() => onCopy(msg.content)}
                  >
                    <Clipboard className="h-3.5 w-3.5" aria-hidden="true" />
                    Copy
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 transition hover:text-blue-700"
                    onClick={() => onExport(msg)}
                  >
                    <Download className="h-3.5 w-3.5" aria-hidden="true" />
                    Evidence pack
                  </button>
                </div>
              )}
            </>
          ) : (
            <>
              {msg.mode && <p className="mb-1 text-[11px] font-semibold text-blue-100">{msg.mode}</p>}
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </>
          )}
        </div>
      </div>
      {!isAssistant && (
        <div className="mt-1 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-blue-100 text-blue-700">
          <span className="text-xs font-bold">U</span>
        </div>
      )}
    </article>
  )
}

export default function ChatPage() {
  const { t } = useLang()
  const [collection, setCollection] = React.useState('HR-docs')
  const [question, setQuestion] = React.useState('')
  const [sessionId, setSessionId] = React.useState('')
  const [messages, setMessages] = React.useState([])
  const [activeMode, setActiveMode] = React.useState('answer')
  const [streamError, setStreamError] = React.useState(null)
  const [isStreaming, setIsStreaming] = React.useState(false)
  const queryClient = useQueryClient()
  const messagesEndRef = React.useRef(null)
  const inputRef = React.useRef(null)

  const collections = useQuery({ queryKey: ['collections'], queryFn: getCollections })
  const sessions = useQuery({ queryKey: ['chat-sessions'], queryFn: getChatSessions, refetchInterval: 10000 })
  const stats = useQuery({ queryKey: ['stats'], queryFn: getStats, refetchInterval: 15000 })
  const providers = useQuery({ queryKey: ['ai-providers'], queryFn: getAiProviders, refetchInterval: 30000 })

  const collectionNames = collections.data?.collections || ['HR-docs', 'Legal-docs', 'Technical-docs']
  const sessionList = sessions.data?.sessions || []
  const selectedMode = answerModes.find((mode) => mode.id === activeMode) || answerModes[0]
  const collectionStats = stats.data?.collections?.find((item) => item.name === collection)
  const providerData = providers.data || {}
  const displayedMessages = React.useMemo(() => {
    let lastQuestion = ''
    let lastMode = ''
    return messages.map((msg) => {
      if (msg.role === 'user') {
        lastQuestion = msg.content || ''
        lastMode = msg.mode || ''
        return msg
      }
      return { ...msg, question_context: msg.question_context || lastQuestion, mode_context: msg.mode_context || lastMode }
    })
  }, [messages])

  const handleSend = async () => {
    const cleanQuestion = question.trim()
    if (!cleanQuestion || isStreaming) return
    const outboundQuestion = selectedMode.instruction
      ? `${cleanQuestion}\n\nAnswer mode: ${selectedMode.instruction}`
      : cleanQuestion

    setIsStreaming(true)
    setStreamError(null)
    setMessages((prev) => [...prev, { role: 'user', content: cleanQuestion, mode: selectedMode.label }])
    setQuestion('')
    inputRef.current?.focus()
    const assistantIdx = { current: -1 }

    try {
      await sendChatStream(outboundQuestion, collection, sessionId, {
        onMetadata: (meta) => {
          if (meta.session_id && !sessionId) setSessionId(meta.session_id)
          setMessages((prev) => {
            assistantIdx.current = prev.length
            return [
              ...prev,
              { role: 'assistant', content: '', language: meta.language, citations: meta.citations, answer_quality: meta.answer_quality },
            ]
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
    onSuccess: (_, deletedSessionId) => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      if (sessionId === deletedSessionId) startNewChat()
    },
  })
  const feedbackMutation = useMutation({ mutationFn: sendChatFeedback })

  const startNewChat = () => {
    setSessionId('')
    setMessages([])
    setQuestion('')
    inputRef.current?.focus()
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    handleSend()
  }

  const copyText = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Clipboard can be blocked in some browser contexts; the answer remains selectable.
    }
  }

  const exportEvidencePack = (msg) => {
    const markdown = buildEvidencePack({ msg, question: msg.question_context, collection, sessionId })
    const url = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = evidenceFileName(collection, msg.question_context)
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  const submitFeedback = (msg, rating, messageIndex) => {
    setMessages((prev) => prev.map((item, idx) => (idx === messageIndex ? { ...item, feedback_rating: rating } : item)))
    feedbackMutation.mutate(
      {
        session_id: sessionId,
        collection: msg.collection || collection,
        question: msg.question_context || '',
        answer_excerpt: (msg.content || '').slice(0, 1500),
        rating,
        language: msg.language || 'en',
        citation_count: msg.citations?.length || 0,
        citations: msg.citations || [],
        answer_quality: msg.answer_quality || {},
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['analytics'] })
        },
        onError: () => {
          setMessages((prev) => prev.map((item, idx) => (idx === messageIndex ? { ...item, feedback_rating: '' } : item)))
        },
      },
    )
  }

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="grid h-full grid-cols-1 overflow-hidden bg-slate-100 xl:grid-cols-[18rem_minmax(0,1fr)] 2xl:grid-cols-[18rem_minmax(0,1fr)_21rem]">
      <aside className="hidden min-h-0 border-r border-slate-200 bg-white xl:flex xl:flex-col">
        <div className="border-b border-slate-200 p-4">
          <button
            type="button"
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-slate-950 px-3 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700"
            onClick={startNewChat}
          >
            <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
            {t('chat.newChat')}
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          <p className="mb-2 px-1 text-xs font-bold uppercase tracking-wide text-slate-400">{t('chat.history')}</p>
          {sessionList.length === 0 ? (
            <EmptyState
              icon={MessageSquarePlus}
              title={t('chat.noConversations')}
              body="Completed answers will appear here with collection and message counts."
              className="min-h-52"
            />
          ) : (
            <div className="space-y-1">
              {sessionList.map((s) => (
                <div
                  key={s.session_id}
                  className={cn(
                    'group flex w-full items-start gap-2 rounded-xl border p-3 text-left transition',
                    sessionId === s.session_id
                      ? 'border-blue-200 bg-blue-50 text-blue-800'
                      : 'border-transparent text-slate-600 hover:border-slate-200 hover:bg-slate-50',
                  )}
                >
                  <button type="button" className="min-w-0 flex-1 text-left" onClick={() => loadSession.mutate(s.session_id)}>
                    <span className="line-clamp-2 text-xs font-semibold leading-relaxed">{s.preview || 'Empty'}</span>
                    <span className="mt-2 block text-[11px] text-slate-400">
                      {s.collection} - {s.message_count} {t('chat.msgs')}
                    </span>
                  </button>
                  <IconButton
                    label="Delete session"
                    className="h-7 w-7 flex-shrink-0 text-slate-300 opacity-0 shadow-none hover:border-rose-200 hover:text-rose-600 group-hover:opacity-100"
                    onClick={() => deleteSession.mutate(s.session_id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  </IconButton>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      <section className="flex min-h-0 min-w-0 flex-col">
        <div className="border-b border-slate-200 bg-white px-4 py-4 sm:px-6">
          <div className="mx-auto flex max-w-5xl flex-col gap-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge tone="blue">
                    <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                    Source-grounded
                  </StatusBadge>
                  <StatusBadge tone="emerald">
                    <Languages className="h-3.5 w-3.5" aria-hidden="true" />
                    FI/SV/EN
                  </StatusBadge>
                  <StatusBadge tone="slate">
                    <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
                    Permission scoped
                  </StatusBadge>
                </div>
                <h1 className="mt-3 text-2xl font-bold text-slate-950">Enterprise answer workbench</h1>
                <p className="mt-1 text-sm text-slate-500">
                  Ask across governed collections, stream cited answers, and review source confidence before decisions move forward.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <select
                  className="min-w-48 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20"
                  value={collection}
                  onChange={(e) => setCollection(e.target.value)}
                  aria-label={t('admin.collection')}
                >
                  {collectionNames.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {answerModes.map((mode) => {
                const Icon = mode.icon
                const active = mode.id === activeMode
                return (
                  <button
                    key={mode.id}
                    type="button"
                    aria-pressed={active}
                    className={cn(
                      'flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition',
                      active ? 'border-blue-300 bg-blue-50 text-blue-800 shadow-sm' : 'border-slate-200 bg-white text-slate-600 hover:border-blue-200',
                    )}
                    onClick={() => setActiveMode(mode.id)}
                  >
                    <span className={cn('flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg', active ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-500')}>
                      <Icon className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-bold">{mode.label}</span>
                      <span className="block truncate text-xs opacity-70">{mode.helper}</span>
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6" role="log" aria-label="Chat messages" aria-live="polite">
          {messages.length === 0 ? (
            <div className="mx-auto grid max-w-5xl gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
              <Surface className="p-5">
                <div className="flex items-start gap-4">
                  <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white">
                    <Search className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-lg font-bold text-slate-950">{t('chat.title')}</h2>
                    <p className="mt-1 text-sm text-slate-500">
                      Start with a policy, customer, legal, HR, or technical question. The assistant answers only from retrieved context and shows citations.
                    </p>
                  </div>
                </div>
                <div className="mt-5 grid gap-2 sm:grid-cols-2">
                  {promptTemplates.map((template) => (
                    <button
                      key={template}
                      type="button"
                      className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-left text-sm font-medium text-slate-700 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-800"
                      onClick={() => {
                        setQuestion(template)
                        inputRef.current?.focus()
                      }}
                    >
                      {template}
                    </button>
                  ))}
                </div>
              </Surface>

              <Surface className="p-5">
                <h3 className="text-sm font-bold text-slate-950">Collection health</h3>
                <div className="mt-4 space-y-4">
                  <div>
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>{collection}</span>
                      <span>{collectionStats?.documents || 0} documents</span>
                    </div>
                    <ProgressBar value={Math.min(100, (collectionStats?.documents || 0) * 12)} tone="blue" className="mt-2" />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xl font-bold text-slate-950">{collectionStats?.chunks || 0}</p>
                      <p className="text-xs text-slate-500">indexed chunks</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xl font-bold text-slate-950">{stats.data?.total_documents || 0}</p>
                      <p className="text-xs text-slate-500">all docs</p>
                    </div>
                  </div>
                  <StatusBadge tone={collectionStats?.documents ? 'emerald' : 'amber'} className="w-full justify-center">
                    {collectionStats?.documents ? 'Ready for source-backed Q&A' : 'Upload evidence before asking'}
                  </StatusBadge>
                </div>
              </Surface>
            </div>
          ) : (
            <div className="mx-auto max-w-5xl space-y-6">
              {displayedMessages.map((msg, i) => (
                <MessageBubble
                  key={`${msg.role}-${i}`}
                  msg={msg}
                  messageIndex={i}
                  onCopy={copyText}
                  onExport={exportEvidencePack}
                  onFeedback={submitFeedback}
                  feedbackPending={feedbackMutation.isPending}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="flex-shrink-0 border-t border-slate-200 bg-white px-4 py-3 sm:px-6">
          <div className="mx-auto max-w-5xl">
            {streamError && <p className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">Error: {streamError}</p>}
            <form onSubmit={handleSubmit} className="flex items-end gap-2" aria-label="Chat input">
              <div className="min-w-0 flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-500/20">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <StatusBadge tone="slate">{selectedMode.label}</StatusBadge>
                  <span className="text-xs text-slate-400">{collection}</span>
                </div>
                <textarea
                  ref={inputRef}
                  className="max-h-36 min-h-12 w-full resize-none bg-transparent text-sm text-slate-800 outline-none placeholder:text-slate-400"
                  placeholder={t('chat.placeholder')}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  disabled={isStreaming}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                />
              </div>
              <IconButton
                label={isStreaming ? 'Streaming answer' : t('chat.send')}
                className="h-12 w-12 border-blue-200 bg-blue-600 text-white hover:bg-blue-700 hover:text-white"
                disabled={isStreaming || !question.trim()}
                onClick={handleSend}
              >
                <ArrowUp className="h-5 w-5" aria-hidden="true" />
              </IconButton>
            </form>
          </div>
        </div>
      </section>

      <aside className="hidden min-h-0 overflow-y-auto border-l border-slate-200 bg-white p-4 2xl:block">
        <div className="space-y-4">
          <Surface className="p-4">
            <h3 className="text-sm font-bold text-slate-950">Trust stack</h3>
            <div className="mt-3 space-y-3">
              {[
                ['Source citations', 'Visible on every supported answer', 'emerald'],
                ['RBAC collections', 'Backend enforces user collection access', 'emerald'],
                ['Quota controls', 'Monthly usage guardrails are available', 'blue'],
                ['EU/on-prem path', 'Docker, TLS, and air-gapped runbooks', 'violet'],
              ].map(([title, detail, tone]) => (
                <div key={title} className="flex items-start gap-3 rounded-lg bg-slate-50 p-3">
                  <CheckCircle2 className={cn('mt-0.5 h-4 w-4 flex-shrink-0', tone === 'emerald' ? 'text-emerald-600' : tone === 'violet' ? 'text-violet-600' : 'text-blue-600')} aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-800">{title}</p>
                    <p className="text-xs text-slate-500">{detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </Surface>

          <Surface className="p-4">
            <h3 className="text-sm font-bold text-slate-950">Provider posture</h3>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between gap-3 border-b border-slate-100 pb-2">
                <span className="text-slate-500">LLM</span>
                <span className="truncate font-semibold text-slate-800">{providerData.llm_provider || 'not configured'}</span>
              </div>
              <div className="flex justify-between gap-3 border-b border-slate-100 pb-2">
                <span className="text-slate-500">Embeddings</span>
                <span className="truncate font-semibold text-slate-800">{providerData.embedding_provider || 'not configured'}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-slate-500">Sovereignty</span>
                <span className="font-semibold text-slate-800">{providerData.data_sovereignty_mode ? 'local mode' : 'hybrid mode'}</span>
              </div>
            </div>
          </Surface>

          <Surface className="p-4">
            <h3 className="text-sm font-bold text-slate-950">Competitive edge</h3>
            <div className="mt-3 space-y-2">
              {[
                'Finnish compound-aware retrieval',
                'Vendor-neutral deployment',
                'Open-source pgvector stack',
                'Admin-visible governance',
              ].map((item) => (
                <div key={item} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700">
                  {item}
                </div>
              ))}
            </div>
          </Surface>
        </div>
      </aside>
    </div>
  )
}
