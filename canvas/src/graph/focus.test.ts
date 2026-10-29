import type { Edge, Node } from '@xyflow/react'
import { describe, expect, it } from 'vitest'
import { applyFocus } from './focus'

const n = (id: string): Node => ({ id, position: { x: 0, y: 0 }, data: {} })
const nodes = ['character:a', 'character:b', 'scene:1', 'scene:2', 'video:v'].map(n)
const edges: Edge[] = [
  { id: 'ref:a->1', source: 'character:a', target: 'scene:1' },
  { id: 'ref:b->2', source: 'character:b', target: 'scene:2' },
  { id: 'member:1->v', source: 'scene:1', target: 'video:v' },
]

describe('applyFocus', () => {
  it('lights the asset and the scenes made from it, dims the rest', () => {
    const r = applyFocus(nodes, edges, 'character:a', 'all')
    expect([...r.related].sort()).toEqual(['character:a', 'scene:1'])
    expect(r.nodes.find((x) => x.id === 'scene:2')!.style!.opacity).toBe(0.2)
    expect(r.edges.find((e) => e.id === 'ref:a->1')!.style!.opacity).toBe(1)
  })

  it('hides asset wires until something is selected in focus mode', () => {
    expect(applyFocus(nodes, edges, null, 'focus').edges.filter((e) => !e.hidden).map((e) => e.id)).toEqual(['member:1->v'])
    const r = applyFocus(nodes, edges, 'scene:2', 'focus')
    expect(r.edges.find((e) => e.id === 'ref:b->2')!.hidden).toBe(false)
    expect(r.edges.find((e) => e.id === 'ref:a->1')!.hidden).toBe(true)
  })
})
