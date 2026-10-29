import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { NodeFrame } from '../components/NodeFrame'
import { useCanvasActions } from '../canvas/actions-context'
import { InlineEdit } from '../components/InlineEdit'
import { orientationOf, sceneMedia, type VideoNodeData } from '../graph/mapping'

export function VideoNode({ id, data, selected }: NodeProps<Node<VideoNodeData>>) {
  const a = useCanvasActions()
  const { video: v, scenes } = data
  const o = orientationOf(v)
  const finalUrl = o === 'VERTICAL' ? v.vertical_url : v.horizontal_url
  const busy = new Set(data.busyIds)
  const stale = new Set([...data.staleIds].filter((id) => !busy.has(id)))
  const missing = scenes.filter((s) => !busy.has(s.id) && sceneMedia(s, o).videoStatus !== 'COMPLETED').length
  return (
    <div data-testid={`node-${id}`} className="flex h-full w-full flex-col overflow-y-auto gap-2 rounded-xl border border-emerald-700 bg-zinc-900 p-2 shadow">
      <NodeFrame selected={selected} minWidth={220} minHeight={160} />
      <div className="text-[10px] uppercase text-emerald-300">Video · {o === 'VERTICAL' ? 'Dọc 9:16' : 'Ngang 16:9'}</div>
      <InlineEdit single label="Tiêu đề" value={v.title} updatedAt={v.updated_at} onSave={(t) => a.patchVideo(v.id, { title: t })} />
      <ol className="nodrag flex flex-col gap-1 text-[11px]">
        {scenes.map((s, i) => (
          <li key={s.id} className="flex items-center gap-1 rounded bg-zinc-800 px-1.5 py-1">
            <span className="w-5 text-zinc-400">{i + 1}.</span>
            <span className="flex-1 truncate">{s.prompt || '(chưa có prompt)'}</span>
            {sceneMedia(s, o).videoStatus === 'COMPLETED' ? '🎬' : '·'}
            <button aria-label="Lên" disabled={i === 0} onClick={() => void a.moveScene(v, scenes, s.id, -1)} className="px-1 disabled:opacity-30">↑</button>
            <button aria-label="Xuống" disabled={i === scenes.length - 1} onClick={() => void a.moveScene(v, scenes, s.id, 1)} className="px-1 disabled:opacity-30">↓</button>
          </li>
        ))}
      </ol>
      {data.directed && (
        <div className="rounded bg-zinc-800 px-2 py-1 text-[11px] text-zinc-300">
          🎬 Clip của phim này do node 📜 Kịch bản tạo và dựng (đủ ảnh nhân vật, bối cảnh trước khi tạo video).
        </div>
      )}
      {!data.directed && <div className="nodrag flex flex-col gap-1">
        <button disabled={!a.canGenerate || missing === 0} className="rounded bg-violet-700 px-2 py-1 text-[11px] disabled:opacity-40"
                onClick={() => void a.run({ kind: 'video-missing', video: v, scenes, busy })}>
          Tạo tất cả cảnh còn thiếu ({missing})
        </button>
        {stale.size > 0 && (
          <button disabled={!a.canGenerate} className="rounded bg-amber-700 px-2 py-1 text-[11px] disabled:opacity-40"
                  onClick={() => void a.run({ kind: 'video-stale', video: v, scenes, stale, busy })}>
            Tạo lại các cảnh bị ảnh hưởng ({stale.size})
          </button>
        )}
        <button disabled={scenes.length === 0} className="rounded bg-emerald-700 px-2 py-1 text-[11px] disabled:opacity-40"
                onClick={() => void a.concat(v)}>Ghép video</button>
      </div>}
      {finalUrl && <div className="text-[11px] text-amber-300">🎞 Đã có phim hoàn chỉnh →</div>}
      <Handle type="target" position={Position.Left} id="scenes" className="!opacity-0" isConnectable={false} />
      <Handle type="target" position={Position.Top} id="script" className="!h-3 !w-3 !bg-sky-400" isConnectable={false} />
      <Handle type="source" position={Position.Right} id="film" className="!h-3 !w-3 !bg-amber-400" isConnectable={false} />
    </div>
  )
}
