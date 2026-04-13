const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function fetchJSON(path, options = {}) {
  const res = await fetch(`${API}${path}`, options)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `Request failed: ${res.status}`)
  }
  return res.json()
}

export function getCollections() {
  return fetchJSON('/admin/collections')
}

export function getJobs() {
  return fetchJSON('/admin/jobs')
}

export function uploadDocument(formData) {
  return fetchJSON('/admin/upload', { method: 'POST', body: formData })
}

export function sendChat(question, collection, sessionId = '') {
  return fetchJSON('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, collection, session_id: sessionId }),
  })
}

export async function sendChatStream(question, collection, sessionId, { onMetadata, onToken, onDone, onError }) {
  try {
    const res = await fetch(`${API}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, collection, session_id: sessionId }),
    })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(text || `Request failed: ${res.status}`)
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE format: blocks separated by blank lines, each block has event: and data: lines
      const blocks = buffer.split(/\r?\n\r?\n/)
      buffer = blocks.pop() || '' // keep last incomplete block in buffer

      for (const block of blocks) {
        if (!block.trim()) continue
        let event = ''
        let data = ''
        for (const raw of block.split(/\r?\n/)) {
          const line = raw.trim()
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) data = line.slice(5).trimStart()
        }
        if (event === 'metadata' && onMetadata) onMetadata(JSON.parse(data))
        else if (event === 'token' && onToken) onToken(data)
        else if (event === 'done' && onDone) onDone()
      }
    }
    // If stream ends without a done event, ensure we clean up
    if (buffer.trim()) {
      let event = ''
      let data = ''
      for (const raw of buffer.split(/\r?\n/)) {
        const line = raw.trim()
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data = line.slice(5).trimStart()
      }
      if (event === 'done' && onDone) onDone()
      else if (event === 'token' && onToken) onToken(data)
    }
  } catch (err) {
    if (onError) onError(err)
  }
}

export function getDocuments(collection) {
  return fetchJSON(`/admin/documents?collection=${encodeURIComponent(collection)}`)
}

export function deleteDocument(documentName, collection) {
  return fetchJSON(`/admin/documents/${encodeURIComponent(documentName)}?collection=${encodeURIComponent(collection)}`, {
    method: 'DELETE',
  })
}

export function getDocumentChunks(documentName, collection, page = 1) {
  return fetchJSON(
    `/admin/documents/${encodeURIComponent(documentName)}/chunks?collection=${encodeURIComponent(collection)}&page=${page}`
  )
}

export function getStats() {
  return fetchJSON('/admin/stats')
}

export function getAnalytics() {
  return fetchJSON('/admin/analytics')
}

export function createCollection(name, description = '') {
  return fetchJSON('/admin/collections', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  })
}

export function deleteCollection(name) {
  return fetchJSON(`/admin/collections/${encodeURIComponent(name)}`, { method: 'DELETE' })
}

export function getChatSessions() {
  return fetchJSON('/chat/sessions')
}

export function getChatHistory(sessionId) {
  return fetchJSON(`/chat/history/${encodeURIComponent(sessionId)}`)
}

export function deleteChatSession(sessionId) {
  return fetchJSON(`/chat/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
}
