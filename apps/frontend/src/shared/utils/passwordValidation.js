/**
 * Password strength rules (must match backend utils.validate_password_strength).
 * Min 8 chars, at least one: uppercase, lowercase, digit, special character.
 */
export const PASSWORD_MIN_LENGTH = 8

export const PASSWORD_RULES = [
  { id: 'length', label: `At least ${PASSWORD_MIN_LENGTH} characters`, test: (p) => p && p.length >= PASSWORD_MIN_LENGTH },
  { id: 'uppercase', label: 'One uppercase letter (A-Z)', test: (p) => /[A-Z]/.test(p || '') },
  { id: 'lowercase', label: 'One lowercase letter (a-z)', test: (p) => /[a-z]/.test(p || '') },
  { id: 'number', label: 'One number (0-9)', test: (p) => /\d/.test(p || '') },
  { id: 'special', label: 'One special character (!@#$%^&* etc.)', test: (p) => /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?`~]/.test(p || '') },
]

/**
 * Returns { valid: boolean, failedRules: string[] }
 */
export function validatePassword(password) {
  const failedRules = PASSWORD_RULES.filter((r) => !r.test(password)).map((r) => r.label)
  return { valid: failedRules.length === 0, failedRules }
}

/**
 * Returns true only if password meets all rules.
 */
export function isPasswordStrong(password) {
  return validatePassword(password).valid
}
