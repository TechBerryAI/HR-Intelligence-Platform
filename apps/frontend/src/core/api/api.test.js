import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiRequest, isSessionAuthError, setUnauthorizedHandler } from './api.js'
import { tokenService } from '@/core/auth/tokenService.js'

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('isSessionAuthError', () => {
  it.each([
    [401, 'Invalid or expired token'],
    [401, 'Access token required'],
    [401, 'Refresh token revoked'],
    [401, 'UNAUTHORIZED'],
    [403, 'Invalid or expired token'],
    [403, 'Account inactive or not found'],
  ])('%i %s is a dead session', (status, message) => {
    expect(isSessionAuthError(status, message)).toBe(true)
  })

  it.each([
    [403, 'Job not found or you do not have permission to update this job'],
    [403, 'Job not found or you do not have permission to delete this job'],
    [403, 'Access denied'],
    [403, 'Forbidden'],
    [403, 'Read-only access'],
    [403, 'Recruiter access required'],
    [403, 'CSRF validation failed'],
    [401, 'Current password is incorrect'],
    [401, 'Invalid email or password'],
    [404, 'Job not found'],
  ])('%i %s is NOT a dead session', (status, message) => {
    expect(isSessionAuthError(status, message)).toBe(false)
  })
})

describe('apiRequest logout behaviour', () => {
  let fetchMock
  let onUnauthorized

  beforeEach(() => {
    tokenService.clear()
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
  })

  afterEach(() => {
    setUnauthorizedHandler(null)
    vi.unstubAllGlobals()
  })

  it('a permission 403 on a job toggle surfaces as an error and does not log out', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(403, { error: 'Job not found or you do not have permission to update this job' })
    )
    await expect(
      apiRequest('/api/jobs/J1/enabled', { method: 'PATCH', body: { enabled: false } })
    ).rejects.toMatchObject({ status: 403 })
    expect(onUnauthorized).not.toHaveBeenCalled()
    expect(fetchMock.mock.calls.some(([u]) => String(u).endsWith('/api/refresh'))).toBe(false)
  })

  it('retries after another tab already rotated the refresh token', async () => {
    let jobCalls = 0
    fetchMock.mockImplementation(async (url) => {
      if (String(url).endsWith('/api/refresh')) {
        return jsonResponse(401, { error: 'Refresh token revoked' })
      }
      jobCalls += 1
      // First call: stale access cookie. Retry: the other tab's fresh cookie is in the jar.
      return jobCalls === 1
        ? jsonResponse(401, { error: 'Invalid or expired token' })
        : jsonResponse(200, { ok: true })
    })
    await expect(apiRequest('/api/jobs/all', { skipRetry: true })).resolves.toEqual({ ok: true })
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('a genuinely dead session still logs out', async () => {
    fetchMock.mockImplementation(async (url) =>
      String(url).endsWith('/api/refresh')
        ? jsonResponse(401, { error: 'Refresh token expired' })
        : jsonResponse(401, { error: 'Invalid or expired token' })
    )
    await expect(apiRequest('/api/jobs/all', { skipRetry: true })).rejects.toMatchObject({ status: 401 })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })
})
