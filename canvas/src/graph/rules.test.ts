import { describe, expect, it } from 'vitest'
import { checkConnection, edgeRemoval, type RuleContext } from './rules'
import { character, scene } from '../test/fixtures'

const ctx = (): RuleContext => ({
  scenes: new Map([
    ['s1', scene({ id: 's1', character_names: [] })],
    ['s2', scene({ id: 's2', parent_scene_id: 's1', chain_type: 'CONTINUATION', character_names: ['teacher-lan'] })],
    ['s3', scene({ id: 's3', character_names: [] })],
    ['x1', scene({ id: 'x1', video_id: 'v2', character_names: [] })],
  ]),
  characters: new Map([['c1', character()]]),
})
const conn = (source: string, sourceHandle: string, target: string, targetHandle: string) =>
  ({ source, sourceHandle, target, targetHandle })

describe('checkConnection', () => {
  it('asset → scene adds the asset name', () => {
    const r = checkConnection(conn('character:c1', 'out', 'scene:s1', 'refs'), ctx())
    expect(r).toEqual({ ok: true, mutation: { sceneId: 's1', patch: { character_names: ['Teacher Lan'] } } })
  })

  it('rejects an asset already referenced by slug', () => {
    const r = checkConnection(conn('character:c1', 'out', 'scene:s2', 'refs'), ctx())
    expect(r.ok).toBe(false)
  })

  it('scene → scene makes a CONTINUATION', () => {
    const r = checkConnection(conn('scene:s1', 'next', 'scene:s3', 'prev'), ctx())
    expect(r).toEqual({ ok: true, mutation: { sceneId: 's3', patch: { parent_scene_id: 's1', chain_type: 'CONTINUATION' } } })
  })

  it.each([
    ['self loop', conn('scene:s1', 'next', 'scene:s1', 'prev')],
    ['second parent', conn('scene:s3', 'next', 'scene:s2', 'prev')],
    ['cycle', conn('scene:s2', 'next', 'scene:s1', 'prev')],
    ['other video', conn('scene:s1', 'next', 'scene:x1', 'prev')],
    ['wrong kinds', conn('scene:s1', 'next', 'character:c1', 'out')],
    ['video target', conn('character:c1', 'out', 'video:v1', 'scenes')],
  ])('rejects %s', (_name, c) => {
    const r = checkConnection(c, ctx())
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.reason.length).toBeGreaterThan(0)
  })
})

describe('edgeRemoval', () => {
  it('removing a ref drops the name even when stored as slug (Review Focus 1)', () => {
    expect(edgeRemoval('ref:c1->s2', ctx())).toEqual({ sceneId: 's2', patch: { character_names: [] } })
  })

  it('removing a chain makes the child ROOT', () => {
    expect(edgeRemoval('chain:s1->s2', ctx())).toEqual(
      { sceneId: 's2', patch: { parent_scene_id: null, chain_type: 'ROOT' } })
  })

  it('member edges cannot be removed', () => {
    expect(edgeRemoval('member:s1->v1', ctx())).toBeNull()
  })
})
