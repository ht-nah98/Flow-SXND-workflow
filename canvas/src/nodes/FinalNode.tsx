import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { NodeFrame } from '../components/NodeFrame'
import { api } from '../api/client'
import type { DirectorRun } from '../api/types'
import { MediaView } from '../components/MediaView'
import { orientationOf, type FinalNodeData } from '../graph/mapping'
import { STAGE_LABEL, ShotFailed, useRunAction } from './RunControls'

const CUT_STAGES = ['CUT', 'PUBLISH', 'RETRO', 'DONE']

/** The finished film of a video — the end of the graph, fed by the video node. */
export function FinalNode({ id, data, selected }: NodeProps<Node<FinalNodeData>>) {
  const { video: v, url, run, doneScenes } = data
  const vertical = orientationOf(v) === 'VERTICAL'
  return (
    <div data-testid={`node-${id}`}
         className={`flex h-full w-full flex-col overflow-y-auto gap-2 rounded-xl border-2 border-amber-500 bg-zinc-900 p-2 shadow-lg`}>
      <NodeFrame selected={selected} minWidth={240} minHeight={180} />
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-semibold text-amber-300">🎞 Phim hoàn chỉnh</span>
        {url && v.duration != null && <span className="text-zinc-400">{v.duration.toFixed(1)}s</span>}
      </div>
      <div className="truncate text-[11px] text-zinc-300">{v.title}</div>
      {url ? <MediaView url={url} kind="video" vertical={vertical} /> : run && <FilmPending run={run} done={doneScenes} />}
      {url && run && <Recut run={run} />}
      <Handle type="target" position={Position.Left} id="film" className="!h-3 !w-3 !bg-amber-400" isConnectable={false} />
      <Handle type="source" position={Position.Right} id="review" className="!h-3 !w-3 !bg-violet-400" isConnectable={false} />
    </div>
  )
}

function FilmPending({ run, done }: { run: DirectorRun; done?: number[] }) {
  const { busy, act } = useRunAction(run)
  const cutting = CUT_STAGES.includes(run.stage)
  // 22/10: the run was cancelled at REFS, the user made all 6 clips by hand and found no way to make the film.
  const shots = run.plan.shotlist?.shots.length ?? 0
  const allMade = shots > 0 && (done?.length ?? 0) >= shots
  return (
    <div className="nodrag flex flex-col gap-1 text-[11px] text-zinc-300">
      <div className={`flex ${orientationLabel(run)} items-center justify-center rounded bg-zinc-800 text-zinc-500`}>🎬</div>
      {run.gate === 'SHOT_FAILED' ? <ShotFailed run={run} done={done} /> : run.status === 'FAILED' && cutting ? (
        <>
          <div className="rounded bg-red-950 px-2 py-1 text-red-200">⚠️ Ghép phim lỗi: {run.error}</div>
          <button disabled={busy} className="rounded bg-amber-700 px-2 py-1 disabled:opacity-40"
                  onClick={() => void act(() => api.retryRun(run.id))}>
            🎬 Ghép lại phim (không tốn credit)
          </button>
        </>
      ) : allMade && run.status !== 'RUNNING' ? (
        <button disabled={busy} className="rounded bg-emerald-700 px-2 py-1 disabled:opacity-40"
                title="Ghép từ bản đang chọn của từng cảnh; chỉ ffmpeg, không tốn credit"
                onClick={() => void act(() => api.recutRun(run.id))}>
          🎬 Ghép phim từ {shots} clip (miễn phí)
        </button>
      ) : (
        <span>{cutting && run.status === 'RUNNING' ? `⏳ ${STAGE_LABEL[run.stage] ?? run.stage}`
               : 'Phim sẽ hiện ở đây sau khi tạo xong các clip — hệ thống tự cắt và ghép.'}</span>
      )}
    </div>
  )
}

const orientationLabel = (run: DirectorRun) => (run.brief.orientation === 'VERTICAL' ? 'aspect-[9/16] max-h-40' : 'aspect-video')

/** After a clip was regenerated or another take was picked: cut the film again from the current takes. */
function Recut({ run }: { run: DirectorRun }) {
  const { busy, act } = useRunAction(run)
  if (run.status === 'RUNNING' && run.stage === 'CUT') return <span className="text-[11px] text-sky-300">⏳ Đang dựng lại phim…</span>
  if (run.status === 'FAILED' && CUT_STAGES.includes(run.stage)) return <FilmPending run={run} />
  if (run.status !== 'DONE') return null
  return (
    <button disabled={busy} className="nodrag rounded bg-zinc-700 px-2 py-1 text-[11px] disabled:opacity-40"
            title="Dùng bản đang chọn của từng cảnh; chỉ ffmpeg, không tốn credit"
            onClick={() => void act(() => api.recutRun(run.id))}>
      🎬 Dựng lại phim từ các bản đang chọn (miễn phí)
    </button>
  )
}
