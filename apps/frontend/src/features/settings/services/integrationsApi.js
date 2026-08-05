import { apiRequest } from '@/core/api/api.js'
import { tokenService } from '@/core/auth/tokenService.js'

function token() {
  return tokenService.getToken()
}

export async function fetchIntegrationProviders() {
  return apiRequest('/api/integrations/providers', { method: 'GET', token: token() })
}

export async function fetchProviderConfig(provider) {
  return apiRequest(`/api/integrations/provider/${provider}`, { method: 'GET', token: token() })
}

export async function saveProviderConfig(provider, body) {
  return apiRequest(`/api/integrations/provider/${provider}`, {
    method: 'PUT',
    token: token(),
    body,
  })
}

export async function createProviderConfig(body) {
  return apiRequest('/api/integrations/provider', {
    method: 'POST',
    token: token(),
    body,
  })
}

export async function deleteProviderConfig(providerOrId) {
  return apiRequest(`/api/integrations/provider/${providerOrId}`, {
    method: 'DELETE',
    token: token(),
  })
}

export async function syncProvider(provider) {
  return apiRequest(`/api/integrations/provider/${provider}/sync`, {
    method: 'POST',
    token: token(),
  })
}

export async function fetchExternalApplications(params = {}) {
  const q = new URLSearchParams()
  if (params.provider) q.set('provider', params.provider)
  if (params.jobId) q.set('jobId', params.jobId)
  if (params.limit) q.set('limit', String(params.limit))
  const qs = q.toString()
  return apiRequest(`/api/integrations/applications${qs ? `?${qs}` : ''}`, {
    method: 'GET',
    token: token(),
  })
}

export async function connectProvider(provider, body = {}) {
  return apiRequest(`/api/integrations/provider/${provider}/connect`, {
    method: 'POST',
    token: token(),
    body,
  })
}

export async function disconnectProvider(provider) {
  return apiRequest(`/api/integrations/provider/${provider}/disconnect`, {
    method: 'POST',
    token: token(),
  })
}

export async function testProviderConnection(provider) {
  return apiRequest(`/api/integrations/provider/${provider}/test`, {
    method: 'POST',
    token: token(),
  })
}

export async function publishJobToProviders(jobId, providers) {
  return apiRequest(`/api/integrations/publish/${jobId}`, {
    method: 'POST',
    token: token(),
    body: providers ? { providers } : {},
  })
}

export async function republishJob(jobId, providers) {
  return apiRequest(`/api/integrations/republish/${jobId}`, {
    method: 'POST',
    token: token(),
    body: providers ? { providers } : {},
  })
}

export async function retryExternalJob(externalJobId) {
  return apiRequest(`/api/integrations/retry/${externalJobId}`, {
    method: 'POST',
    token: token(),
  })
}

export async function fetchExternalJobs(jobId) {
  const q = jobId ? `?jobId=${encodeURIComponent(jobId)}` : ''
  return apiRequest(`/api/integrations/jobs${q}`, { method: 'GET', token: token() })
}

export async function fetchIntegrationLogs(limit = 50) {
  return apiRequest(`/api/integrations/logs?limit=${limit}`, { method: 'GET', token: token() })
}

export async function fetchIntegrationStatus() {
  return apiRequest('/api/integrations/status', { method: 'GET', token: token() })
}

export async function fetchIntegrationDashboard() {
  return apiRequest('/api/integrations/dashboard', { method: 'GET', token: token() })
}
