import { useState } from 'react'
import { api } from '../api/client'
import { useCanvasActions } from '../canvas/actions-context'
import { useToast } from './Toast'

export type AssistTarget = { kind: 'scene' | 'character'; id: string; label: string }
type Change = { kind: 'scene' | 'character'; id: string; field: string; value: string; why: string }
type Model = 'sonnet' | 'opus' | 'haiku'

const FIELD: Record<string, string> = {
  video_prompt: 'Prompt video', prompt: 'Ý tưởng shot', description: 'Mô tả', image_prompt: 'Prompt ảnh asset', name: 'Tên',
}
const QUICK = [
  { label: '✨ Tối ưu prompt video', text: 'Tối ưu prompt video của các clip đã chọn (giữ ý tưởng và asset).' },
  { label: '🌐 Dịch sang tiếng Anh', text: 'Dịch prompt sang tiếng Anh, giữ nguyên nội dung.' },
  { label: '🧍 Làm rõ asset', text: 'Viết lại mô tả và prompt ảnh của asset đã chọn cho rõ, nhất quán.' },
]

/** SciCloud sample (19/10): select nodes on the canvas, ask in words, review the proposed edits, apply them.
 *  Free of Flow credit; nothing changes until "Áp dụng". */
export function AssistBar({ projectId, targets }: { projectId: string; targets: AssistTarget[] }) {
  const a = useCanvasActions()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [model, setModel] = useState<Model>('sonnet')
  const [busy, setBusy] = useState(false)
  const [reply, setReply] = useState<{ answer: string; changes: Change[] } | null>(null)
  const [applied, setApplied] = useState<Set<number>>(new Set())

  const send = async (instruction: string) => {
    if (instruction.trim().length < 2) return
    setBusy(true); setReply(null); setApplied(new Set())
    try {
      setReply(await api.assist({ project_id: projectId, instruction, model,
                                  targets: targets.map(({ kind, id }) => ({ kind, id })) }))
    } catch (e) { toast(e instanceof Error ? e.message : String(e), 'error') } finally { setBusy(false) }
  }
  const apply = async (c: Change, i: number) => {
    if (c.kind === 'scene') await a.patchScene(c.id, { [c.field]: c.value })
    else await a.patchCharacter(c.id, { [c.field]: c.value })
    setApplied((s) => new Set(s).add(i))
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="rounded-full bg-violet-700 px-3 py-1.5 text-xs font-semibold shadow-lg">
        🤖 Hỏi AI{targets.length ? ` (${targets.length} ô đã chọn)` : ''}
      </button>
    )
  }
  return (
    <div role="region" aria-label="Hỏi AI" className="nodrag nowheel flex w-[640px] max-w-[90vw] flex-col gap-2 rounded-xl bg-zinc-900/95 p-3 text-xs shadow-2xl ring-1 ring-violet-700">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-violet-300">🤖 Hỏi AI về các ô đã chọn</span>
        <span className="flex items-center gap-1">
          <select aria-label="Model" value={model} onChange={(e) => setModel(e.target.value as Model)} className="rounded bg-zinc-800 px-1 py-0.5">
            <option value="sonnet">Sonnet (mặc định)</option><option value="opus">Opus (kỹ hơn)</option><option value="haiku">Haiku (nhanh)</option>
          </select>
          <button onClick={() => setOpen(false)} className="rounded bg-zinc-800 px-2 py-0.5">Thu gọn</button>
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {targets.length ? targets.map((t) => <span key={t.id} className="rounded bg-zinc-800 px-1.5 py-0.5">@{t.label}</span>)
          : <span className="text-zinc-400">Chọn một hoặc nhiều ô (Shift/Ctrl + bấm) — cảnh hoặc asset — để AI sửa chúng.</span>}
      </div>
      <div className="flex flex-wrap gap-1">
        {QUICK.map((q) => (
          <button key={q.label} disabled={busy || !targets.length} onClick={() => { setText(q.text); void send(q.text) }}
                  className="rounded bg-zinc-800 px-2 py-1 disabled:opacity-40">{q.label}</button>
        ))}
      </div>
      <div className="flex gap-1">
        <textarea aria-label="Yêu cầu" value={text} onChange={(e) => setText(e.target.value)} rows={2}
                  placeholder="VD: cho clip này quay từ ngoài cửa sổ nhìn vào, trời mưa"
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(text) } }}
                  className="flex-1 resize-y rounded bg-zinc-800 p-2" />
        <button disabled={busy || text.trim().length < 2} onClick={() => void send(text)}
                className="rounded bg-violet-700 px-3 font-semibold disabled:opacity-40">{busy ? '⏳' : 'Gửi'}</button>
      </div>
      {reply && (
        <div className="flex max-h-[45vh] flex-col gap-2 overflow-y-auto">
          <p className="whitespace-pre-wrap text-zinc-200">{reply.answer}</p>
          {reply.changes.map((c, i) => (
            <div key={i} className="flex flex-col gap-1 rounded bg-zinc-800/70 p-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold">{targets.find((t) => t.id === c.id)?.label ?? c.id} · {FIELD[c.field] ?? c.field}</span>
                <button disabled={applied.has(i)} onClick={() => void apply(c, i)}
                        className="rounded bg-emerald-700 px-2 py-0.5 disabled:opacity-50">{applied.has(i) ? '✓ Đã áp dụng' : 'Áp dụng'}</button>
              </div>
              {c.why && <span className="text-zinc-400">{c.why}</span>}
              <pre className="whitespace-pre-wrap text-[11px] text-zinc-300">{c.value}</pre>
            </div>
          ))}
          {reply.changes.length > 1 && (
            <button onClick={() => void Promise.all(reply.changes.map((c, i) => (applied.has(i) ? null : apply(c, i))))}
                    className="self-end rounded bg-emerald-800 px-2 py-1">Áp dụng tất cả</button>
          )}
        </div>
      )}
    </div>
  )
}
