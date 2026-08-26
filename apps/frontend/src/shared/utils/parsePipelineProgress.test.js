import { describe, expect, it } from 'vitest'
import {
  hintForStage,
  isPipelineComplete,
  overlayCatchupMs,
  overlayStepIndex,
  progressPctForStage,
} from './parsePipelineProgress.js'

describe('parse pipeline overlay mapping', () => {
  it('maps resume engine stages onto the four overlay steps', () => {
    expect(overlayStepIndex('resume', 'text')).toBe(0)
    expect(overlayStepIndex('resume', 'layout')).toBe(0)
    expect(overlayStepIndex('resume', 'sections')).toBe(1)
    expect(overlayStepIndex('resume', 'deterministic')).toBe(1)
    expect(overlayStepIndex('resume', 'coverage')).toBe(2)
    expect(overlayStepIndex('resume', 'semantic')).toBe(2)
    expect(overlayStepIndex('resume', 'knowledge')).toBe(2)
    expect(overlayStepIndex('resume', 'validate')).toBe(3)
    expect(overlayStepIndex('resume', 'persist')).toBe(3)
  })

  it('maps JD engine stages onto the four overlay steps', () => {
    expect(overlayStepIndex('jd', 'text')).toBe(0)
    expect(overlayStepIndex('jd', 'sections')).toBe(1)
    expect(overlayStepIndex('jd', 'knowledge')).toBe(2)
    expect(overlayStepIndex('jd', 'coverage')).toBe(2)
    expect(overlayStepIndex('jd', 'persist')).toBe(3)
  })

  it('advances resume progress in pipeline order (text before layout)', () => {
    const textPct = progressPctForStage('resume', 'text')
    const layoutPct = progressPctForStage('resume', 'layout')
    const sectionsPct = progressPctForStage('resume', 'sections')
    expect(textPct).toBeGreaterThan(progressPctForStage('resume', 'persist_raw'))
    expect(layoutPct).toBeGreaterThan(textPct)
    expect(sectionsPct).toBeGreaterThan(layoutPct)
    expect(progressPctForStage('resume', 'persist')).toBe(100)
  })

  it('does not drop coverage from the live overlay', () => {
    expect(overlayStepIndex('resume', 'coverage')).toBeGreaterThanOrEqual(0)
    expect(progressPctForStage('resume', 'coverage')).toBeGreaterThan(
      progressPctForStage('resume', 'deterministic'),
    )
  })

  it('holds the overlay long enough for skipped steps to catch up', () => {
    expect(overlayCatchupMs('resume', 'persist')).toBe(500)
    expect(overlayCatchupMs('resume', 'text')).toBeGreaterThan(overlayCatchupMs('resume', 'persist'))
    expect(overlayCatchupMs('resume', 'sections')).toBeGreaterThan(500)
  })

  it('prefers engine messages and flags persist completion', () => {
    expect(hintForStage('text', 'Extracted 1200 chars')).toBe('Extracted 1200 chars')
    expect(hintForStage('semantic', '')).toBe('Understanding content')
    expect(isPipelineComplete({ stage: 'persist', status: 'completed' })).toBe(true)
    expect(isPipelineComplete({ stage: 'persist', status: 'started' })).toBe(false)
  })
})
