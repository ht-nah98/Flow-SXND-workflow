import { describe, expect, it } from 'vitest'
import { autoLayout, flowLayout, NODE_SIZE, placeNear, rowsLayout, scriptSpot } from './layout'

describe('autoLayout', () => {
  it('puts assets left of scenes and scenes left of the video', () => {
    const pos = autoLayout(
      [{ id: 'character:c1', type: 'asset' }, { id: 'scene:s1', type: 'scene' },
       { id: 'scene:s2', type: 'scene' }, { id: 'video:v1', type: 'video' }, { id: 'note:n', type: 'note' }],
      [{ source: 'character:c1', target: 'scene:s1' }, { source: 'scene:s1', target: 'scene:s2' },
       { source: 'scene:s2', target: 'video:v1' }],
    )
    expect(pos['character:c1'].x).toBeLessThan(pos['scene:s1'].x)
    expect(pos['scene:s1'].x).toBeLessThan(pos['scene:s2'].x)
    expect(pos['scene:s2'].x).toBeLessThan(pos['video:v1'].x)
    expect(pos['note:n']).toBeDefined()
  })

  it('puts the script left of every other node, at the top', () => {
    const pos = autoLayout(
      [{ id: 'script:p1', type: 'script' }, { id: 'character:c1', type: 'asset' }, { id: 'scene:s1', type: 'scene' },
       { id: 'video:v1', type: 'video' }],
      [{ source: 'script:p1', target: 'video:v1' }, { source: 'character:c1', target: 'scene:s1' },
       { source: 'scene:s1', target: 'video:v1' }],
    )
    const others = ['character:c1', 'scene:s1', 'video:v1'].map((k) => pos[k])
    expect(pos['script:p1'].x + NODE_SIZE.script.w).toBeLessThan(Math.min(...others.map((p) => p.x)))
    expect(pos['script:p1'].y).toBe(Math.min(...others.map((p) => p.y)))
  })
})

describe('scriptSpot', () => {
  it('sits left of the leftmost node', () => {
    expect(scriptSpot([{ x: 100, y: 50 }, { x: 400, y: -20 }])).toEqual({ x: 100 - NODE_SIZE.script.w - 80, y: -20 })
  })
})

describe('placeNear', () => {
  it('places right of the anchor when free', () => {
    expect(placeNear({ x: 0, y: 0 }, [], 'scene')).toEqual({ x: NODE_SIZE.scene.w + 80, y: 0 })
  })

  it('moves down until it does not overlap', () => {
    const first = placeNear({ x: 0, y: 0 }, [], 'scene')
    const second = placeNear({ x: 0, y: 0 }, [{ ...first, type: 'scene' }], 'scene')
    expect(second.x).toBe(first.x)
    expect(second.y).toBeGreaterThanOrEqual(first.y + NODE_SIZE.scene.h)
  })

  it('without anchor starts at the origin column', () => {
    expect(placeNear(null, [], 'note')).toEqual({ x: 0, y: 0 })
  })
})

describe('flowLayout', () => {
  it('puts each step in its own column, scenes in film order, assets level with their first scene', () => {
    const nodes = [
      { id: 'script:p', type: 'script' }, { id: 'character:a', type: 'asset' }, { id: 'character:b', type: 'asset' },
      { id: 'scene:2', type: 'scene', rank: 2 }, { id: 'scene:1', type: 'scene', rank: 1 },
      { id: 'video:v', type: 'video' }, { id: 'final:v', type: 'final' },
    ]
    const edges = [
      { source: 'character:b', target: 'scene:2' }, { source: 'character:a', target: 'scene:1' },
      { source: 'scene:1', target: 'video:v' }, { source: 'scene:2', target: 'video:v' }, { source: 'video:v', target: 'final:v' },
    ]
    const p = flowLayout(nodes, edges)
    const xs = ['script:p', 'character:a', 'scene:1', 'video:v', 'final:v'].map((id) => p[id].x)
    expect([...xs].sort((a, b) => a - b)).toEqual(xs)
    expect(p['scene:1'].y).toBeLessThan(p['scene:2'].y)
    expect(p['character:a'].y).toBe(p['scene:1'].y)
    expect(p['character:b'].y).toBe(p['scene:2'].y)
    expect(p['final:v'].y).toBe(p['video:v'].y)
  })
})

describe('rowsLayout', () => {
  it('reads like a page: idea/script row, asset row, scene rows wrapping left to right, then video and film', () => {
    const nodes = [
      { id: 'idea:r', type: 'idea' }, { id: 'script:p', type: 'script' },
      { id: 'character:b', type: 'asset' }, { id: 'character:a', type: 'asset' },
      ...[3, 1, 2].map((i) => ({ id: `scene:${i}`, type: 'scene', rank: i })),
      { id: 'video:v', type: 'video' }, { id: 'final:v', type: 'final' },
    ]
    const edges = [{ source: 'character:a', target: 'scene:1' }, { source: 'character:b', target: 'scene:3' },
                   { source: 'video:v', target: 'final:v' }]
    const p = rowsLayout(nodes, edges, 2)
    expect(p['idea:r'].y).toBe(p['script:p'].y)
    expect(p['idea:r'].x).toBeLessThan(p['script:p'].x)
    expect(p['character:a'].y).toBeGreaterThan(p['script:p'].y)
    expect(p['character:a'].x).toBeLessThan(p['character:b'].x)            // a is needed first
    expect(p['scene:1'].y).toBe(p['scene:2'].y)
    expect(p['scene:1'].x).toBeLessThan(p['scene:2'].x)
    expect(p['scene:3'].x).toBe(p['scene:1'].x)                              // wraps to a new row, at the left
    expect(p['scene:3'].y).toBeGreaterThan(p['scene:1'].y)
    expect(p['final:v'].y).toBe(p['video:v'].y)
    expect(p['video:v'].y).toBeGreaterThan(p['scene:3'].y)
  })
})

describe('assetSpot', () => {
  it('a new asset joins the end of the asset row, not a far corner (20/10)', async () => {
    const { assetSpot, NODE_SIZE } = await import('./layout')
    const row = [{ x: 0, y: 100, type: 'asset' }, { x: 300, y: 100, type: 'asset' }, { x: 0, y: 900, type: 'scene' }]
    const p = assetSpot(row)!
    expect(p.y).toBe(100)
    expect(p.x).toBeGreaterThan(300 + NODE_SIZE.asset.w - 1)
    expect(assetSpot([{ x: 0, y: 0, type: 'scene' }])).toBeNull()
  })
})
