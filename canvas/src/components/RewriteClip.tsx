import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { SceneReview } from '../api/types'
import { projectKey } from '../api/queries'
import { explainError } from '../lib/errors'
import { useToast } from './Toast'

/** Lines of the new prompt that are not in the old one: what the rewrite actually changed. */
export const changedLines = (oldText: string, newText: string) => {
  const before = new Set(oldText.split('\n').map((l) => l.trim()))
  return newText.split('\n').map((line) => ({ line, changed: !before.has(line.trim()) }))
}

/** Continuous film: scenes that open on this clip's last frame. Those already made were made from the old take. */
export function ChainNote({ chained, made = [] }: { chained: number[]; made?: number[] }) {
  if (!chained.length) return null
  const list = (ns: number[]) => `cảnh ${ns.join(', ')}`
  return (
    <div className="rounded bg-amber-950/70 px-2 py-1 text-[10px] text-amber-200">
      🔗 Phim liền mạch: {list(chained)} mở từ khung cuối của cảnh này.{' '}
      {made.length
        ? `${list(made)} đã tạo từ bản cũ — tạo lại cảnh này thì muốn khớp hoàn toàn phải tạo lại cả ${made.length > 1 ? 'các cảnh đó' : 'cảnh đó'}.`
        : 'Nên chốt cảnh này ưng ý trước rồi mới tạo các cảnh sau.'}
    </div>
  )
}

/** "Sửa clip này bằng lời": Claude rewrites only this clip's prompt; the user reads the change first.
 *  `review` (22/10): rewrite from the video review's errors instead — set by "Claude viết lại theo đánh giá".
 *  Free — the credit is spent only when the clip is regenerated afterwards. */
export function RewriteClip({ runId, shotId, projectId, review = null, chained = [], chainedMade = [] }: {
  runId: string; shotId: string; projectId: string; review?: SceneReview | null; chained?: number[]; chainedMade?: number[]
}) {
  const qc = useQueryClient()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [busy, setBusy] = useState(false)
  const [proposal, setProposal] = useState<{ old: string; new: string } | null>(null)
  const fail = (e: unknown) => toast(explainError(e instanceof Error ? e.message : String(e)).message, 'error')

  const ask = async (from?: SceneReview) => {
    setBusy(true)
    try { setProposal(await api.rewriteShot(runId, shotId, feedback.trim(), from)) } catch (e) { fail(e) } finally { setBusy(false) }
  }
  useEffect(() => {
    if (!review) return
    setOpen(true); setProposal(null)
    void ask(review)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [review])
  const apply = async () => {
    setBusy(true)
    try {
      await api.applyRewrite(runId, shotId)
      await qc.invalidateQueries({ queryKey: projectKey(projectId) })
      toast('Đã đổi prompt. Bấm "Gen lại video" trên cảnh để tạo clip mới (tốn credit).')
      setOpen(false); setProposal(null); setFeedback('')
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  if (!open) {
    return <button className="nodrag rounded bg-zinc-700 px-2 py-1 text-[11px]" onClick={() => setOpen(true)}>✏️ Sửa clip bằng lời</button>
  }
  return (
    <div className="nodrag nowheel flex flex-col gap-1 rounded bg-zinc-800/70 p-1.5 text-[11px]">
      {!proposal ? (
        <>
          <ChainNote chained={chained} made={chainedMade} />
          <textarea aria-label="Góp ý cho clip" rows={2} value={feedback} onChange={(e) => setFeedback(e.target.value)}
                    placeholder="Ví dụ: cô gái cười tươi hơn, máy quay gần hơn, bỏ chậu thứ hai…"
                    className="rounded bg-zinc-900 px-2 py-1" />
          <div className="flex gap-1">
            <button disabled={busy || feedback.trim().length < 2} className="flex-1 rounded bg-sky-700 px-2 py-1 disabled:opacity-40"
                    onClick={() => void ask()}>{busy ? '⏳ Claude đang viết lại…' : 'Viết lại prompt (miễn phí)'}</button>
            <button className="rounded bg-zinc-700 px-2 py-1" onClick={() => setOpen(false)}>Huỷ</button>
          </div>
        </>
      ) : (
        <>
          <div className="text-zinc-400">Prompt mới{review ? ` (theo đánh giá ${review.overall_score.toFixed(1)}/10)` : ''} — dòng <span className="text-emerald-300">xanh</span> là chỗ đã sửa:</div>
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded bg-zinc-900 p-1.5 text-[10px] leading-snug">
            {changedLines(proposal.old, proposal.new).map((l, i) => (
              <div key={i} className={l.changed ? 'bg-emerald-950 text-emerald-200' : 'text-zinc-400'}>{l.line}</div>
            ))}
          </pre>
          <ChainNote chained={chained} made={chainedMade} />
          <div className="flex gap-1">
            <button disabled={busy} className="flex-1 rounded bg-emerald-700 px-2 py-1 disabled:opacity-40" onClick={() => void apply()}>
              Dùng prompt này
            </button>
            <button disabled={busy} className="rounded bg-zinc-700 px-2 py-1" onClick={() => setProposal(null)}>Viết lại</button>
          </div>
        </>
      )}
    </div>
  )
}
