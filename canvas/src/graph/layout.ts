import dagre from '@dagrejs/dagre'

export const NODE_SIZE: Record<string, { w: number; h: number }> = {
  // Heights of the full (zoomed-in) nodes, so laid-out nodes never overlap when read up close.
  asset: { w: 220, h: 680 },
  scene: { w: 320, h: 900 },
  video: { w: 280, h: 360 },
  final: { w: 480, h: 340 },
  script: { w: 360, h: 620 },
  idea: { w: 360, h: 560 },
  note: { w: 220, h: 140 },
  review: { w: 520, h: 900 },
}
const GAP = 80

export function autoLayout(nodes: { id: string; type: string }[], edges: { source: string; target: string }[]) {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 60, ranksep: 120 })
  g.setDefaultEdgeLabel(() => ({}))
  // Notes and the script sit outside the graph: the script is the first column, notes go underneath.
  const graphNodes = nodes.filter((n) => n.type !== 'note' && n.type !== 'script' && n.type !== 'idea')
  for (const n of graphNodes) g.setNode(n.id, { width: NODE_SIZE[n.type].w, height: NODE_SIZE[n.type].h })
  const ids = new Set(graphNodes.map((n) => n.id))
  for (const e of edges) if (ids.has(e.source) && ids.has(e.target)) g.setEdge(e.source, e.target)
  dagre.layout(g)
  const out: Record<string, { x: number; y: number }> = {}
  let maxY = 0
  for (const n of graphNodes) {
    const p = g.node(n.id)
    out[n.id] = { x: p.x - p.width / 2, y: p.y - p.height / 2 }
    maxY = Math.max(maxY, p.y + p.height / 2)
  }
  const spot = scriptSpot(graphNodes.map((n) => out[n.id]))
  nodes.filter((n) => n.type === 'script').forEach((n) => { out[n.id] = spot })
  nodes.filter((n) => n.type === 'idea').forEach((n, i) => { out[n.id] = ideaSpot(spot, i) })
  nodes.filter((n) => n.type === 'note').forEach((n, i) => {
    out[n.id] = { x: i * (NODE_SIZE.note.w + GAP), y: maxY + GAP }
  })
  return out
}

const overlaps = (a: { x: number; y: number; type: string }, b: { x: number; y: number; type: string }) => {
  const sa = NODE_SIZE[a.type], sb = NODE_SIZE[b.type]
  return a.x < b.x + sb.w && b.x < a.x + sa.w && a.y < b.y + sb.h && b.y < a.y + sa.h
}

export function placeNear(anchor: { x: number; y: number } | null,
                          occupied: { x: number; y: number; type: string }[], type: string,
                          anchorW: number = NODE_SIZE.scene.w) {
  const x = anchor ? anchor.x + anchorW + GAP : 0
  let y = anchor ? anchor.y : 0
  for (let i = 0; i < 200; i++) {
    const cand = { x, y, type }
    if (!occupied.some((o) => overlaps(cand, o))) return { x, y }
    y += NODE_SIZE[type].h + 20
  }
  return { x, y }
}

/** 20/10: a new asset (e.g. added by a script revision) joins the end of the asset row; it used to land alone in
 *  a far corner, where the user never found its image prompt. */
export function assetSpot(occupied: { x: number; y: number; type: string }[]) {
  const row = occupied.filter((o) => o.type === 'asset')
  if (!row.length) return null
  const y = Math.min(...row.map((o) => o.y))
  return { x: Math.max(...row.filter((o) => o.y === y).map((o) => o.x)) + NODE_SIZE.asset.w + GAP, y }
}

/** The script node opens the canvas: left of everything already placed, aligned with the top. */
export function scriptSpot(occupied: { x: number; y: number }[]) {
  if (!occupied.length) return { x: 0, y: 0 }
  return { x: Math.min(...occupied.map((o) => o.x)) - NODE_SIZE.script.w - GAP, y: Math.min(...occupied.map((o) => o.y)) }
}

/** The idea sits above the script it became (several runs stack upwards). */
export const ideaSpot = (script: { x: number; y: number }, i = 0) =>
  ({ x: script.x, y: script.y - (i + 1) * (NODE_SIZE.idea.h + GAP) })

export type LayoutNode = { id: string; type: string; rank?: number }

/** "Dòng chảy": one column per step — idea/script │ assets │ scenes in film order │ video │ film.
 *  Each asset sits level with the first scene that uses it, so its wires run mostly straight. */
