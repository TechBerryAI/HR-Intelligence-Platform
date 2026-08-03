import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'

export async function scheduleInterview(payload) {
  const token = tokenService.getToken()
  return apiRequest('/api/head-hr/interviews', {
    method: 'POST',
    token,
    body: payload,
  })
}

export async function listInterviews() {
  const token = tokenService.getToken()
  return apiRequest('/api/head-hr/interviews', { method: 'GET', token })
}

export async function listApplicationInterviews(applicationId) {
  const token = tokenService.getToken()
  return apiRequest(`/api/head-hr/applications/${applicationId}/interviews`, {
    method: 'GET',
    token,
  })
}

export async function getInterview(interviewId) {
  const token = tokenService.getToken()
  return apiRequest(`/api/head-hr/interviews/${interviewId}`, { method: 'GET', token })
}

export async function cancelInterview(interviewId) {
  const token = tokenService.getToken()
  return apiRequest(`/api/head-hr/interviews/${interviewId}/cancel`, {
    method: 'POST',
    token,
  })
}

export async function getPublicSession(inviteToken) {
  return apiRequest(`/api/interviews/session/${encodeURIComponent(inviteToken)}`, {
    method: 'GET',
  })
}

export async function startPublicSession(inviteToken) {
  return apiRequest(`/api/interviews/session/${encodeURIComponent(inviteToken)}/start`, {
    method: 'POST',
  })
}

export async function submitPublicAnswer(inviteToken, answer) {
  return apiRequest(`/api/interviews/session/${encodeURIComponent(inviteToken)}/answer`, {
    method: 'POST',
    body: { answer },
  })
}

export async function completePublicSession(inviteToken) {
  return apiRequest(`/api/interviews/session/${encodeURIComponent(inviteToken)}/complete`, {
    method: 'POST',
  })
}
