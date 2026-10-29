import { Handle, Position, useReactFlow, type Node, type NodeProps } from '@xyflow/react'
import { NodeFrame } from '../components/NodeFrame'
import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useMaterials } from '../api/queries'
import { useCanvasActions } from '../canvas/actions-context'
import { EditEffects } from '../components/EditEffects'
import { InlineEdit } from '../components/InlineEdit'
import { nodeKey } from '../graph/keys'
import { NODE_SIZE } from '../graph/layout'
import { videoModeOf, type ScriptItem, type ScriptNodeData, type ScriptStatus, type VideoMode } from '../graph/mapping'
import { RunControls, ScriptSummary } from './RunControls'
import { StorySpine, clock } from '../components/StorySpine'
import { ScriptPackageButton } from '../components/ScriptPackage'
import { MoveAccount } from '../components/FlowAccounts'

const STATUS: Record<ScriptStatus, { icon: string; label: string }> = {
  todo: { icon: '○', label: 'Chưa tạo' },
  busy: { icon: '⏳', label: 'Đang tạo' },
  done: { icon: '🎬', label: 'Đã có video' },
  failed: { icon: '⚠️', label: 'Lỗi' },
}

/** Scene titles carry the material's style prefix ("Real RAW photograph, …") — noise when reading the script. */
export const sceneTitle = (prompt: string | null, prefix?: string | null) => {
  const t = (prefix && prompt?.startsWith(prefix) ? prompt.slice(prefix.length) : prompt ?? '').trim()
  return t || '(chưa có tiêu đề)'
}

const seconds = (items: ScriptItem[]) => items.reduce((t, i) => t + (i.scene.duration ?? 0), 0)

/** The project's script: synopsis + every clip in order, the first thing to read on a canvas. */
export function ScriptNode({ id, data, selected, height }: NodeProps<Node<ScriptNodeData>>) {
  const a = useCanvasActions()
  const rf = useReactFlow()
  const [reading, setReading] = useState(false)
  const { project: p, parts, run, progress, missingRefs, missingAssets = [] } = data
  const prefix = useMaterials().data?.find((m) => m.id === p.material)?.scene_prefix
  const count = parts.reduce((t, x) => t + x.items.length, 0)

  const jumpTo = (key: string, size: { w: number; h: number }) => {
    const n = rf.getNode(key)
    if (!n) return
    rf.setNodes((ns) => ns.map((x) => ({ ...x, selected: x.id === key })))
    void rf.setCenter(n.position.x + size.w / 2, n.position.y + size.h / 3, { zoom: 0.9, duration: 400 })
  }
  const jump = (sceneId: string) => {
    const n = rf.getNode(nodeKey.scene(sceneId))
    if (n) void rf.setCenter(n.position.x + NODE_SIZE.scene.w / 2, n.position.y + NODE_SIZE.scene.h / 2, { zoom: 0.9, duration: 400 })
  }

  return (
    <div data-testid={`node-${id}`} className="@container flex h-full w-full flex-col gap-2 overflow-hidden rounded-xl border-2 border-sky-600 bg-zinc-900 p-2 shadow-lg">
      <NodeFrame selected={selected} minWidth={300} minHeight={200} />
      {/* 20/10: the gate buttons sat at the very bottom of a box that scrolled inside while the wheel zoomed the
          canvas — the user could not find "make images / make videos". The content scrolls; the controls stay. */}
      <div className="nowheel flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-semibold text-sky-300">📜 Kịch bản
          {p.flow_account && <span className="ml-1 font-normal text-zinc-400" title="Tài khoản Google chứa phim này">· 👤 {p.flow_account.split('@')[0]}</span>}
          {' '}<MoveAccount projectId={p.id} current={p.flow_account} />
        </span>
        <span className="text-zinc-400">{count} clip</span>
      </div>
      <VideoModeToggle mode={videoModeOf(p)} directed={!!run} onChange={(m) => void a.patchProject({ video_mode: m })} />
      {run && <ScriptSummary run={run} />}
      <StorySpine story={run?.plan.story} compact />
      <InlineEdit label="Tóm tắt câu chuyện" value={p.story} updatedAt={p.updated_at}
                  placeholder="Câu chuyện kể gì: mở đầu, bước ngoặt, kết thúc…"
                  onSave={(t) => a.patchProject({ story: t })} />
      {parts.map(({ video: v, items }) => (
        <div key={v.id} className="flex flex-col gap-1">
          {parts.length > 1 && <div className="text-[10px] uppercase text-zinc-400">{v.title}</div>}
          {/* Wider box → more columns (directive G1: read the script across, not down one narrow column). */}
          <ol className={`nodrag nowheel grid grid-cols-1 gap-1 overflow-y-auto text-[11px] @2xl:grid-cols-2 @5xl:grid-cols-3 @7xl:grid-cols-4 ${height ? '' : 'max-h-[380px]'}`}>
            {items.map((it, i) => (
              <li key={it.scene.id}>
                <button onClick={() => jump(it.scene.id)} title={it.error ?? STATUS[it.status].label}
                        className="flex w-full items-start gap-1 rounded bg-zinc-800 px-1.5 py-1 text-left hover:bg-zinc-700">
                  <span className="w-5 shrink-0 text-zinc-400">{i + 1}.</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{sceneTitle(it.scene.prompt, prefix)}</span>
                    <span className="block truncate text-[10px] text-zinc-400">
                      {it.scene.duration ? `${it.scene.duration}s · ` : ''}{(it.scene.character_names ?? []).join(', ') || 'không có ảnh tham chiếu'}
                    </span>
                  </span>
                  <span className="shrink-0" aria-label={STATUS[it.status].label}>{STATUS[it.status].icon}</span>
                </button>
              </li>
            ))}
          </ol>
        </div>
      ))}
      <div className="flex gap-1 [&>*]:flex-1">
        <button className="nodrag rounded bg-zinc-700 px-2 py-1 text-[11px]" onClick={() => setReading(true)}>📖 Đọc toàn bộ kịch bản (màn hình rộng)</button>
        {run?.plan.shotlist && <ScriptPackageButton run={run} />}
        {run?.plan.shotlist && <EditEffects run={run} />}
      </div>
      </div>
      {run && (
        <div data-testid="script-controls" className="nowheel max-h-[55%] shrink-0 overflow-y-auto border-t border-zinc-700 pt-2">
          {missingAssets.length > 0 && (
            <div className="mb-1 flex flex-wrap items-center gap-1 rounded bg-amber-950 px-2 py-1 text-[11px] text-amber-200">
              🖼 Chưa có ảnh (bấm để tới node, xem prompt ảnh, bấm Gen ảnh):
              {missingAssets.map((m) => (
                <button key={m.id} className="nodrag rounded bg-amber-800 px-1.5 text-amber-50 hover:bg-amber-700"
                        onClick={() => jumpTo(nodeKey.character(m.id), NODE_SIZE.asset)}>{m.name}</button>
              ))}
            </div>
          )}
          <RunControls run={run} progress={progress} missingRefs={missingRefs}
                       doneScenes={(parts[0]?.items ?? []).flatMap((it, i) => (it.status === 'done' ? [i + 1] : []))} />
        </div>
      )}
      <Handle type="source" position={Position.Right} id="script" className="!h-3 !w-3 !bg-sky-400" isConnectable={false} />
      <Handle type="target" position={Position.Top} id="idea" className="!h-3 !w-3 !bg-yellow-400" isConnectable={false} />
      {reading && createPortal(<ScriptReader data={data} prefix={prefix} onClose={() => setReading(false)} />, document.body)}
    </div>
  )
}

