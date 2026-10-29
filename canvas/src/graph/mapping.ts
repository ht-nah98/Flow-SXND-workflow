import type { Edge, Node } from '@xyflow/react'
import type {
  CanvasNodeRecord, Character, DirectorRun, FlowRequest, MediaStatus, Orientation, Project, Scene, Video,
} from '../api/types'
import { assetColors } from './colors'
import { nodeKey } from './keys'
import { NODE_SIZE } from './layout'

export interface AssetNodeData extends Record<string, unknown> {
  kind: 'asset'; character: Character; busy: boolean
  /** The asset's colour: its node, wires and chips share it. */
  color: string
  /** How many scenes use it as a reference. */
  uses: number
}
/** A reference asset as shown on a scene: who/what is in the clip, at a glance. */
export interface AssetChip { id: string; name: string; color: string; url: string | null; type: string }
export interface ShotRef { runId: string; shotId: string; chained: number[]; chainedMade: number[] }
export interface SceneNodeData extends Record<string, unknown> {
  kind: 'scene'; scene: Scene; video: Video; orientation: Orientation; stale: boolean; lastError: string | null
  busy: boolean
  videoMode: VideoMode
  assets: AssetChip[]
  /** Set when the AI director made this scene: which run and shot to rewrite. `chained`: in a continuous film, the
   *  scene numbers that open on this clip's last frame (a new take of this clip means remaking them too). */
  shot: ShotRef | null
}
export interface VideoNodeData extends Record<string, unknown> {
  kind: 'video'; video: Video; scenes: Scene[]; staleIds: string[]; busyIds: string[]
  /** Made by the AI director: its clips are generated and cut from the 📜 script node, not by hand. */
  directed: boolean
}
export interface FinalNodeData extends Record<string, unknown> {
  kind: 'final'; video: Video; url: string | null
  /** The director run that cuts this film; shown while the film is not ready yet. */
  run: DirectorRun | null
  /** Scene numbers (1-based, film order) whose clip is ready — a clip failed at the cut gate may have been re-made since. */
  doneScenes: number[]
}
/** Agent Review (21/10): the film judged as a whole, beside the 🎞 film node. */
export interface ReviewNodeData extends Record<string, unknown> {
  kind: 'review'; run: DirectorRun; video: Video
  /** scene node key per shot id, to jump from a finding to its clip */
  sceneKeys: Record<string, string>
  filmReady: boolean
}
export type ScriptStatus = 'todo' | 'busy' | 'done' | 'failed'
export interface ScriptItem { scene: Scene; status: ScriptStatus; error: string | null }
export interface ScriptNodeData extends Record<string, unknown> {
  kind: 'script'; project: Project; parts: { video: Video; items: ScriptItem[] }[]
  /** The director run whose script this is, once the script exists; its approvals live on this node. */
  run: DirectorRun | null; progress: IdeaProgress | null
  /** Assets with no reference image yet: r2v clips must not start until this is empty. */
  missingRefs: string[]
  missingAssets: { id: string; name: string }[]   // assets with no picture yet: the script node jumps to them
}
export interface IdeaProgress { label: string; done: number; total: number }
export interface IdeaNodeData extends Record<string, unknown> {
  kind: 'idea'; run: DirectorRun
  /** Assets already on the project with a picture: the director casts them instead of making new ones. */
  reuse?: string[]
}
export interface NoteNodeData extends Record<string, unknown> { kind: 'note'; text: string }
export type FlowNodeData = AssetNodeData | SceneNodeData | VideoNodeData | FinalNodeData | ScriptNodeData | IdeaNodeData | NoteNodeData | ReviewNodeData
export type CanvasNode = Node<FlowNodeData>

export interface GraphInput {
  project: Project
  videos: Video[]
  scenesByVideo: Record<string, Scene[]>
  characters: Character[]
  layout: CanvasNodeRecord[]
  requests: FlowRequest[]
  runs?: DirectorRun[]
}

export const orientationOf = (v: Video): Orientation => v.orientation ?? 'HORIZONTAL'