export function flowLayout(nodes: LayoutNode[], edges: { source: string; target: string }[]) {
  const W = NODE_SIZE, ROW = 40
  const col = { script: 0, asset: W.script.w + 2 * GAP }
  const sceneX = col.asset + W.asset.w + 3 * GAP
  const videoX = sceneX + W.scene.w + 3 * GAP
  const finalX = videoX + W.video.w + 2 * GAP
  const out: Record<string, { x: number; y: number }> = {}

  const scenes = nodes.filter((n) => n.type === 'scene').sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0))
  scenes.forEach((n, i) => { out[n.id] = { x: sceneX, y: i * (W.scene.h + ROW) } })
  const sceneRow = new Map(scenes.map((n, i) => [n.id, i]))

  const firstUse = (id: string) => Math.min(...edges.filter((e) => e.source === id && sceneRow.has(e.target))
    .map((e) => sceneRow.get(e.target)!), Infinity)
  const assets = nodes.filter((n) => n.type === 'asset')
    .map((n) => ({ n, first: firstUse(n.id) })).sort((a, b) => a.first - b.first)
  let bottom = -Infinity
  for (const { n, first } of assets) {
    const want = Number.isFinite(first) ? first * (W.scene.h + ROW) : bottom + ROW
    const y = Math.max(want, bottom + ROW)
    out[n.id] = { x: col.asset, y: Number.isFinite(y) ? y : 0 }
    bottom = out[n.id].y + W.asset.h
  }

  for (const v of nodes.filter((n) => n.type === 'video')) {
    const ys = edges.filter((e) => e.target === v.id && out[e.source] && sceneRow.has(e.source)).map((e) => out[e.source].y)
    const y = ys.length ? (Math.min(...ys) + Math.max(...ys)) / 2 : 0
    out[v.id] = { x: videoX, y }
    const film = edges.find((e) => e.source === v.id && nodes.find((n) => n.id === e.target)?.type === 'final')
    if (film) out[film.target] = { x: finalX, y }
  }
  for (const e of edges) {   // the film's review sits right of the film
    const r = nodes.find((n) => n.id === e.target && n.type === 'review')
    if (r && out[e.source]) out[r.id] = { x: out[e.source].x + W.final.w + GAP, y: out[e.source].y }
  }
  nodes.filter((n) => n.type === 'final' && !out[n.id]).forEach((n, i) => { out[n.id] = { x: finalX, y: i * (W.final.h + ROW) } })

  const spot = { x: col.script, y: 0 }
  nodes.filter((n) => n.type === 'script').forEach((n) => { out[n.id] = spot })
  nodes.filter((n) => n.type === 'idea').forEach((n, i) => { out[n.id] = ideaSpot(spot, i) })
  const maxY = Math.max(0, ...Object.entries(out).map(([id, p]) => p.y + W[nodes.find((n) => n.id === id)!.type].h))
  nodes.filter((n) => n.type === 'note').forEach((n, i) => { out[n.id] = { x: i * (W.note.w + GAP), y: maxY + GAP } })
  return out
}

/** "Hàng ngang": read like a page — left to right, then a new row for the next step:
 *  idea → script │ assets │ scenes in film order (wrapping every `perRow`) │ video → film. */
export function rowsLayout(nodes: LayoutNode[], edges: { source: string; target: string }[], perRow = 8) {
  const W = NODE_SIZE, ROW_GAP = 2 * GAP
  const out: Record<string, { x: number; y: number }> = {}
  let y = 0
  const row = (items: LayoutNode[]) => {
    if (!items.length) return
    let x = 0
    for (const n of items) { out[n.id] = { x, y }; x += W[n.type].w + GAP }
    y += Math.max(...items.map((n) => W[n.type].h)) + ROW_GAP
  }
  const of = (t: string) => nodes.filter((n) => n.type === t)

  row([...of('idea'), ...of('script')])
  // Assets in the order the film first needs them, unused ones last.
  const scenes = of('scene').sort((a, b) => (a.rank ?? 0) - (b.rank ?? 0))
  const sceneIdx = new Map(scenes.map((n, i) => [n.id, i]))
  const first = (id: string) => Math.min(Infinity, ...edges.filter((e) => e.source === id && sceneIdx.has(e.target))
    .map((e) => sceneIdx.get(e.target)!))
  row(of('asset').map((n) => ({ n, f: first(n.id) })).sort((a, b) => a.f - b.f).map(({ n }) => n))
  for (let i = 0; i < scenes.length; i += perRow) row(scenes.slice(i, i + perRow))
  const films = of('final')
  row(of('video').flatMap((v) => {
    const f = films.find((x) => edges.some((e) => e.source === v.id && e.target === x.id))
    const r = f && of('review').find((x) => edges.some((e) => e.source === f.id && e.target === x.id))
    return f ? (r ? [v, f, r] : [v, f]) : [v]
  }).concat(films.filter((f) => !edges.some((e) => e.target === f.id))))
  row(of('note'))
  return out
}
