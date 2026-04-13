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
