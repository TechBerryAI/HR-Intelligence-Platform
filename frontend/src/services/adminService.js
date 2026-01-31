/**
 * Admin API - job matches (ATS results per job), uses backend /api/admin and /api/jobs.
 */
import { apiRequest } from '../utils/api.js'

/** List jobs with application and shortlisted counts (admin). */
export async function getJobMatches() {
  return apiRequest('/api/admin/job-matches')
}

/** Get applications for a job with ATS scores (admin). Uses existing jobs API. */
export async function getJobApplications(jobId) {
  return apiRequest(`/api/jobs/${jobId}/applications`)
}
