import { describe, expect, it } from 'vitest'
import { mergeStale, staleFor } from './invalidation'

const ev = (type: string, data: Record<string, unknown> = {}) => ({ type, data })

describe('staleFor', () => {
  it('a worker tick refreshes nothing', () => {
    expect(staleFor(ev('worker_tick', { active: 0, pending: 0 }))).toBeNull()
  })

  it('a request update refreshes only its own film', () => {
    const p = staleFor(ev('request_update', { project_id: 'A', status: 'COMPLETED' }))!
    expect(p(['p', 'A', 'requests'])).toBe(true)
    expect(p(['p', 'A', 'scenes', 'v1'])).toBe(true)
    expect(p(['p', 'B', 'requests'])).toBe(false)
    expect(p(['credits'])).toBe(true)
    expect(p(['health'])).toBe(false)
    expect(p(['system-check'])).toBe(false)
  })

  it('moving a box refreshes only that film\'s layout', () => {
    const p = staleFor(ev('entity_changed', { entity: 'canvas', project_id: 'A' }))!
    expect(p(['p', 'A', 'canvas'])).toBe(true)
    expect(p(['p', 'A', 'scenes', 'v1'])).toBe(false)
  })

  it('unknown events still refresh everything but health', () => {
    const p = staleFor(ev('something_new'))!
    expect(p(['p', 'A', 'runs'])).toBe(true)
    expect(p(['health'])).toBe(false)
  })

  it('merges a debounce window of events', () => {
    expect(mergeStale([null, null])).toBeNull()
    const p = mergeStale([null, staleFor(ev('request_update', { project_id: 'A' })), staleFor(ev('director_stage', {}))])!
    expect(p(['p', 'B', 'runs'])).toBe(true)
    expect(p(['timeline', 'r1'])).toBe(true)
  })
})
