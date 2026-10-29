import { describe, expect, it } from 'vitest'
import { computeStale } from './stale'
import { character, request, scene } from '../test/fixtures'

const scenes = [
  scene({ id: 's1', character_names: ['Teacher Lan'] }),
  scene({ id: 's2', parent_scene_id: 's1', chain_type: 'CONTINUATION', character_names: [] }),
  scene({ id: 's3', parent_scene_id: 's2', chain_type: 'CONTINUATION', character_names: [] }),
]
const img = (id: string, scene_id: string, t: string) =>
  request({ id, scene_id, type: 'GENERATE_IMAGE', updated_at: t })

describe('computeStale', () => {
  it('nothing stale when children are newer than parents', () => {
    const reqs = [img('a', 's1', '01'), img('b', 's2', '02'), img('c', 's3', '03')]
    expect(computeStale(scenes, [character()], reqs, 'HORIZONTAL')).toEqual(new Set())
  })

  it('regenerated parent makes every descendant stale', () => {
    const reqs = [img('a', 's1', '01'), img('b', 's2', '02'), img('c', 's3', '03'),
                  request({ id: 'd', scene_id: 's1', type: 'REGENERATE_IMAGE', updated_at: '04' })]
    expect(computeStale(scenes, [character()], reqs, 'HORIZONTAL')).toEqual(new Set(['s2', 's3']))
  })

  it('newer asset reference image makes the referencing scene (and its chain) stale', () => {
    const reqs = [img('a', 's1', '01'), img('b', 's2', '02'), img('c', 's3', '03'),
                  request({ id: 'e', scene_id: null, character_id: 'c1', type: 'UPLOAD_IMAGE', updated_at: '05' })]
    expect(computeStale(scenes, [character()], reqs, 'HORIZONTAL')).toEqual(new Set(['s1', 's2', 's3']))
  })

  it('ignores the other orientation and failed requests', () => {
    const reqs = [img('a', 's1', '01'), img('b', 's2', '02'),
                  request({ id: 'f', scene_id: 's1', orientation: 'VERTICAL', updated_at: '09' }),
                  request({ id: 'g', scene_id: 's1', status: 'FAILED', updated_at: '09' })]
    expect(computeStale(scenes.slice(0, 2), [character()], reqs, 'HORIZONTAL')).toEqual(new Set())
  })

  it('a scene with no completed image is never stale', () => {
    expect(computeStale(scenes, [character()], [img('a', 's1', '05')], 'HORIZONTAL')).toEqual(new Set())
  })
})
