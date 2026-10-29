import { useState } from 'react'
import { Handle, Position, useReactFlow, type Node, type NodeProps } from '@xyflow/react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { FilmReviewEntry, ReviewFinding, ReviewLayer } from '../api/types'
import { NodeFrame } from '../components/NodeFrame'
import { useToast } from '../components/Toast'
import { explainError } from '../lib/errors'
import { NODE_SIZE } from '../graph/layout'
import type { ReviewNodeData } from '../graph/mapping'

export const LAYER_LABEL: Record<ReviewLayer, string> = {
  story: 'Kịch bản', clips: 'Từng clip', continuity: 'Nối cảnh', edit: 'Dựng',
}
const SEV = {
  CRITICAL: { label: 'Nghiêm trọng', chip: 'bg-red-800 text-red-100', dot: 'bg-red-500' },
  HIGH: { label: 'Rõ', chip: 'bg-amber-800 text-amber-100', dot: 'bg-amber-400' },
  MINOR: { label: 'Nhỏ', chip: 'bg-zinc-700 text-zinc-200', dot: 'bg-zinc-400' },
} as const
const CAUSE: Record<string, string> = {
  prompt: 'câu chữ prompt', asset: 'ảnh asset', blocking: 'hành động không làm được', script: 'kịch bản',
  edit: 'dựng/cắt', model_limit: 'giới hạn mô hình', policy: 'bộ lọc Flow', other: 'khác',
}
const ACTION: Record<string, string> = {
  rewrite_prompt: '✏️ Viết lại prompt (miễn phí)', regen_video: '🎬 Tạo lại video (≈15 credit)',
  add_asset: '🖼 Thêm asset (≈1 credit)', revise_script: '📜 Sửa kịch bản', edit_cut: '✂️ Cắt/dựng lại (miễn phí)',
  add_lesson: '📚 Thêm bài học', none: '—',
}
const fmt = (t: number | null) => (t == null ? '' : `${Math.floor(t / 60)}:${(t % 60).toFixed(0).padStart(2, '0')}`)

/** Agent Review (21/10): the cut film judged as a whole — script, each clip, the seams, root causes. User-triggered,
 *  Claude only (no Flow credit). Findings jump to their scene node; fixing them is step 3. */
export function ReviewNode({ id, data, selected }: NodeProps<Node<ReviewNodeData>>) {
  const { run, filmReady, sceneKeys } = data
  const qc = useQueryClient()
  const toast = useToast()
  const rf = useReactFlow()
  const key = ['p', run.project_id, 'film-review', run.id]
  const q = useQuery({
    queryKey: key, queryFn: () => api.filmReviews(run.id),
    refetchInterval: (query) => (query.state.data?.job?.status === 'RUNNING' ? 5000 : false),
  })
  const [note, setNote] = useState('')
  const [pick, setPick] = useState(0)
  const [open, setOpen] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const job = q.data?.job ?? null
  const running = job?.status === 'RUNNING'
  const reviews = q.data?.reviews ?? []
  const r: FilmReviewEntry | undefined = reviews[Math.min(pick, reviews.length - 1)]

  const start = async () => {
    setBusy(true)
    try {
      await api.startFilmReview(run.id, note)
      setNote(''); setPick(0)
      await qc.invalidateQueries({ queryKey: key })
    } catch (e) { toast(explainError(e instanceof Error ? e.message : String(e)).message, 'error') }
    finally { setBusy(false) }
  }
  const jump = (f: ReviewFinding) => {
    setOpen(f.id)
    const k = f.shot_id ? sceneKeys[f.shot_id] : undefined
    const n = k ? rf.getNode(k) : undefined
    if (!n) return
    rf.setNodes((ns) => ns.map((x) => ({ ...x, selected: x.id === k })))
    void rf.setCenter(n.position.x + NODE_SIZE.scene.w / 2, n.position.y + NODE_SIZE.scene.h / 3, { zoom: 0.9, duration: 400 })
  }

  return (
    <div data-testid={`node-${id}`}
         className="flex h-full w-full flex-col gap-2 rounded-xl border-2 border-violet-500 bg-zinc-900 p-2 text-[11px] text-zinc-200 shadow-lg">
      <NodeFrame selected={selected} minWidth={360} minHeight={240} />
      <Handle type="target" position={Position.Left} id="review" className="!h-3 !w-3 !bg-violet-400" isConnectable={false} />
      <div className="flex items-center justify-between">
        <span className="font-semibold text-violet-300">🔍 Đánh giá phim (Agent Review)</span>
        {reviews.length > 1 && (
          <select aria-label="Chọn lần đánh giá" className="nodrag rounded bg-zinc-800 px-1 text-[10px]" value={pick}
                  onChange={(e) => { setPick(Number(e.target.value)); setOpen(null) }}>
            {reviews.map((x, i) => <option key={x.id} value={i}>{i === 0 ? 'Mới nhất' : `Lần trước ${i}`} · {x.created_at.slice(5, 16).replace('T', ' ')}</option>)}
          </select>
        )}
      </div>

      <div className="nowheel nodrag min-h-0 flex-1 overflow-y-auto pr-1">
        {running && <div className="mb-2 rounded bg-violet-950 px-2 py-1 text-violet-200">⏳ Agent đang xem phim, từng clip và từng chỗ nối… (thường 4–6 phút)</div>}
        {job?.status === 'FAILED' && <div className="mb-2 rounded bg-red-950 px-2 py-1 text-red-200">⚠️ Đánh giá lỗi: {job.error}</div>}
        {!r && !running && <div className="text-zinc-400">Chưa có đánh giá. Agent xem cả phim, chấm 4 tầng (kịch bản, từng clip, nối cảnh, dựng), tìm gốc lỗi và đề xuất cách sửa.</div>}
        {r && <Report r={r} open={open} setOpen={setOpen} jump={jump} />}
      </div>

      <div className="flex shrink-0 flex-col gap-1 border-t border-zinc-700 pt-2" data-testid="review-controls">
        <textarea aria-label="Góp ý cho agent" rows={2} value={note} onChange={(e) => setNote(e.target.value)}
                  placeholder="Góp ý của anh (không bắt buộc), ví dụ: giây 14 cái bình thành nồi"
                  className="nodrag nowheel resize-none rounded bg-zinc-800 px-2 py-1 text-[11px]" />
        <button disabled={busy || running || !filmReady} onClick={() => void start()}
                className="nodrag rounded bg-violet-700 px-2 py-1 disabled:opacity-40"
                title={filmReady ? 'Chỉ tốn lượt Claude, không tốn credit Flow' : 'Ghép phim trước rồi mới đánh giá được'}>
          {running ? '⏳ Đang đánh giá…' : r ? '🔍 Đánh giá lại phim (chỉ tốn lượt Claude)' : '🔍 Đánh giá phim (chỉ tốn lượt Claude)'}
        </button>
      </div>
    </div>
  )
}

