import type { Edge, Node } from '@xyflow/react'

export type WireMode = 'all' | 'focus'

/** Clicking a node lights up what it is connected to and dims the rest: an asset shows the scenes
 *  made from it, a scene shows its assets and video. `wires: 'focus'` hides asset wires until then. */
export function applyFocus<N extends Node>(nodes: N[], edges: Edge[], focusId: string | null, wires: WireMode) {
  const isRef = (e: Edge) => e.id.startsWith('ref:')
  const touching = (e: Edge) => focusId !== null && (e.source === focusId || e.target === focusId)
  const related = new Set<string>(focusId ? [focusId] : [])
  for (const e of edges) if (touching(e)) { related.add(e.source); related.add(e.target) }

  const outEdges = edges.map((e) => {
    const hidden = wires === 'focus' && isRef(e) && !touching(e)
    if (!focusId) return { ...e, hidden }
    const on = touching(e)
    return { ...e, hidden, zIndex: on ? 10 : 0,
             style: { ...e.style, opacity: on ? 1 : 0.08, strokeWidth: on ? 4 : e.style?.strokeWidth } }
  })
  const outNodes = focusId
    ? nodes.map((n) => ({ ...n, style: { ...n.style, opacity: related.has(n.id) ? 1 : 0.2, transition: 'opacity .15s' } }))
    : nodes
  return { nodes: outNodes, edges: outEdges, related }
}
