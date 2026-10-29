import { describe, expect, it } from 'vitest'
import type { RunTimeline } from '../api/types'
import { clock, etaMs, timelineRows } from './WritingTimeline'

const step = (stage: string) => ({ stage, attempt: 1, status: 'OK', duration_ms: 1000, created_at: '' })

describe('writing timeline', () => {
  it('marks a step that goes back after the editor as a revision', () => {
    const t = { steps: ['BRIEF', 'STORY', 'SHOTLIST', 'PROMPTS', 'EDIT_REVIEW', 'SHOTLIST'].map(step) } as RunTimeline
    expect(timelineRows(t).map((r) => r.revision)).toEqual([false, false, false, false, false, true])
  })

  it('estimates the rest from typical stage lengths', () => {
    const t = { stage: 'PROMPTS', typical_ms: { PROMPTS: 100_000, EDIT_REVIEW: 50_000 } } as unknown as RunTimeline
    expect(etaMs(t, 40_000)).toBe(110_000)
    expect(clock(83_000)).toBe('1:23')
  })
})
