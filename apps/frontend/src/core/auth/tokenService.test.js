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

  it('setToken / getToken round-trip via localStorage', () => {
    tokenService.setToken('access-abc')
    expect(tokenService.getToken()).toBe('access-abc')
    expect(window.localStorage.getItem('jwtToken')).toBe('access-abc')
  })

  it('clear removes access and refresh tokens', () => {
    tokenService.setToken('access-abc')
    tokenService.setRefreshToken('refresh-xyz')
    tokenService.clear()
    expect(tokenService.getToken()).toBe('')
    expect(tokenService.getRefreshToken()).toBe('')
    expect(window.localStorage.getItem('jwtToken')).toBe(null)
    expect(window.localStorage.getItem('refreshToken')).toBe(null)
  })
})
