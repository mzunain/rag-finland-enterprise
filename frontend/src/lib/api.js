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

export function sendChat(question, collection) {
  return fetchJSON('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, collection }),
  })
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
