import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../api/client'
import { projectKey } from '../api/queries'
import type { ClipEditChoice, DirectorRun, EffectOption, FilmEdit } from '../api/types'
import { explainError } from '../lib/errors'
import { useToast } from './Toast'

type ShotInfo = { id: string; idea?: string; order?: number }

/** Change one clip's choice without touching the others. */
export function setClip(edit: FilmEdit, shotId: string, patch: Partial<ClipEditChoice>): FilmEdit {
  return { ...edit, clips: edit.clips.map((c) => (c.shot_id === shotId ? { ...c, ...patch } : c)) }
}

function Pick({ label, value, options, onChange, none }: {
  label: string; value: string | null | undefined; options: EffectOption[]; onChange: (v: string | null) => void; none: string
}) {
  const cur = options.find((o) => o.id === value)
  return (
    <select aria-label={label} title={cur?.use ?? none} value={value ?? ''} onChange={(e) => onChange(e.target.value || null)}
            className="min-w-0 flex-1 rounded bg-zinc-800 px-1.5 py-1 text-[12px]">
      <option value="">{none}</option>
      {options.map((o) => <option key={o.id} value={o.id} title={o.use}>{o.label}</option>)}
    </select>
  )
}

/** 🎨 Hiệu ứng dựng: the film's colour grade, each clip's effects and how it hands over to the next.
 *  The director proposes them in the script; the user can change them here. Free: applied when the film is cut. */
export function EditEffects({ run }: { run: DirectorRun }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button className="nodrag rounded bg-zinc-700 px-2 py-1 text-[11px]" onClick={() => setOpen(true)}>🎨 Hiệu ứng dựng</button>
      {open && createPortal(<EditDialog run={run} onClose={() => setOpen(false)} />, document.body)}
    </>
  )
}

function EditDialog({ run, onClose }: { run: DirectorRun; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const catalog = useQuery({ queryKey: ['effects'], queryFn: api.effectsCatalog, staleTime: Infinity })
  const saved = useQuery({ queryKey: ['edit', run.id], queryFn: () => api.getEdit(run.id) })
  const [draft, setDraft] = useState<FilmEdit | null>(null)
  const [busy, setBusy] = useState(false)
  const edit = draft ?? saved.data
  const shots = new Map(((run.plan.shotlist?.shots ?? []) as ShotInfo[]).map((s) => [s.id, s]))
  const cutDone = run.status === 'DONE'

  const save = async (recut: boolean) => {
    if (!edit) return
    setBusy(true)
    try {
      await api.putEdit(run.id, edit)
      if (recut) await api.recutRun(run.id)
      await qc.invalidateQueries({ queryKey: ['edit', run.id] })
      await qc.invalidateQueries({ queryKey: projectKey(run.project_id ?? '') })
      toast(recut ? 'Đang dựng lại phim với hiệu ứng mới (khoảng 1 phút, không tốn credit).'
                  : 'Đã lưu. Hiệu ứng được áp dụng khi dựng phim.')
      onClose()
    } catch (e) {
      toast(explainError(e instanceof Error ? e.message : String(e)).message, 'error')
    } finally { setBusy(false) }
  }

  return (
    <div role="dialog" aria-label="Hiệu ứng dựng" className="fixed inset-0 z-50 flex justify-center bg-black/70 p-4" onClick={onClose}>
      <article className="flex w-full max-w-3xl flex-col gap-3 overflow-y-auto rounded-xl bg-zinc-900 p-5 text-sm text-zinc-200"
               onClick={(e) => e.stopPropagation()}>
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold">🎨 Hiệu ứng dựng</h1>
            <p className="text-xs text-zinc-400">
              Kiểu CapCut, dựng lại bằng ffmpeg. Đạo diễn đã đề xuất; bạn đổi tuỳ ý. Miễn phí — áp dụng khi dựng phim.
              Phần lớn chỗ nối nên để cắt thẳng.
            </p>
          </div>
          <button onClick={onClose} className="rounded bg-zinc-800 px-2 py-1">Đóng</button>
        </header>
        {!edit || !catalog.data ? <p className="text-zinc-400">Đang tải…</p> : (
          <>
            <label className="flex items-center gap-2">
              <span className="w-40 shrink-0 text-zinc-300">Bộ lọc màu cả phim</span>
              <Pick label="Bộ lọc màu cả phim" value={edit.look} options={catalog.data.looks} none="Gốc (màu của Flow)"
                    onChange={(v) => setDraft({ ...edit, look: v ?? 'goc' })} />
            </label>
            <ol className="flex flex-col gap-2">
              {edit.clips.map((c, i) => {
                const fx = c.fx ?? []
                const last = i === edit.clips.length - 1
                return (
                  <li key={c.shot_id} className="flex flex-col gap-1 rounded bg-zinc-800/60 p-2">
                    <div className="truncate font-semibold">{i + 1}. {shots.get(c.shot_id)?.idea ?? c.shot_id}</div>
                    <div className="flex flex-wrap gap-1">
                      {[0, 1].map((k) => (
                        <Pick key={k} label={`Hiệu ứng ${k + 1} clip ${i + 1}`} value={fx[k]} options={catalog.data.fx}
                              none={k ? '+ hiệu ứng thứ hai' : 'Không hiệu ứng'}
                              onChange={(v) => {
                                const next = [...fx]; next[k] = v ?? ''
                                setDraft(setClip(edit, c.shot_id, { fx: next.filter(Boolean) }))
                              }} />
                      ))}
                    </div>
                    {!last && (
                      <div className="flex items-center gap-2 text-[12px] text-zinc-400">
                        <span className="shrink-0">↓ chuyển sang clip {i + 2}:</span>
                        <Pick label={`Chuyển tiếp sau clip ${i + 1}`} value={c.transition_out ?? 'cat'}
                              options={catalog.data.transitions.filter((t) => t.id !== 'cat')} none="Cắt thẳng"
                              onChange={(v) => setDraft(setClip(edit, c.shot_id, { transition_out: v ?? 'cat' }))} />
                      </div>
                    )}
                  </li>
                )
              })}
            </ol>
            <footer className="flex gap-2">
              <button disabled={busy || !draft} className="rounded bg-sky-700 px-3 py-1.5 disabled:opacity-40"
                      onClick={() => void save(false)}>Lưu</button>
              {cutDone && (
                <button disabled={busy} className="rounded bg-amber-700 px-3 py-1.5 disabled:opacity-40"
                        onClick={() => void save(true)}>🎬 Lưu &amp; dựng lại phim (miễn phí)</button>
              )}
            </footer>
          </>
        )}
      </article>
    </div>
  )
}
