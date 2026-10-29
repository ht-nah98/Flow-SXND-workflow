import { describe, expect, it } from 'vitest'
import type { DirectorRun } from '../api/types'
import { filmTimeline, segmentAt } from './filmTimeline'

const run = (mode: string, shots: object[], trims: [number, number][], drop: string[] = []) => ({
  plan: { brief: { film_mode: mode }, shotlist: { shots }, trims, drop, ids: { scenes: { a: 'S1', b: 'S2', c: 'S3' } } },
}) as unknown as DirectorRun

describe('filmTimeline', () => {
  it('places each used shot in the cut film with how it is entered', () => {
    const segs = filmTimeline(run('continuous', [{ id: 'a', order: 1 }, { id: 'b', order: 2, continues: true },
                                                 { id: 'c', order: 3, continues: true }], [[0, 10], [1, 8], [1.5, 10]]))
    expect(segs.map((s) => [s.sceneId, s.start, s.len, s.join])).toEqual([['S1', 0, 10, 'cut'], ['S2', 10, 7, 'chain'], ['S3', 17, 8.5, 'chain']])
    expect(segmentAt(segs, 16.9)).toBe(1)
    expect(segmentAt(segs, 30)).toBe(-1)
  })

  it('a dropped shot breaks the join and keyframe joins are named', () => {
    const segs = filmTimeline(run('keyframe', [{ id: 'a', order: 1 }, { id: 'b', order: 2, join_in: 'screen' },
                                               { id: 'c', order: 3, join_in: 'occlusion' }], [[2, 4], [0, 2.5]], ['b']))
    expect(segs.map((s) => [s.sceneId, s.join])).toEqual([['S1', 'cut'], ['S3', 'cut']])
    expect(filmTimeline(run('cut', [{ id: 'a', order: 1 }], []))).toEqual([])
  })
})
