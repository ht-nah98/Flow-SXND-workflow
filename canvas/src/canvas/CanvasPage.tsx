import {
  Background, Controls, MiniMap, Panel, ReactFlow, ReactFlowProvider, useNodesInitialized, useNodesState, useReactFlow,
  type Connection, type Edge, type FinalConnectionState, type NodeChange, type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { projectKey, useProjectData } from '../api/queries'
import { useChoice } from '../components/ChoiceDialog'
import { useToast } from '../components/Toast'
import { parseKey } from '../graph/keys'
import { applyFocus, type WireMode } from '../graph/focus'
import { NODE_SIZE, assetSpot, autoLayout, flowLayout, ideaSpot, placeNear, rowsLayout, scriptSpot, type LayoutNode } from '../graph/layout'
import {
  buildGraph, orientationOf, type AssetNodeData, type CanvasNode, type FinalNodeData, type SceneNodeData,
} from '../graph/mapping'
import { checkConnection, edgeRemoval, type RuleContext } from '../graph/rules'
import { computeStale } from '../graph/stale'
import { explainError } from '../lib/errors'
import { AssetLibrary, CHARACTER_MIME } from '../panels/AssetLibrary'
import { AssetNode } from '../nodes/AssetNode'
import { NoteNode } from '../nodes/NoteNode'
import { SceneNode } from '../nodes/SceneNode'
import { FinalNode } from '../nodes/FinalNode'
import { ReviewNode } from '../nodes/ReviewNode'
import { IdeaNode } from '../nodes/IdeaNode'
import { ScriptNode } from '../nodes/ScriptNode'
import { VideoNode } from '../nodes/VideoNode'
import { ASSET_PALETTE } from '../graph/colors'
import { Storyboard } from '../views/Storyboard'
import { RunLogPanel } from '../components/RunLogPanel'
import { nodeKey } from '../graph/keys'
import { AssistBar, type AssistTarget } from '../components/AssistBar'
import { CanvasActionsContext } from './actions-context'
import { useActions } from './useActions'

type View = 'canvas' | 'storyboard'
type LayoutKind = 'rows' | 'flow' | 'graph'
/** Per-viewer conveniences only: storage can be missing (private window) and that must not matter. */
const pref = <T extends string>(key: string, fallback: T, allowed?: readonly T[]): T => {
  try {
    const v = localStorage.getItem(key) as T | null
    return v != null && (!allowed || allowed.includes(v)) ? v : fallback   // a stale/garbled value must not blank the page
  } catch { return fallback }
}
const savePref = (key: string, v: string) => { try { localStorage.setItem(key, v) } catch { /* not persisted */ } }

/** Layout input: scenes carry their film order so "Dòng chảy" can stack them top to bottom. */
const layoutNodes = (ns: CanvasNode[]): LayoutNode[] => {
  const videoIdx = new Map<string, number>()
  return ns.map((n) => {
    if (n.type !== 'scene') return { id: n.id, type: n.type! }
    const d = n.data as SceneNodeData
    if (!videoIdx.has(d.video.id)) videoIdx.set(d.video.id, videoIdx.size)
    return { id: n.id, type: 'scene', rank: videoIdx.get(d.video.id)! * 10000 + d.scene.display_order }
  })
}

/** Same functions across renders, each calling the latest closure. */
function useStableHandlers<T extends Record<string, (...args: never[]) => unknown>>(handlers: T): T {
  const latest = useRef(handlers)
  latest.current = handlers
  return useMemo(() => Object.fromEntries(Object.keys(handlers).map((k) => [k,
    (...args: never[]) => latest.current[k](...args)])) as T, []) // eslint-disable-line react-hooks/exhaustive-deps
}

const samePos = (a: { x: number; y: number }, b: { x: number; y: number }) => a.x === b.x && a.y === b.y
const unchanged = (o: CanvasNode, n: CanvasNode) =>
  o.type === n.type && samePos(o.position, n.position) && o.width === n.width && o.height === n.height
  && o.deletable === n.deletable && sameData(o.data, n.data)
/** Key by key: rows react-query did not refetch keep their identity, so only the few rebuilt values (small arrays,
 *  flags) are compared by content. Stringifying the whole node data cost ~7ms per update on a 55-shot film. */
const sameData = (a: Record<string, unknown>, b: Record<string, unknown>) => {
  if (a === b) return true
  const ka = Object.keys(a)
  if (ka.length !== Object.keys(b).length) return false
  return ka.every((k) => a[k] === b[k] || JSON.stringify(a[k]) === JSON.stringify(b[k]))
}

const nodeTypes: NodeTypes = { asset: AssetNode, scene: SceneNode, video: VideoNode, final: FinalNode, script: ScriptNode, idea: IdeaNode, note: NoteNode, review: ReviewNode }

export function CanvasPage() {
  const { pid = '' } = useParams()
  return <ReactFlowProvider><CanvasInner pid={pid} /></ReactFlowProvider>
}

function CanvasInner({ pid }: { pid: string }) {
  const { data, isLoading, error } = useProjectData(pid)
  const qc = useQueryClient()
  const toast = useToast()
  const choose = useChoice()
  const rf = useReactFlow()
  const actions = useActions(pid, data)

  const stale = useMemo(() => {
    if (!data) return new Set<string>()
    return new Set(data.videos.flatMap((v) => [...computeStale(
      data.scenesByVideo[v.id] ?? [], data.characters, data.requests, orientationOf(v))]))
  }, [data])
  const graph = useMemo(() => (data ? buildGraph(data, stale) : null), [data, stale])
  const ctx: RuleContext = useMemo(() => ({
    scenes: new Map(Object.values(data?.scenesByVideo ?? {}).flat().map((s) => [s.id, s])),
    characters: new Map((data?.characters ?? []).map((c) => [c.id, c])),
  }), [data])

  const [nodes, setNodes, onNodesChange] = useNodesState<CanvasNode>([])
  const dragging = useRef(new Set<string>())
  // Selected scenes and assets are what the "ask AI" bar works on (SciCloud sample, 19/10).
  const assistTargets: AssistTarget[] = useMemo(() => nodes.filter((n) => n.selected).flatMap((n): AssistTarget[] => {
    if (n.type === 'scene') { const d = n.data as SceneNodeData; return [{ kind: 'scene', id: d.scene.id, label: `Cảnh ${d.scene.display_order + 1}` }] }
    if (n.type === 'asset') { const d = n.data as AssetNodeData; return [{ kind: 'character', id: d.character.id, label: d.character.name }] }
    return []
  }), [nodes])
  useEffect(() => {
    if (!graph) return
    setNodes((prev) => {
      const old = new Map(prev.map((n) => [n.id, n]))
      return graph.nodes.map((n) => {
        const o = old.get(n.id)
        const next = { ...n, deletable: n.type !== 'video' && n.type !== 'script' && n.type !== 'idea',
                       position: o && dragging.current.has(n.id) ? o.position : n.position, selected: o?.selected,
                       measured: o?.measured,
                       // A box the user just resized keeps its live size until the saved one comes back (directive G1).
                       width: o?.width ?? n.width, height: o?.height ?? n.height }
        // Perf (19/10): a node whose content did not change keeps its old object, so React Flow skips redrawing it
        // (one finished clip used to redraw all 74 boxes of a 55-shot film).
        return o && unchanged(o, next) ? o : next
      })
    })
  }, [graph, setNodes])

  // The declarative `fitView` prop below only fits whatever `nodes` holds on
  // its first render; since nodes start empty and populate above once data
  // loads, that first fit can run against zero nodes, leaving the viewport
  // unfit to the real content (and connection handles off-screen). Fit
  // explicitly once nodes are mounted, measured, AND every node has a real
  // (not placeholder (0,0)) position — i.e. once the layingOut effect below
  // has nothing left to place. Fitting against placeholder positions would
  // consume the one-shot guard before the real auto-layout positions land.
  const nodesInitialized = useNodesInitialized()
  const fittedOnce = useRef(false)
  useEffect(() => {
    if (!fittedOnce.current && nodesInitialized && nodes.length > 0 && graph?.missingLayout.length === 0) {
      fittedOnce.current = true
      rf.fitView()
    }
  }, [nodesInitialized, nodes.length, graph, rf])

  const persist = useCallback(async (rows: { node_key: string; x: number; y: number; w?: number; h?: number }[]) => {
    try {
      await api.putCanvasNodes(pid, rows)
      await qc.invalidateQueries({ queryKey: [...projectKey(pid), 'canvas'] })
    } catch (e) { toast(explainError(e instanceof Error ? e.message : String(e)).message, 'error') }
  }, [pid, qc, toast])

  const layingOut = useRef(false)
  useEffect(() => {
    if (!graph || !data || graph.missingLayout.length === 0 || layingOut.current) return
    layingOut.current = true
    let rows: { node_key: string; x: number; y: number }[]
    // A fresh canvas, or the director just filled it (assets + scenes at once): lay everything out again.
    if (data.layout.length === 0 || graph.missingLayout.length * 2 > graph.nodes.length) {
      const pos = rowsLayout(layoutNodes(graph.nodes), graph.edges)
      rows = Object.entries(pos).map(([node_key, p]) => ({ node_key, ...p }))
    } else {
      const missing = new Set(graph.missingLayout)
      const occupied = graph.nodes.filter((n) => !missing.has(n.id)).map((n) => ({ ...n.position, type: n.type! }))
      rows = []
      for (const id of graph.missingLayout) {
        const type = graph.nodes.find((n) => n.id === id)!.type!
        if (type === 'script') { rows.push({ node_key: id, ...scriptSpot(occupied) }); continue }
        if (type === 'idea') {
          const script = graph.nodes.find((n) => n.type === 'script')!
          const placed = rows.find((r) => r.node_key === script.id) ?? (missing.has(script.id) ? null : script.position)
          rows.push({ node_key: id, ...ideaSpot(placed ?? scriptSpot(occupied)) })
          continue
        }
        const inRow = type === 'asset' ? assetSpot(occupied) : null
        if (inRow) { occupied.push({ ...inRow, type }); rows.push({ node_key: id, ...inRow }); continue }
        const anchorEdge = graph.edges.find((e) => e.target === id && (type === 'video' || !e.id.startsWith('member:')))
        const anchor = anchorEdge ? graph.nodes.find((n) => n.id === anchorEdge.source)?.position ?? null : null
        const p = placeNear(anchor, occupied, type, type === 'review' ? NODE_SIZE.final.w : undefined)
        occupied.push({ ...p, type })
        rows.push({ node_key: id, ...p })
      }
    }
    void persist(rows).finally(() => { layingOut.current = false })
  }, [graph, data, persist])

  const relayout = (kind: LayoutKind) => {
    if (!graph) return
    const pos = kind === 'rows' ? rowsLayout(layoutNodes(graph.nodes), graph.edges)
      : kind === 'flow' ? flowLayout(layoutNodes(graph.nodes), graph.edges)
      : autoLayout(graph.nodes.map((n) => ({ id: n.id, type: n.type! })), graph.edges)
    void persist(Object.entries(pos).map(([node_key, p]) => ({ node_key, ...p })))
      .then(() => setTimeout(() => rf.fitView({ duration: 300 }), 50))
  }

  const [view, setView] = useState<View>(() => pref<View>('fc.view', 'canvas', ['canvas', 'storyboard']))
  const [wires, setWires] = useState<WireMode>(() => pref<WireMode>('fc.wires', 'all'))
  const [focusId, setFocusId] = useState<string | null>(null)
  const [fitTo, setFitTo] = useState<string | null>(null)
  const pickView = (v: View) => { setView(v); savePref('fc.view', v) }
  const pickWires = (w: WireMode) => { setWires(w); savePref('fc.wires', w) }
  const shown = useMemo(() => applyFocus(nodes, graph?.edges ?? [], focusId, wires), [nodes, graph, focusId, wires])
  useEffect(() => {
    if (view !== 'canvas' || !fitTo) return
    const t = setTimeout(() => { rf.fitView({ nodes: [{ id: fitTo }], duration: 400, maxZoom: 0.9 }); setFitTo(null) }, 80)
    return () => clearTimeout(t)
  }, [view, fitTo, rf])
  // The canvas is laid out while hidden behind the storyboard: fit it when it comes back into view.
  const prevView = useRef(view)
  useEffect(() => {
    if (prevView.current !== 'canvas' && view === 'canvas' && !fitTo) setTimeout(() => rf.fitView(), 50)
    prevView.current = view
  }, [view, fitTo, rf])
  const openOnCanvas = (id: string) => { pickView('canvas'); setFocusId(id); setFitTo(id) }
  // 📋 Nhật ký (21/10): a panel beside the canvas; its "Cảnh N →" buttons bring that scene into view.
  const [logOpen, setLogOpen] = useState(() => pref<string>('fc.log', '0') === '1')
  const toggleLog = () => { setLogOpen((o) => { savePref('fc.log', o ? '0' : '1'); return !o }) }
  const runIds = useMemo(() => [...(data?.runs ?? [])].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? '')).map((r) => r.id),
                         [data?.runs])
  const showScene = (n: number) => {
    const sc = Object.values(data?.scenesByVideo ?? {}).flat().find((s) => s.display_order === n - 1)
    if (!sc) return
    const key = nodeKey.scene(sc.id)
    pickView('canvas')
    setNodes((ns) => ns.map((x) => (x.selected === (x.id === key) ? x : { ...x, selected: x.id === key })))
    setFitTo(key)
  }

  const center = () => rf.screenToFlowPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 })

  const onConnect = (c: Connection) => {
    const r = checkConnection(c, ctx)
    if (!r.ok) { toast(r.reason, 'error'); return }
    void actions.patchScene(r.mutation.sceneId, r.mutation.patch).catch(() => {})
  }

  const onConnectEnd = (event: MouseEvent | TouchEvent, st: FinalConnectionState) => {
    if (st.toNode || st.fromNode?.type !== 'scene' || st.fromHandle?.id !== 'next') return
    const point = 'changedTouches' in event ? event.changedTouches[0] : event
    const parent = ctx.scenes.get(parseKey(st.fromNode.id).id)
    if (parent) void actions.addContinuation(parent, rf.screenToFlowPosition({ x: point.clientX, y: point.clientY })).catch(() => {})
  }

  // Edges removed only because their node is being deleted must not trigger scene patches.
  const deletingNodes = useRef(new Set<string>())
  const onBeforeDelete = async ({ nodes: ns, edges: es }: { nodes: CanvasNode[]; edges: Edge[] }) => {
    const important = ns.filter((n) => n.type === 'scene' || n.type === 'asset')
    if (important.length === 0) {
      ns.forEach((n) => deletingNodes.current.add(n.id))
      return { nodes: ns, edges: es.filter((e) => e.deletable !== false) }
    }
    const pick = await choose({
      title: 'Xoá khỏi canvas?',
      body: `${important.filter((n) => n.type === 'scene').length} cảnh sẽ bị xoá hẳn. ` +
            `${important.filter((n) => n.type === 'asset').length} asset sẽ được bỏ khỏi project (vẫn còn trong thư viện).`,
      options: [{ value: 'ok', label: 'Xoá' }],
    })
    if (pick !== 'ok') return false
    ns.forEach((n) => deletingNodes.current.add(n.id))
    return true
  }

  const onNodesDelete = async (ns: CanvasNode[]) => {
    for (const n of ns) {
      const { kind, id } = parseKey(n.id)
      try {
        if (kind === 'note') await api.deleteCanvasNode(pid, n.id)
        if (kind === 'character') await api.detachCharacter(pid, id)
        if (kind === 'scene') {
          for (const child of [...ctx.scenes.values()].filter((s) => s.parent_scene_id === id)) {
            await api.patchScene(child.id, { parent_scene_id: null, chain_type: 'ROOT' })
          }
          await api.deleteScene(id)
        }
      } catch (e) { toast(explainError(e instanceof Error ? e.message : String(e)).message, 'error') }
      deletingNodes.current.delete(n.id)
    }
    void qc.invalidateQueries({ queryKey: projectKey(pid) })
  }

  const onEdgesDelete = (es: Edge[]) => {
    for (const e of es) {
      if (deletingNodes.current.has(e.source) || deletingNodes.current.has(e.target)) continue
      const m = edgeRemoval(e.id, ctx)
      if (m) void actions.patchScene(m.sceneId, m.patch).catch(() => {})
    }
  }

  if (error) return <p className="p-6 text-red-300">{explainError(error instanceof Error ? error.message : String(error)).message}</p>
  // Perf (19/10): React Flow hands these to every node box; new functions on each render redrew all 74 boxes of a
  // 55-shot film on every data refresh. Stable wrappers call the latest version instead.
  const flowHandlers = useStableHandlers({
    onNodeClick: (_: unknown, n: CanvasNode) => setFocusId((f) => (f === n.id ? null : n.id)),
    onPaneClick: () => setFocusId(null),
    onNodesChange: (changes: NodeChange<CanvasNode>[]) => {
      onNodesChange(changes)
      // A finished resize (directive G1): save the box's size with its position.
      const ended = changes.filter((c) => c.type === 'dimensions' && c.resizing === false).map((c) => (c as { id: string }).id)
      if (ended.length) setTimeout(() => void persist(ended.flatMap((nid) => {
        const n = rf.getNode(nid)
        const w = n?.width ?? n?.measured?.width, h = n?.height ?? n?.measured?.height
        return n && w && h ? [{ node_key: nid, x: n.position.x, y: n.position.y, w, h }] : []
      })))
    },
    onNodeDragStart: (_: unknown, n: CanvasNode) => { dragging.current.add(n.id) },
    onNodeDragStop: (_: unknown, n: CanvasNode, dragged: CanvasNode[]) => {
      const moved = dragged?.length ? dragged : [n]
      void persist(moved.map((m) => ({ node_key: m.id, x: m.position.x, y: m.position.y })))
        .finally(() => moved.forEach((m) => dragging.current.delete(m.id)))
    },
    onConnect, onConnectEnd,
    isValidConnection: (c: Connection | Edge) => checkConnection(c as Connection, ctx).ok,
    onBeforeDelete, onNodesDelete: (ns: CanvasNode[]) => void onNodesDelete(ns), onEdgesDelete,
  })

  if (isLoading || !data || !graph) return <p className="p-6 text-zinc-400">Đang tải canvas…</p>

  return (
    <CanvasActionsContext.Provider value={actions}>
      <div className="flex h-[100dvh] flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 px-3 py-2 text-sm">
          <Link to="/" className="text-zinc-400 hover:text-white">← Project</Link>
          <span className="font-semibold">{data.project.name}</span>
          <span className="flex-1" />
          <button className="rounded bg-zinc-800 px-2 py-1" onClick={() => data.videos[0] && void actions.addScene(data.videos[0], center()).catch(() => {})}>+ Cảnh</button>
          <button className="rounded bg-zinc-800 px-2 py-1" onClick={() => void actions.addNote(center()).catch(() => {})}>+ Ghi chú</button>
          <div className="flex overflow-hidden rounded border border-zinc-700" role="tablist" aria-label="Kiểu xem">
            {([['canvas', '🧩 Canvas'], ['storyboard', '🎞 Storyboard']] as const).map(([v, label]) => (
              <button key={v} role="tab" aria-selected={view === v} onClick={() => pickView(v)}
                      className={`px-2 py-1 ${view === v ? 'bg-sky-700 text-white' : 'bg-zinc-900 text-zinc-300'}`}>{label}</button>
            ))}
          </div>
          {view === 'canvas' && (
            <>
              <select aria-label="Sắp xếp" value="" className="rounded bg-zinc-800 px-2 py-1"
                      title="Hàng ngang: đọc như trang sách — ý tưởng → kịch bản, xuống dòng asset, xuống dòng các cảnh, rồi video → phim"
                      onChange={(e) => { if (e.target.value) relayout(e.target.value as LayoutKind) }}>
                <option value="">Sắp xếp…</option>
                <option value="rows">Hàng ngang</option>
                <option value="flow">Cột dọc</option>
                <option value="graph">Theo đồ thị</option>
              </select>
              <select aria-label="Dây asset" value={wires} className="rounded bg-zinc-800 px-2 py-1"
                      onChange={(e) => pickWires(e.target.value as WireMode)}>
                <option value="all">Dây: luôn hiện</option>
                <option value="focus">Dây: khi chọn</option>
              </select>
            </>
          )}
          <button className="rounded bg-zinc-800 px-2 py-1" onClick={() => void actions.exportProject()}>Xuất project</button>
          <button className={`rounded px-2 py-1 ${logOpen ? 'bg-sky-700 text-white' : 'bg-zinc-800'}`} onClick={toggleLog}
                  aria-pressed={logOpen} title="Từng bước, lý do bị trả lại, AI và Flow đã làm gì">📋 Nhật ký</button>
        </div>
        {view === 'storyboard' && (
          <div className="min-h-0 flex-1">
            <Storyboard
              scenes={graph.nodes.filter((n) => n.type === 'scene')
                .map((n) => ({ id: n.id, data: n.data as SceneNodeData }))
                .sort((a, b) => layoutRank(a.data) - layoutRank(b.data))}
              assets={graph.nodes.filter((n) => n.type === 'asset').map((n) => ({ id: n.id, data: n.data as AssetNodeData }))
                .sort((a, b) => order(a.data) - order(b.data))}
              films={graph.nodes.filter((n) => n.type === 'final').map((n) => n.data as FinalNodeData)}
              onOpen={openOnCanvas} />
          </div>
        )}
        <div className={`relative flex flex-1 ${view === 'canvas' ? '' : 'hidden'}`}>
          <AssetLibrary attachedIds={new Set(data.characters.map((c) => c.id))} dropPoint={center} />
          <div className="flex-1" data-testid="canvas"
               onDragOver={(e) => { if (e.dataTransfer.types.includes(CHARACTER_MIME)) e.preventDefault() }}
               onDrop={(e) => {
                 const cid = e.dataTransfer.getData(CHARACTER_MIME)
                 if (!cid) return
                 e.preventDefault()
                 void actions.placeCharacter(cid, rf.screenToFlowPosition({ x: e.clientX, y: e.clientY })).catch(() => {})
               }}>
            <ReactFlow
              nodes={shown.nodes} edges={shown.edges} nodeTypes={nodeTypes}
              {...flowHandlers}
              minZoom={0.1} fitView proOptions={{ hideAttribution: true }} colorMode="dark">
              <Background />
              <Legend assets={graph.nodes.filter((n) => n.type === 'asset').map((n) => ({ id: n.id, data: n.data as AssetNodeData }))
                        .sort((a, b) => order(a.data) - order(b.data))}
                      focusId={focusId} onFocus={setFocusId} />
              <Controls />
              <MiniMap pannable zoomable />
              <Panel position="bottom-center" className="!mb-14"><AssistBar projectId={pid} targets={assistTargets} /></Panel>
            </ReactFlow>
          </div>
          {logOpen && <RunLogPanel projectId={pid} runIds={runIds} onScene={showScene} onClose={toggleLog} />}
        </div>
      </div>
    </CanvasActionsContext.Provider>
  )
}

