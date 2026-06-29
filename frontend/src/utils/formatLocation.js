/** Format candidate location from string, object, or legacy dict-like text. */
export function formatLocation(value) {
  if (value == null || value === '') return '—'
  if (typeof value === 'object') {
    return [value.city, value.state, value.country].filter(Boolean).join(', ') || '—'
  }
  const text = String(value).trim()
  if (!text) return '—'
  if (text.startsWith('{') && text.includes('city')) {
    try {
      const parsed = JSON.parse(text.replace(/'/g, '"'))
      if (parsed && typeof parsed === 'object') {
        return [parsed.city, parsed.state, parsed.country].filter(Boolean).join(', ') || text
      }
    } catch {
      // fall through
    }
  }
  return text
}
