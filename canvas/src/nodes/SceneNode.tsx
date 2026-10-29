import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { useState } from 'react'
import type { SceneReview } from '../api/types'
import { NodeFrame } from '../components/NodeFrame'
import { useCanvasActions } from '../canvas/actions-context'
import { ErrorBadge } from '../components/ErrorBadge'
import { InlineEdit } from '../components/InlineEdit'
import { MediaView } from '../components/MediaView'
import { ReviewPanel } from '../components/ReviewPanel'
import { VersionStrip } from '../components/VersionStrip'
import { AssetChips } from '../components/AssetChips'
import { RewriteClip } from '../components/RewriteClip'
import { useCompact } from '../canvas/zoom'
import { isRefsScene, sceneMedia, type SceneNodeData } from '../graph/mapping'
import { sceneTitle } from './ScriptNode'

/** The border tells the clip's state; colours on wires and chips belong to assets only. */
export const STATUS_RING = {
  done: 'border-emerald-500', busy: 'border-sky-400 border-dashed', failed: 'border-red-500',
  stale: 'border-amber-400', todo: 'border-zinc-700',
} as const
export const STATUS_TEXT = { done: '✅ Có video', busy: '⏳ Đang tạo', failed: '⚠️ Lỗi', stale: '↻ Cần tạo lại', todo: '· Chưa có video' }

export function sceneStatus(d: Pick<SceneNodeData, 'busy' | 'lastError' | 'stale' | 'scene' | 'orientation'>) {
  const v = sceneMedia(d.scene, d.orientation).videoStatus
  return d.busy ? 'busy' : d.lastError || v === 'FAILED' ? 'failed' : d.stale ? 'stale' : v === 'COMPLETED' ? 'done' : 'todo'
}

export function SceneNode({ id, data, selected }: NodeProps<Node<SceneNodeData>>) {
  const { scene: s } = data
  const m = sceneMedia(s, data.orientation)
  const status = sceneStatus(data)
  const compact = useCompact()
  const handles = (
    <>
      <Handle type="target" position={Position.Left} id="refs" style={{ top: 40 }} className="!h-3 !w-3 !bg-sky-400" />
      <Handle type="target" position={Position.Left} id="prev" style={{ top: 120 }} className="!h-3 !w-3 !bg-violet-400" />
      <Handle type="source" position={Position.Right} id="next" style={{ top: 120 }} className="!h-3 !w-3 !bg-violet-400" />
      <Handle type="source" position={Position.Bottom} id="member" className="!opacity-0" isConnectable={false} />
    </>
  )
  if (compact) {
    // Zoomed out: the picture, the assets it uses and its state — readable from afar.
    return (
      <div data-testid={`node-${id}`} className={`flex h-full w-full flex-col overflow-y-auto gap-2 rounded-xl border-4 bg-zinc-900 p-2 ${STATUS_RING[status]}`}>
        <NodeFrame selected={selected} minWidth={260} minHeight={200} />
        <div className="truncate text-2xl font-bold">{s.display_order + 1}. {sceneTitle(s.prompt)}</div>
        <MediaView url={m.videoUrl ?? m.imageUrl} kind={m.videoUrl ? 'video' : 'image'} vertical={data.orientation === 'VERTICAL'} />
        <AssetChips assets={data.assets} size="lg" />
        {handles}
      </div>
    )
  }
  return (
    <div data-testid={`node-${id}`}
         className={`flex h-full w-full flex-col overflow-y-auto gap-2 rounded-xl border-2 bg-zinc-900 p-2 shadow ${STATUS_RING[status]}`}>
      <NodeFrame selected={selected} minWidth={260} minHeight={200} />
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-semibold">Cảnh {s.display_order + 1}</span>
        <span className="flex gap-1">
          {data.stale && <span className="rounded bg-amber-500/20 px-1.5 text-amber-300">cần tạo lại</span>}
          <span className="rounded bg-zinc-800 px-1.5 text-zinc-400">{s.chain_type === 'CONTINUATION' ? 'nối tiếp' : 'gốc'}</span>
        </span>
      </div>
      <SceneBody data={data} />
      {handles}
    </div>
  )
}


