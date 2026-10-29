import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { SampleMeta } from '../api/types'
import { useToast } from '../components/Toast'
import { explainError } from '../lib/errors'

const STATUS: Record<SampleMeta['status'], string> = {
  ANALYZING: '⏳ Claude đang xem…', READY: '✋ Chờ bạn chọn kỹ thuật', FAILED: '⚠️ Lỗi', ADOPTED: '✅ Đã thêm vào sổ tay',
}
const SCOPE: Record<string, string> = {
  story: 'Kịch bản', shotlist: 'Chia cảnh', prompt: 'Prompt', omni_flash: 'Omni Flash', edit: 'Dựng / hiệu ứng',
}

/** Learn from a sample video: Claude reads every shot; the user picks which techniques the director adopts. */
export function LearnPage() {
  const qc = useQueryClient()
  const toast = useToast()
  const list = useQuery({ queryKey: ['samples'], queryFn: api.listSamples, refetchInterval: 4000 })
  const [sel, setSel] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const fail = (e: unknown) => toast(explainError(e instanceof Error ? e.message : String(e)).message, 'error')
  const upload = async (f: File) => {
    setUploading(true)
    try {
      const m = await api.uploadSample(f)
      setSel(m.id)
      await qc.invalidateQueries({ queryKey: ['samples'] })
    } catch (e) { fail(e) } finally { setUploading(false) }
  }
  const samples = list.data ?? []
  useEffect(() => { if (!sel && samples[0]) setSel(samples[0].id) }, [sel, samples])

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-6 text-sm">
      <div className="flex items-center gap-3">
        <Link to="/" className="text-zinc-400 hover:text-white">← Project</Link>
        <h1 className="text-lg font-semibold">📚 Học từ video mẫu</h1>
      </div>
      <label onDragOver={(e) => e.preventDefault()}
             onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) void upload(f) }}
             className="cursor-pointer rounded-xl border border-dashed border-zinc-600 p-6 text-center text-zinc-400 hover:border-sky-500">
        {uploading ? '⏳ Đang tải lên…' : 'Kéo thả video mẫu vào đây hoặc bấm để chọn (mp4, mov, webm — tối đa 300 MB). '
          + 'Claude xem từng shot (không nghe được âm thanh), rồi đề xuất kỹ thuật để bạn chọn.'}
        <input type="file" accept="video/*" className="sr-only" aria-label="Chọn video mẫu"
               onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = '' }} />
      </label>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-[260px_1fr]">
        <ul className="flex flex-col gap-1">
          {samples.map((s) => (
            <li key={s.id}>
              <button onClick={() => setSel(s.id)}
                      className={`w-full rounded-lg px-3 py-2 text-left ${sel === s.id ? 'bg-zinc-800' : 'bg-zinc-900 hover:bg-zinc-800'}`}>
                <div className="truncate font-medium">{s.title ?? s.name}</div>
                <div className="text-xs text-zinc-400">{STATUS[s.status]}{s.shots ? ` · ${s.shots} shot` : ''}</div>
              </button>
            </li>
          ))}
          {!samples.length && <li className="text-zinc-500">Chưa có video mẫu nào.</li>}
        </ul>
        {sel && <SampleView sid={sel} onError={fail} />}
      </div>
    </div>
  )
}

function SampleView({ sid, onError }: { sid: string; onError: (e: unknown) => void }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['sample', sid], queryFn: () => api.getSample(sid),
                       refetchInterval: (r) => (r.state.data?.status === 'ANALYZING' ? 4000 : false) })
  const [picked, setPicked] = useState<Set<number> | null>(null)
  const [busy, setBusy] = useState(false)
  const s = q.data
  if (!s) return <p className="text-zinc-400">Đang tải…</p>
  const a = s.analysis
  const chosen = picked ?? new Set(a?.techniques.map((_, i) => i) ?? [])
  const toggle = (i: number) => { const n = new Set(chosen); if (n.has(i)) n.delete(i); else n.add(i); setPicked(n) }
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try { await fn(); await qc.invalidateQueries({ queryKey: ['sample', sid] }); await qc.invalidateQueries({ queryKey: ['samples'] }) }
    catch (e) { onError(e) } finally { setBusy(false) }
  }
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start gap-4">
        <video src={api.sampleVideoUrl(sid)} controls className="max-h-[360px] max-w-[420px] rounded bg-black" />
        <div className="min-w-[240px] flex-1">
          <h2 className="text-base font-semibold">{a?.title ?? s.name}</h2>
          <p className="text-zinc-400">{STATUS[s.status]}</p>
          {s.status === 'FAILED' && (
            <>
              <p className="text-red-300">{s.error}</p>
              <button disabled={busy} className="mt-1 rounded bg-amber-700 px-2 py-1" onClick={() => void act(() => api.retrySample(sid))}>Phân tích lại</button>
            </>
          )}
          {a && <p className="mt-2 whitespace-pre-wrap text-zinc-200">{a.summary}</p>}
          {a && <p className="mt-2 whitespace-pre-wrap text-zinc-400"><b className="text-zinc-300">Cấu trúc:</b> {a.structure}</p>}
          {s.playbook && <p className="mt-2 text-emerald-300">Đã lưu vào sổ tay: {s.playbook.split('/').slice(-2).join('/')}</p>}
        </div>
      </div>
      {a && (
        <>
          <h3 className="font-semibold">Kỹ thuật đáng học</h3>
          <ul className="flex flex-col gap-2">
            {a.techniques.map((t, i) => (
              <li key={i} className="rounded-lg bg-zinc-900 p-3">
                <label className="flex items-start gap-2">
                  <input type="checkbox" checked={chosen.has(i)} disabled={s.status === 'ADOPTED'} onChange={() => toggle(i)} className="mt-1" />
                  <span>
                    <b>{t.name}</b> <span className="rounded bg-zinc-800 px-1.5 text-xs text-zinc-300">{SCOPE[t.scope] ?? t.scope}</span>
                    <span className="block text-zinc-200">{t.rule}</span>
                    <span className="block text-xs text-zinc-400">Cách làm: {t.how}</span>
                    <span className="block text-xs text-zinc-500">Trong mẫu: {t.example}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {s.status === 'READY' && (
            <button disabled={busy || chosen.size === 0} className="self-start rounded-lg bg-emerald-700 px-3 py-1.5 font-medium disabled:opacity-40"
                    onClick={() => void act(() => api.adoptSample(sid, [...chosen]))}>
              Thêm {chosen.size} kỹ thuật vào sổ tay — đạo diễn áp dụng từ phim sau
            </button>
          )}
          <h3 className="font-semibold">Từng shot ({a.shots.length})</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-left text-zinc-400">
                <tr>{['#', 'Thời gian', 'Nội dung', 'Cỡ cảnh', 'Góc máy', 'Chuyển động', 'Vào cảnh', 'Ánh sáng / màu'].map((h) => <th key={h} className="p-1.5">{h}</th>)}</tr>
              </thead>
              <tbody>
                {a.shots.map((sh, i) => (
                  <tr key={i} className="border-t border-zinc-800 align-top">
                    <td className="p-1.5">{i + 1}</td><td className="p-1.5 whitespace-nowrap">{sh.start_s.toFixed(1)}–{sh.end_s.toFixed(1)}s</td>
                    <td className="p-1.5">{sh.content}</td><td className="p-1.5">{sh.framing}</td><td className="p-1.5">{sh.angle}</td>
                    <td className="p-1.5">{sh.movement}</td><td className="p-1.5">{sh.transition_in}</td><td className="p-1.5">{sh.look}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
