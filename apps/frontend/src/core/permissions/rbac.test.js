import { describe, expect, it } from 'vitest'
import {
  ROLES,
  getRole,
  isStaff,
  isHeadHr,
  isRecruiter,
  isCeo,
  isStaffRecruiter,
} from './rbac.js'

describe('rbac helpers', () => {
  it('isStaff is true for recruiter, head HR, and CEO', () => {
    expect(isStaff({ isLoggedIn: true, role: ROLES.RECRUITER })).toBe(true)
    expect(isStaff({ isLoggedIn: true, role: ROLES.HEAD_HR })).toBe(true)
    expect(isStaff({ isLoggedIn: true, role: ROLES.CEO })).toBe(true)
  })

  it('isStaff / getRole reject guests and unknown roles', () => {
    expect(isStaff({ isLoggedIn: false, role: ROLES.RECRUITER })).toBe(false)
    expect(isStaff({ isLoggedIn: true, role: 'CANDIDATE' })).toBe(false)
    expect(getRole({ isLoggedIn: true, role: 'CANDIDATE' })).toBe(null)
    expect(getRole(null)).toBe(null)
  })

  it('role-specific helpers match expected roles', () => {
    const head = { isLoggedIn: true, role: ROLES.HEAD_HR }
    const recruiter = { isLoggedIn: true, role: ROLES.RECRUITER }
    const ceo = { isLoggedIn: true, role: ROLES.CEO }

    expect(isHeadHr(head)).toBe(true)
    expect(isRecruiter(recruiter)).toBe(true)
    expect(isCeo(ceo)).toBe(true)
    expect(isStaffRecruiter(recruiter)).toBe(true)
    expect(isStaffRecruiter(ceo)).toBe(false)
  })
})
