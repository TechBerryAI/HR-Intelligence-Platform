import { beforeEach, describe, expect, it } from 'vitest'
import { tokenService } from './tokenService.js'

describe('tokenService', () => {
  beforeEach(() => {
    tokenService.clear()
    window.localStorage.clear()
  })

  it('getToken returns empty string when unset', () => {
    expect(tokenService.getToken()).toBe('')
    expect(tokenService.getRefreshToken()).toBe('')
  })

  it('setToken / getToken round-trip via the in-memory cache', () => {
    tokenService.setToken('access-abc')
    expect(tokenService.getToken()).toBe('access-abc')
  })

  it('never writes the token to localStorage (auth is cookie-based on the web)', () => {
    tokenService.setToken('access-abc')
    tokenService.setRefreshToken('refresh-xyz')
    expect(window.localStorage.getItem('jwtToken')).toBe(null)
    expect(window.localStorage.getItem('refreshToken')).toBe(null)
  })

  it('clear removes access and refresh tokens', () => {
    tokenService.setToken('access-abc')
    tokenService.setRefreshToken('refresh-xyz')
    tokenService.clear()
    expect(tokenService.getToken()).toBe('')
    expect(tokenService.getRefreshToken()).toBe('')
  })

  it('purges any legacy localStorage tokens from before the cookie migration', async () => {
    window.localStorage.setItem('jwtToken', 'stale-access')
    window.localStorage.setItem('refreshToken', 'stale-refresh')
    await tokenService.initTokenService()
    expect(window.localStorage.getItem('jwtToken')).toBe(null)
    expect(window.localStorage.getItem('refreshToken')).toBe(null)
  })
})
