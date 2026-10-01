import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { csrfHeaders } from './api.js'
import { uploadAndParseJDStream, uploadAndParseResumeStream } from './parsingApi.js'
import { tokenService } from '@/core/auth/tokenService.js'

function setCookie(value) {
  document.cookie = `csrf_token=${value}; path=/`
}

function clearCookie() {
  document.cookie = 'csrf_token=; path=/; max-age=0'
}

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function sseResponse(result) {
  const text = `event: result\ndata: ${JSON.stringify(result)}\n\n`
  return new Response(text, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

const OK_RESULT = { status: 'ok', form: { title: 'Engineer' } }

describe('CSRF on authenticated parse uploads', () => {
  let fetchMock

  beforeEach(() => {
    tokenService.clear()
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    clearCookie()
    vi.unstubAllGlobals()
  })

  it('csrfHeaders echoes the csrf cookie', () => {
    setCookie('tok-123')
    expect(csrfHeaders()).toEqual({ 'X-CSRF-Token': 'tok-123' })
    clearCookie()
    expect(csrfHeaders()).toEqual({})
  })

  it.each([
    ['JD', () => uploadAndParseJDStream(new File(['x'], 'jd.pdf')), '/api/parse/jd/stream'],
    ['resume', () => uploadAndParseResumeStream(new File(['x'], 'cv.pdf')), '/api/parse/resume/stream'],
  ])('%s stream sends X-CSRF-Token and cookies', async (_label, run, path) => {
    setCookie('tok-abc')
    fetchMock.mockResolvedValue(sseResponse(OK_RESULT))

    await expect(run()).resolves.toEqual(OK_RESULT)

    const [url, opts] = fetchMock.mock.calls.find(([u]) => String(u).endsWith(path))
    expect(String(url)).toContain(path)
    expect(opts.credentials).toBe('include')
    expect(opts.headers['X-CSRF-Token']).toBe('tok-abc')
    expect(opts.headers.Authorization).toBeUndefined()
  })

  it('falls back to the JSON route when the stream is rejected with CSRF 403', async () => {
    setCookie('tok-abc')
    fetchMock.mockImplementation(async (url) => {
      const u = String(url)
      if (u.endsWith('/api/parse/jd/stream')) {
        return jsonResponse(403, { error: 'CSRF validation failed' })
      }
      if (u.endsWith('/api/parse/jd')) return jsonResponse(200, OK_RESULT)
      return jsonResponse(404, {})
    })

    await expect(uploadAndParseJDStream(new File(['x'], 'jd.pdf'))).resolves.toEqual(OK_RESULT)
    expect(fetchMock.mock.calls.some(([u]) => String(u).endsWith('/api/parse/jd'))).toBe(true)
  })

  it('re-issues a missing csrf cookie via /api/refresh before retrying', async () => {
    let jdCalls = 0
    fetchMock.mockImplementation(async (url, opts) => {
      const u = String(url)
      if (u.endsWith('/api/refresh')) {
        setCookie('fresh-tok')
        return jsonResponse(200, {})
      }
      if (u.endsWith('/api/parse/jd')) {
        jdCalls += 1
        const sent = opts.headers.get('X-CSRF-Token')
        return sent === 'fresh-tok'
          ? jsonResponse(200, OK_RESULT)
          : jsonResponse(403, { error: 'CSRF validation failed' })
      }
      if (u.endsWith('/api/parse/jd/stream')) {
        return jsonResponse(403, { error: 'CSRF validation failed' })
      }
      return jsonResponse(404, {})
    })

    await expect(uploadAndParseJDStream(new File(['x'], 'jd.pdf'))).resolves.toEqual(OK_RESULT)
    expect(fetchMock.mock.calls.some(([u]) => String(u).endsWith('/api/refresh'))).toBe(true)
    expect(jdCalls).toBe(2)
  })
})
