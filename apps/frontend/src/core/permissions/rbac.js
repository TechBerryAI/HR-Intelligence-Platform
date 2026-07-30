/**
 * Centralized RBAC — mirrors backend/rbac.py
 */

export const ROLES = {
  CEO: 'CEO',
  HEAD_HR: 'HEAD_HR',
  RECRUITER: 'RECRUITER',
}

const PERMISSIONS = {
  'analytics:read': new Set([ROLES.CEO, ROLES.HEAD_HR]),
  'jobs:read_all': new Set([ROLES.CEO, ROLES.HEAD_HR]),
  'jobs:read_own': new Set([ROLES.RECRUITER, ROLES.HEAD_HR, ROLES.CEO]),
  'jobs:write_own': new Set([ROLES.RECRUITER, ROLES.HEAD_HR]),
  'jobs:write_any': new Set([ROLES.HEAD_HR]),
  'candidates:read_all': new Set([ROLES.CEO, ROLES.HEAD_HR]),
  'candidates:read_own': new Set([ROLES.RECRUITER, ROLES.HEAD_HR, ROLES.CEO]),
  'candidates:act_own': new Set([ROLES.RECRUITER, ROLES.HEAD_HR]),
  'candidates:act_any': new Set([ROLES.HEAD_HR]),
  'hr_users:manage': new Set([ROLES.HEAD_HR]),
  'bulk_parse:run': new Set([ROLES.RECRUITER, ROLES.HEAD_HR]),
  'bulk_parse:read_all': new Set([ROLES.CEO, ROLES.HEAD_HR]),
  'bulk_parse:read_own': new Set([ROLES.RECRUITER, ROLES.HEAD_HR, ROLES.CEO]),
  'settings:configure': new Set([ROLES.HEAD_HR]),
}

export function getRole(auth) {
  if (!auth?.isLoggedIn) return null
  const role = auth.role
  return Object.values(ROLES).includes(role) ? role : null
}

export function isHeadHr(auth) {
  return getRole(auth) === ROLES.HEAD_HR
}

export function isRecruiter(auth) {
  return getRole(auth) === ROLES.RECRUITER
}

export function isStaffRecruiter(auth) {
  const role = getRole(auth)
  return role === ROLES.RECRUITER || role === ROLES.HEAD_HR
}

export function isCeo(auth) {
  return getRole(auth) === ROLES.CEO
}