/** Assets keep the palette order (characters, locations, props) wherever they are listed. */
const order = (a: AssetNodeData) => ASSET_PALETTE.indexOf(a.color)
const layoutRank = (d: SceneNodeData) => d.scene.display_order

/** What the colours mean, and a shortcut to light up one asset's scenes. */
function Legend({ assets, focusId, onFocus }: {
  assets: { id: string; data: AssetNodeData }[]; focusId: string | null; onFocus: (id: string | null) => void
}) {
  if (!assets.length) return null
  return (
    <Panel position="top-right" className="!m-2 flex max-w-[220px] flex-col gap-1 rounded-lg bg-zinc-900/90 p-2 text-[11px] shadow">
      <div className="font-semibold text-zinc-300">Màu asset · bấm để soi</div>
      {assets.map(({ id, data: a }) => (
        <button key={id} onClick={() => onFocus(focusId === id ? null : id)}
                className={`flex items-center gap-1.5 rounded px-1 py-0.5 text-left hover:bg-zinc-800 ${focusId === id ? 'bg-zinc-800' : ''}`}>
          <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: a.color }} />
          <span className="truncate">{a.character.name}</span>
          <span className="ml-auto text-zinc-500">{a.uses}</span>
        </button>
      ))}
      <div className="mt-1 border-t border-zinc-700 pt-1 text-zinc-400">
        <div>Chip màu trên cảnh: asset cảnh dùng</div>
        <div>━ asset → cảnh · ┄ cảnh thuộc video</div>
        <div><span className="text-amber-400">━</span> cam: video → phim</div>
        <div>Viền cảnh: <span className="text-emerald-400">xong</span> · <span className="text-sky-400">đang tạo</span> · <span className="text-red-400">lỗi</span></div>
      </div>
    </Panel>
  )
}
