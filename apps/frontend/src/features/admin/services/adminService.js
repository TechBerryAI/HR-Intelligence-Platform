/**
 * Admin API - uses backend /api/jobs for candidates per job.
 */
import { apiRequest } from '@/core/api/api.js'

/** Get applications for a job with ATS scores (admin). Uses existing jobs API. */
export async function getJobApplications(jobId) {
  return apiRequest(`/api/jobs/${jobId}/applications`)
}
