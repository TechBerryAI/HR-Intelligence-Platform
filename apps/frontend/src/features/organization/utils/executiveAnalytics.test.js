import { describe, expect, it } from 'vitest'
import {
  classifyVerdict,
  computeExecutiveAnalytics,
  normalizePipelineStatus,
  outcomeBucket,
} from './executiveAnalytics.js'

describe('executive analytics bucketing', () => {
  it('keeps Applied apps as not shortlisted, not rejected', () => {
    const apps = [
      { id: 1, status: 'Shortlisted', shortlisted: true, job_id: 'j1', match_score: 82, verdict: 'Strong Match' },
      ...Array.from({ length: 8 }, (_, i) => ({
        id: i + 2,
        status: 'Applied',
        shortlisted: false,
        job_id: 'j1',
        match_score: 22,
        verdict: 'Not a Match',
      })),
    ]
    const analytics = computeExecutiveAnalytics(apps, [{ jdid: 'j1', title: 'Engineer' }])
    expect(analytics.total).toBe(9)
    expect(analytics.byOutcome.shortlisted).toBe(1)
    expect(analytics.byOutcome.notShortlisted).toBe(8)
    expect(analytics.byOutcome.rejected).toBe(0)
    expect(analytics.shortlistRate).toBe(11)
    expect(analytics.topJobs[0].conversion).toBe(11)
    expect(analytics.topJobs[0].notShortlisted).toBe(8)
  })

  it('maps Screening and profile_viewed, not Applied', () => {
    expect(normalizePipelineStatus({ status: 'Screening' })).toBe('screening')
    expect(normalizePipelineStatus({ status: 'profile_viewed' })).toBe('screening')
    expect(outcomeBucket({ status: 'Screening', shortlisted: false })).toBe('notShortlisted')
  })

  it('counts Interview / Offer / Hired as shortlisted outcome', () => {
    expect(outcomeBucket({ status: 'Interview', shortlisted: true })).toBe('shortlisted')
    expect(outcomeBucket({ status: 'Offer', shortlisted: false })).toBe('shortlisted')
    expect(outcomeBucket({ status: 'Hired' })).toBe('shortlisted')
    expect(normalizePipelineStatus({ status: 'Interview' })).toBe('interview')
  })

  it('keeps explicit Rejected separate from not shortlisted', () => {
    expect(outcomeBucket({ status: 'Rejected', shortlisted: false })).toBe('rejected')
    expect(outcomeBucket({ status: 'not_shortlisted' })).toBe('rejected')
    const analytics = computeExecutiveAnalytics([
      { status: 'Rejected', shortlisted: false, job_id: 'j1' },
      { status: 'Applied', shortlisted: false, job_id: 'j1' },
    ])
    expect(analytics.byOutcome.rejected).toBe(1)
    expect(analytics.byOutcome.notShortlisted).toBe(1)
  })

  it('classifies ATS verdicts, with score fallback', () => {
    expect(classifyVerdict({ verdict: 'Strong Match' })).toBe('strong')
    expect(classifyVerdict({ verdict: 'Potential Match (Recruiter Review)' })).toBe('potential')
    expect(classifyVerdict({ verdict: 'Not a Match' })).toBe('notMatch')
    expect(classifyVerdict({ match_score: 81 })).toBe('strong')
    expect(classifyVerdict({ match_score: 45 })).toBe('potential')
    expect(classifyVerdict({ match_score: 10 })).toBe('notMatch')
    expect(classifyVerdict({})).toBe('unknown')
  })
})