export function sceneMedia(s: Scene, o: Orientation) {
  return o === 'VERTICAL'
    ? { imageUrl: s.vertical_image_url, imageStatus: s.vertical_image_status as MediaStatus | null,
        imageMediaId: s.vertical_image_media_id, videoUrl: s.vertical_video_url,
        videoMediaId: s.vertical_video_media_id, videoStatus: s.vertical_video_status as MediaStatus | null }
    : { imageUrl: s.horizontal_image_url, imageStatus: s.horizontal_image_status as MediaStatus | null,
        imageMediaId: s.horizontal_image_media_id, videoUrl: s.horizontal_video_url,
        videoMediaId: s.horizontal_video_media_id, videoStatus: s.horizontal_video_status as MediaStatus | null }
}

/** A root scene with reference assets and no keyframe is filmed reference-to-video (r2v): no image step.
 *  Continuations keep the image chain (EDIT_IMAGE from the parent's frame). */
export type VideoMode = 'refs' | 'image'
/** Directive D1: prompt + asset references unless the user switched the project to image → video. */
export const videoModeOf = (p?: Pick<Project, 'video_mode'> | null): VideoMode => (p?.video_mode === 'image' ? 'image' : 'refs')

/** Is this scene's video made from the reference assets (no image step)? Always, in refs mode. */
export const isRefsScene = (s: Scene, o: Orientation, mode: VideoMode) =>
  mode === 'refs'
  || (s.chain_type !== 'CONTINUATION' && sceneMedia(s, o).imageStatus !== 'COMPLETED' && !!s.character_names?.length)

export const matchesName = (c: Character, n: string) => n === c.name || (!!c.slug && n === c.slug)

function lastError(sceneId: string, requests: FlowRequest[]): string | null {
  // The newest request decides: a failure followed by a fresh attempt is not an error any more.
  const mine = requests
    .filter((r) => r.scene_id === sceneId)
    .sort((a, b) => (b.created_at ?? b.updated_at ?? '').localeCompare(a.created_at ?? a.updated_at ?? '')
      || (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))
  return mine[0]?.status === 'FAILED' ? mine[0].error_message ?? 'Lỗi không rõ' : null
}

const active = (r: FlowRequest) => r.status === 'PENDING' || r.status === 'PROCESSING'

/** How far the run's generation stage is: reference images ("ref:" keys) or clips ("vid:" keys). */
function runProgress(run: DirectorRun, requests: FlowRequest[]): IdeaProgress | null {
  const prefix = run.stage === 'REFS' ? 'ref:' : run.stage === 'VIDEOS' ? 'vid:' : null
  if (!prefix) return null
  const ids = Object.entries(run.plan.requests ?? {}).filter(([k]) => k.startsWith(prefix)).map(([, v]) => v)
  const byId = new Map(requests.map((r) => [r.id, r]))
  const done = ids.filter((id) => ['COMPLETED', 'FAILED'].includes(byId.get(id)?.status ?? '')).length
  return { label: prefix === 'ref:' ? 'Ảnh asset' : 'Video', done, total: ids.length }
}

/** Perf (19/10): an `animated` edge redraws the whole edge layer 60×/s — one such edge cost ~35% CPU on a 55-shot
 * canvas at rest. Running work is shown by a static bright dashed line instead. */
const RUNNING_EDGE = { stroke: '#facc15', strokeWidth: 2.5, strokeDasharray: '8 5' }

