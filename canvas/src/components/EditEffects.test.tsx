import { describe, expect, it } from 'vitest'
import { setClip } from './EditEffects'

describe('setClip', () => {
  it('changes only the chosen clip', () => {
    const edit = { look: 'goc', clips: [{ shot_id: 'SH01', fx: [], transition_out: 'cat' },
                                        { shot_id: 'SH02', fx: ['hat'], transition_out: null }] }
    const next = setClip(edit, 'SH01', { transition_out: 'nhay-trang' })
    expect(next.clips[0]).toEqual({ shot_id: 'SH01', fx: [], transition_out: 'nhay-trang' })
    expect(next.clips[1]).toBe(edit.clips[1])
    expect(edit.clips[0].transition_out).toBe('cat')
  })
})