/** Everything a scene shows and does — on its canvas node and in the Storyboard's detail panel (22/10), so both
 *  offer the same tools: media, prompts, generate, versions, rewrite, review. */
export function SceneBody({ data }: { data: SceneNodeData }) {
  const a = useCanvasActions()
  const [fromReview, setFromReview] = useState<SceneReview | null>(null)   // "Claude viết lại theo đánh giá"
  const { scene: s, video, orientation } = data
  const m = sceneMedia(s, orientation)
  const imageMode = data.videoMode === 'image'  // opt-in per project; default is prompt + assets (directive D1)
  const refs = isRefsScene(s, orientation, data.videoMode)  // r2v: the video is made from the reference assets
  const noAssets = refs && !data.assets.length
  const videoLabel = m.videoStatus === 'COMPLETED' ? 'Gen lại video'
    : data.lastError || m.videoStatus === 'FAILED' ? 'Tạo lại video' : 'Tạo video'
  const promptField = s.image_prompt ? 'image_prompt' : 'prompt'
  return (
    <>
      <AssetChips assets={data.assets} />
      <ErrorBadge error={data.lastError} />
      {!refs && <MediaView url={m.imageUrl} kind="image" vertical={data.orientation === 'VERTICAL'} busy={data.busy && m.imageStatus !== 'COMPLETED'} />}
      {(refs || m.videoUrl || m.imageStatus === 'COMPLETED') && (
        <MediaView url={m.videoUrl} kind="video" vertical={data.orientation === 'VERTICAL'} busy={data.busy && (refs || m.imageStatus === 'COMPLETED')} />
      )}
      {imageMode
        ? <InlineEdit label="Prompt ảnh" value={s[promptField]} updatedAt={s.updated_at}
                      onSave={(v) => a.patchScene(s.id, { [promptField]: v })} />
        : <InlineEdit label="Ý tưởng shot" value={s.prompt} updatedAt={s.updated_at}
                      onSave={(v) => a.patchScene(s.id, { prompt: v })} />}
      <InlineEdit label="Prompt video" value={s.video_prompt} updatedAt={s.updated_at}
                  onSave={(v) => a.patchScene(s.id, { video_prompt: v })} />
      <div className="nodrag flex flex-wrap gap-1">
        {!refs && (
          <button disabled={!a.canGenerate || data.busy} className="rounded bg-sky-700 px-2 py-1 text-[11px] disabled:opacity-40"
                  onClick={() => void a.run({ kind: 'scene-image', scene: s, video })}>
            {m.imageStatus === 'COMPLETED' ? 'Gen lại ảnh' : 'Gen ảnh'}
          </button>
        )}
        <button disabled={!a.canGenerate || data.busy || noAssets || (!refs && m.imageStatus !== 'COMPLETED')}
                title={noAssets ? 'Gắn asset (nhân vật / bối cảnh) vào cảnh trước' : undefined}
                className="rounded bg-violet-700 px-2 py-1 text-[11px] disabled:opacity-40"
                onClick={() => void a.run({ kind: 'scene-video', scene: s, video })}>
          {videoLabel}
        </button>
        {refs && <span className="self-center text-[10px] text-zinc-500">
          {noAssets ? '⚠️ chưa gắn asset' : '🎬 prompt + asset'}</span>}
      </div>
      {imageMode && <VersionStrip target={{ kind: 'scene', id: s.id, media: 'image', orientation }} currentMediaId={m.imageMediaId} />}
      <VersionStrip target={{ kind: 'scene', id: s.id, media: 'video', orientation }} currentMediaId={m.videoMediaId} />
      {data.shot && <RewriteClip runId={data.shot.runId} shotId={data.shot.shotId} projectId={video.project_id}
                                 review={fromReview} chained={data.shot.chained} chainedMade={data.shot.chainedMade} />}
      <ReviewPanel scene={s} hasVideo={m.videoStatus === 'COMPLETED'} onRewrite={data.shot ? setFromReview : undefined} />
    </>
  )
}