export function buildGraph(input: GraphInput, stale: Set<string>) {
  const pos = new Map(input.layout.map((l) => [l.node_key, l]))
  const nodes: CanvasNode[] = []
  const edges: Edge[] = []
  const missingLayout: string[] = []
  const place = (id: string) => {
    const l = pos.get(id)
    if (!l) missingLayout.push(id)
    return { x: l?.x ?? 0, y: l?.y ?? 0 }
  }

  const colors = assetColors(input.characters)
  const allScenes = Object.values(input.scenesByVideo).flat()
  const shotOf = new Map<string, ShotRef>()
  for (const r of input.runs ?? []) {
    const ids = r.plan.ids?.scenes ?? {}
    const hasVideo = (sh: string) => allScenes.some((x) => x.id === ids[sh] && (x.horizontal_video_status === 'COMPLETED' || x.vertical_video_status === 'COMPLETED'))
    for (const [shotId, sceneId] of Object.entries(ids)) {
      const after = chainedShots(r, shotId)
      shotOf.set(sceneId, { runId: r.id, shotId, chained: after.map((x) => x.order),
                            chainedMade: after.filter((x) => hasVideo(x.id)).map((x) => x.order) })
    }
  }
  const assetsOf = (s: Scene): AssetChip[] => (s.character_names ?? []).flatMap((n) => {
    const c = input.characters.find((x) => matchesName(x, n))
    return c ? [{ id: c.id, name: c.name, color: colors.get(c.id)!, url: c.reference_image_url, type: c.entity_type }] : []
  })
  for (const c of input.characters) {
    const id = nodeKey.character(c.id)
    nodes.push({ id, type: 'asset', position: place(id), data: { kind: 'asset', character: c,
            busy: input.requests.some((r) => active(r) && r.character_id === c.id),
            color: colors.get(c.id)!, uses: allScenes.filter((s) => assetsOf(s).some((a) => a.id === c.id)).length } })
  }
  const scriptId = nodeKey.script(input.project.id)
  const parts: ScriptNodeData['parts'] = []
  const scripted = (input.runs ?? []).filter((r) => r.plan.shotlist)
    .sort((a, b) => (a.created_at ?? '').localeCompare(b.created_at ?? '')).at(-1) ?? null
  nodes.push({ id: scriptId, type: 'script', position: place(scriptId), deletable: false,
               data: { kind: 'script', project: input.project, parts, run: scripted,
                       progress: scripted ? runProgress(scripted, input.requests) : null,
                       missingRefs: input.characters.filter((c) => !c.media_id).map((c) => c.name),
                       missingAssets: input.characters.filter((c) => !c.media_id).map((c) => ({ id: c.id, name: c.name })) } })
  for (const run of input.runs ?? []) {
    const iid = nodeKey.idea(run.id)
    nodes.push({ id: iid, type: 'idea', position: place(iid), deletable: false,
                 data: { kind: 'idea', run, reuse: input.characters.filter((c) => c.media_id).map((c) => c.name) } })
    edges.push({ id: `idea:${run.id}`, source: iid, target: scriptId, sourceHandle: 'idea', targetHandle: 'idea',
                 deletable: false, style: run.status === 'RUNNING' ? RUNNING_EDGE : { stroke: '#facc15' } })
  }
  for (const v of input.videos) {
    const scenes = [...(input.scenesByVideo[v.id] ?? [])].sort((a, b) => a.display_order - b.display_order)
    const vid = nodeKey.video(v.id)
    parts.push({ video: v, items: scenes.map((s) => {
      const error = lastError(s.id, input.requests)
      const status: ScriptStatus = input.requests.some((r) => active(r) && r.scene_id === s.id) ? 'busy'
        : sceneMedia(s, orientationOf(v)).videoStatus === 'COMPLETED' ? 'done' : error ? 'failed' : 'todo'
      return { scene: s, status, error }
    }) })
    edges.push({ id: `script:${v.id}`, source: scriptId, target: vid, sourceHandle: 'script', targetHandle: 'script',
                 deletable: false, style: { stroke: '#38bdf8', opacity: 0.6 } })
    const run = (input.runs ?? []).find((r) => r.plan.ids?.video_id === v.id) ?? null
    const directed = run !== null
    nodes.push({ id: vid, type: 'video', position: place(vid), data: { kind: 'video', video: v, scenes, directed,
                 staleIds: scenes.filter((s) => stale.has(s.id)).map((s) => s.id),
                 busyIds: scenes.filter((s) => input.requests.some((r) => active(r) && r.scene_id === s.id)).map((s) => s.id) } })
    const filmUrl = orientationOf(v) === 'VERTICAL' ? v.vertical_url : v.horizontal_url
    if (filmUrl || directed) {
      const fid = nodeKey.final(v.id)
      nodes.push({ id: fid, type: 'final', position: place(fid), deletable: false,
                   data: { kind: 'final', video: v, url: filmUrl ?? null, run,
                           doneScenes: [...scenes].sort((a, b) => a.display_order - b.display_order)
                             .flatMap((sc, i) => sceneMedia(sc, orientationOf(v)).videoStatus === 'COMPLETED' ? [i + 1] : []) } })
      edges.push({ id: `film:${v.id}`, source: vid, target: fid, sourceHandle: 'film', targetHandle: 'film',
                   deletable: false, style: { stroke: '#f59e0b' } })
      if (run && run.plan.shotlist) {
        const rid = nodeKey.review(run.id)
        nodes.push({ id: rid, type: 'review', position: place(rid), deletable: false,
                     data: { kind: 'review', run, video: v, filmReady: Boolean(filmUrl),
                             sceneKeys: Object.fromEntries(Object.entries(run.plan.ids?.scenes ?? {}).map(([sh, sc]) => [sh, nodeKey.scene(sc)])) } })
        edges.push({ id: `review:${v.id}`, source: fid, target: rid, sourceHandle: 'review', targetHandle: 'review', deletable: false, style: { stroke: '#a78bfa' } })
      }
    }
    for (const s of scenes) {
      const sid = nodeKey.scene(s.id)
      nodes.push({
        id: sid, type: 'scene', position: place(sid),
        data: { kind: 'scene', scene: s, video: v, orientation: orientationOf(v), videoMode: videoModeOf(input.project),
                stale: stale.has(s.id), lastError: lastError(s.id, input.requests),
                busy: input.requests.some((r) => active(r) && r.scene_id === s.id), assets: assetsOf(s),
                shot: shotOf.get(s.id) ?? null },
      })
      edges.push({ id: `member:${s.id}->${v.id}`, source: sid, target: vid,
                   sourceHandle: 'member', targetHandle: 'scenes', deletable: false,
                   style: { strokeDasharray: '4 4', opacity: 0.4 } })
      if (s.parent_scene_id) {
        edges.push({ id: `chain:${s.parent_scene_id}->${s.id}`, source: nodeKey.scene(s.parent_scene_id),
                     target: sid, sourceHandle: 'next', targetHandle: 'prev' })
      }
      for (const name of s.character_names ?? []) {
        const c = input.characters.find((x) => matchesName(x, name))
        if (c) edges.push({ id: `ref:${c.id}->${s.id}`, source: nodeKey.character(c.id), target: sid,
                            sourceHandle: 'out', targetHandle: 'refs' })
      }
    }
  }
  for (const l of input.layout) {
    if (l.node_key.startsWith('note:')) {
      nodes.push({ id: l.node_key, type: 'note', position: { x: l.x, y: l.y },
                   data: { kind: 'note', text: String(l.data.text ?? '') } })
    }
  }
  // Directive G1: every box can be resized; its saved size comes back with its position.
  for (const n of nodes) {
    const l = pos.get(n.id)
    const vertical = n.type === 'final' && orientationOf((n.data as FinalNodeData).video) === 'VERTICAL'
    n.width = l?.w ?? (vertical ? 300 : NODE_SIZE[n.type!]?.w)
    if (l?.h) n.height = l.h
    else if (n.type === 'review') n.height = NODE_SIZE.review.h   // the findings scroll inside; the run button stays at the foot
  }
  return { nodes, edges: dedupe(edges), missingLayout }
}

const dedupe = (edges: Edge[]) => [...new Map(edges.map((e) => [e.id, e])).values()]

type ChainShot = { id: string; order: number; continues?: boolean }
/** Continuous film (playbook 09): the scenes after `shotId` that open, one after another, on the frame before. */
export function chainedShots(run: { plan: { brief?: { film_mode?: string } | null; shotlist?: { shots: unknown[] } } }, shotId: string): ChainShot[] {
  if (run.plan.brief?.film_mode !== 'continuous') return []
  const shots = ((run.plan.shotlist?.shots ?? []) as ChainShot[]).slice().sort((a, b) => a.order - b.order)
  const at = shots.findIndex((x) => x.id === shotId)
  const out: ChainShot[] = []
  for (const s of at < 0 ? [] : shots.slice(at + 1)) {
    if (!s.continues) break
    out.push(s)
  }
  return out
}
export const chainedAfter = (run: Parameters<typeof chainedShots>[0], shotId: string) => chainedShots(run, shotId).map((s) => s.order)
