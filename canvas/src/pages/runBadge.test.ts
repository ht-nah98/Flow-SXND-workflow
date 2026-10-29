import { describe, expect, it } from 'vitest'
import type { DirectorRun } from '../api/types'
import { runBadge } from './ProjectList'

const run = (o: Partial<DirectorRun>) => ({ status: 'RUNNING', stage: 'STORY', gate: null, ...o }) as DirectorRun

describe('runBadge', () => {
  it('says where the project stands', () => {
    expect(runBadge(undefined, false)).toBe('✋ Làm tay')
    expect(runBadge(run({ status: 'WAITING_GATE', gate: 'SCRIPT' }), false)).toBe('📜 Chờ duyệt kịch bản')
    expect(runBadge(run({ status: 'DONE' }), true)).toBe('✅ Có phim')
    expect(runBadge(run({}), false)).toMatch(/^⏳ Biên kịch/)
  })
})