function ScriptReader({ data, prefix, onClose }: { data: ScriptNodeData; prefix?: string | null; onClose: () => void }) {
  // Directive G1: read the script across the screen (one row per clip); "Đọc dọc" keeps the old page layout.
  const [wide, setWide] = useState(true)
  return (
    <div role="dialog" aria-label="Kịch bản" className="fixed inset-0 z-50 flex justify-center bg-black/70 p-4" onClick={onClose}>
      <article className={`flex w-full ${wide ? 'max-w-[96vw]' : 'max-w-3xl'} flex-col gap-4 overflow-y-auto rounded-xl bg-zinc-900 p-6 text-sm text-zinc-200`}
               onClick={(e) => e.stopPropagation()}>
        <header className="flex items-start justify-between gap-4">
          <h1 className="text-lg font-semibold">📜 {data.project.name}</h1>
          <span className="flex gap-1">
            <button onClick={() => setWide((w) => !w)} className="rounded bg-zinc-800 px-2 py-1">
              {wide ? '↕ Đọc dọc' : '↔ Bảng ngang'}
            </button>
            <button onClick={onClose} className="rounded bg-zinc-800 px-2 py-1">Đóng</button>
          </span>
        </header>
        <div className={wide ? 'grid grid-cols-1 gap-4 lg:grid-cols-2' : 'flex flex-col gap-4'}>
          <StorySpine story={data.run?.plan.story} />
          <div className="flex flex-col gap-3">
            <p className="whitespace-pre-wrap text-zinc-300">{data.project.story || 'Chưa có tóm tắt câu chuyện.'}</p>
            <StoryPeople story={data.run?.plan.story} />
          </div>
        </div>
        {data.parts.map(({ video: v, items }) => (
          <section key={v.id} className="flex flex-col gap-4">
            <h2 className="border-b border-zinc-700 pb-1 font-semibold">
              {v.title} · {items.length} clip{seconds(items) ? ` · ${seconds(items)}s nguồn` : ''}
            </h2>
            {wide ? (
              <table className="w-full table-fixed border-collapse text-left text-[13px]">
                <thead className="text-xs text-zinc-400">
                  <tr>
                    <th className="w-10 p-2">#</th><th className="w-1/5 p-2">Ý tưởng shot</th><th className="w-1/6 p-2">Asset</th>
                    <th className="p-2">Prompt video</th><th className="w-28 p-2">Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, i) => (
                    <tr key={it.scene.id} className="border-t border-zinc-800 align-top">
                      <td className="p-2 text-zinc-400">{i + 1}</td>
                      <td className="p-2 font-semibold">{sceneTitle(it.scene.prompt, prefix)}</td>
                      <td className="p-2 text-xs text-zinc-400">
                        {(it.scene.character_names ?? []).join(', ') || '—'}{it.scene.duration ? ` · ${it.scene.duration}s` : ''}
                      </td>
                      <td className="whitespace-pre-wrap p-2 leading-relaxed">{it.scene.video_prompt || '(chưa có prompt)'}</td>
                      <td className="p-2 text-xs">
                        {STATUS[it.status].icon} {STATUS[it.status].label}
                        {it.error && <div className="text-red-300">{it.error}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : items.map((it, i) => (
              <div key={it.scene.id} className="flex flex-col gap-1">
                <h3 className="font-semibold">
                  {i + 1}. {sceneTitle(it.scene.prompt, prefix)}{' '}
                  <span className="text-xs font-normal text-zinc-400">{STATUS[it.status].icon} {STATUS[it.status].label}</span>
                </h3>
                <div className="text-xs text-zinc-400">
                  Ảnh tham chiếu: {(it.scene.character_names ?? []).join(', ') || '—'}
                  {it.scene.duration ? ` · ${it.scene.duration}s` : ''}
                </div>
                <p className="whitespace-pre-wrap text-[13px] leading-relaxed">{it.scene.video_prompt || '(chưa có prompt)'}</p>
                {it.error && <p className="text-xs text-red-300">Lỗi gần nhất: {it.error}</p>}
              </div>
            ))}
          </section>
        ))}
      </article>
    </div>
  )
}

/** Acts with their place in the film and characters with who they are (SciCloud sample, 19/10). */
function StoryPeople({ story }: { story?: NonNullable<ScriptNodeData['run']>['plan']['story'] }) {
  const acts = story?.sequences ?? []
  const people = (story?.cast ?? []).filter((c) => c.entity_type === 'character')
  if (!acts.length && !people.length) return null
  return (
    <div className="flex flex-col gap-2 text-[13px]">
      {acts.length > 0 && (
        <ol className="flex flex-col gap-0.5">
          {acts.map((a) => (
            <li key={a.id}>
              <span className="text-zinc-400">{a.start_s != null && a.end_s != null ? `${clock(a.start_s)}–${clock(a.end_s)} · ` : ''}Màn {a.act}</span>{' '}
              <span className="font-semibold">{a.title}</span> <span className="text-zinc-400">— {a.purpose}</span>
            </li>
          ))}
        </ol>
      )}
      {people.length > 0 && (
        <ul className="flex flex-col gap-1">
          {people.map((c) => (
            <li key={c.name}>
              <span className="font-semibold text-sky-300">{c.name}</span>
              {c.personality && <span className="text-zinc-300"> — {c.personality}</span>}
              {c.signature && <span className="block text-xs text-zinc-500">Động tác đặc trưng: {c.signature}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Directive D1: videos come from prompt + asset references. Image → video is an opt-in for hand-made projects;
 *  an AI-director film is always prompt + assets. */
export function VideoModeToggle({ mode, directed, onChange }: {
  mode: VideoMode; directed: boolean; onChange: (m: VideoMode) => void
}) {
  // 23/10: this read "prompt + asset" for every directed film, keyframe films too — the mode decides the words
  if (directed) return <div className="text-[10px] text-zinc-400">{mode === 'image'
    ? '🖼 Video từ ảnh keyframe (ảnh chốt trước → video)'
    : '🎬 Video từ prompt + asset (không tạo ảnh trước)'}</div>
  const btn = (m: VideoMode, label: string) => (
    <button onClick={() => mode !== m && onChange(m)} aria-pressed={mode === m}
            className={`rounded px-1.5 py-0.5 ${mode === m ? 'bg-sky-700 text-white' : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'}`}>
      {label}
    </button>
  )
  return (
    <div className="nodrag flex items-center gap-1 text-[10px]">
      <span className="text-zinc-400">Cách làm video:</span>
      {btn('refs', '🎬 Prompt + asset')}
      {btn('image', '🖼 Ảnh → video')}
    </div>
  )
}
