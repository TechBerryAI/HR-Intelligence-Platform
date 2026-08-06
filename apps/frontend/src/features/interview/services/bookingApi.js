import { BASE_URL } from '@/core/api/api.js'

function join(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  if (!BASE_URL) return p
  return `${BASE_URL}${p}`
}

async function publicJson(path, options = {}) {
  const res = await fetch(join(path), {
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
    ...options,
  })
  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  if (!res.ok) {
    const err = new Error((data && data.error) || res.statusText || 'Request failed')
    err.status = res.status
    err.data = data
    throw err
  }
  return data
}

export function fetchBooking(token) {
  return publicJson(`/api/interviews/book/${encodeURIComponent(token)}`)
}

export function bookSlot(token, slotId) {
  return publicJson(`/api/interviews/book/${encodeURIComponent(token)}`, {
    method: 'POST',
    body: JSON.stringify({ slotId }),
  })
}