function Report({ r, open, setOpen, jump }: {
  r: FilmReviewEntry; open: string | null; setOpen: (id: string | null) => void; jump: (f: ReviewFinding) => void
}) {
  const dur = Math.max(r.film_duration_s, 1)
  return (
    <div className="flex flex-col gap-2">
      {r.note && <div className="text-zinc-400">Góp ý đã gửi: “{r.note}”</div>}
      <div className="leading-snug">{r.summary}</div>
      <div className="grid grid-cols-2 gap-1" data-testid="review-scores">
        {r.scores.map((s) => (
          <div key={s.layer} className="rounded bg-zinc-800 px-2 py-1" title={s.note}>
            <div className="flex justify-between"><span>{LAYER_LABEL[s.layer]}</span>
              <span className={s.score >= 7 ? 'text-emerald-300' : s.score >= 5 ? 'text-amber-300' : 'text-red-300'}>{s.score}/10</span></div>
            <div className="mt-0.5 h-1 rounded bg-zinc-700"><div className="h-1 rounded bg-violet-400" style={{ width: `${s.score * 10}%` }} /></div>
            <div className="mt-0.5 line-clamp-2 text-[10px] text-zinc-400">{s.note}</div>
          </div>
        ))}
      </div>

      <div data-testid="review-timeline">
        <div className="relative h-5 rounded bg-zinc-800">
          {r.clips.map((c) => (
            <div key={c.shot_id} className="absolute top-0 h-5 border-l border-zinc-600 text-[9px] text-zinc-500"
                 style={{ left: `${(c.film_start_s / dur) * 100}%` }}><span className="pl-0.5">{c.scene}</span></div>
          ))}
          {r.findings.filter((f) => f.film_t != null).map((f) => (
            <button key={f.id} title={`${f.title} (${fmt(f.film_t)})`} onClick={() => jump(f)}
                    className={`absolute top-1 h-3 w-3 -translate-x-1/2 rounded-full ring-1 ring-zinc-900 ${SEV[f.severity].dot} ${open === f.id ? 'ring-2 ring-white' : ''}`}
                    style={{ left: `${(f.film_t! / dur) * 100}%` }} />
          ))}
        </div>
        <div className="flex justify-between text-[9px] text-zinc-500"><span>0:00</span><span>{fmt(r.film_duration_s)}</span></div>
      </div>

      <div className="flex flex-col gap-1" data-testid="review-findings">
        <div className="font-semibold text-zinc-300">{r.findings.length} phát hiện</div>
        {r.findings.map((f) => (
          <div key={f.id} className={`rounded border ${open === f.id ? 'border-violet-500' : 'border-zinc-700'} bg-zinc-950 px-2 py-1`}>
            <button className="flex w-full items-start gap-1 text-left" onClick={() => setOpen(open === f.id ? null : f.id)}>
              <span className={`shrink-0 rounded px-1 text-[9px] ${SEV[f.severity].chip}`}>{SEV[f.severity].label}</span>
              <span className="shrink-0 text-zinc-400">{f.scene ? `Cảnh ${f.scene}` : 'Cả phim'}{f.film_t != null ? ` · ${fmt(f.film_t)}` : ''}</span>
              <span className="font-medium">{f.title}</span>
            </button>
            {open === f.id && (
              <div className="mt-1 flex flex-col gap-1 text-zinc-300">
                <div><span className="text-zinc-500">Thấy gì: </span>{f.evidence}</div>
                <div><span className="text-zinc-500">Gốc lỗi ({CAUSE[f.cause] ?? f.cause}): </span>{f.cause_detail}</div>
                <div className="rounded bg-zinc-800 px-2 py-1"><span className="text-emerald-300">Đề xuất: </span>{f.fix}</div>
                {f.rule && <div className="text-[10px] text-zinc-400">📚 Quy tắc: {f.rule}</div>}
                <div className="flex flex-wrap items-center gap-1">
                  <span className="rounded bg-zinc-800 px-1 text-[10px] text-zinc-400" title="Nút thực hiện có ở bước 3">{ACTION[f.action] ?? f.action}</span>
                  {f.shot_id && <button className="rounded bg-zinc-700 px-1.5 text-[10px]" onClick={() => jump(f)}>→ Tới cảnh {f.scene}</button>}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {r.strengths.length > 0 && (
        <details>
          <summary className="cursor-pointer text-emerald-300">✅ Điểm tốt cần giữ ({r.strengths.length})</summary>
          <ul className="ml-4 list-disc text-zinc-300">{r.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
        </details>
      )}
    </div>
  )
}
