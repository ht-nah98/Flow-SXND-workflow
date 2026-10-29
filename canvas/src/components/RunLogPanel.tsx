import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import type { RunLog, RunLogIssue } from '../api/types'
import { clock, WRITING_STEPS } from './WritingTimeline'

/** 📋 Nhật ký (21/10): why a step went red, what the AI and Flow did — one panel beside the canvas, three tabs so
 *  progress, activity and errors are not mixed in one wall of text. */
export type LogTab = 'progress' | 'activity' | 'errors'
type Level = 'ok' | 'info' | 'warn' | 'error' | 'run'
export interface LogRow {
  id: string; at: string; icon: string; level: Level; title: string; meta?: string
  issues?: RunLogIssue[]; detail?: string; scene?: number | null
}

const WRITING = new Set(WRITING_STEPS.map(([k]) => k))
const REQ_STATUS: Record<string, [string, Level]> = {
  PENDING: ['chờ', 'info'], PROCESSING: ['đang tạo', 'run'], COMPLETED: ['xong', 'ok'], FAILED: ['lỗi', 'error'],
}
const KIND_ICON: Record<string, string> = { ai: '🤖', chain: '🔗', qc: '🔍', gate: '✋', error: '⛔', stage: '▸' }
const byTime = (a: LogRow, b: LogRow) => a.at.localeCompare(b.at)
const sceneOf = (d: Record<string, unknown>) => (typeof d.scene === 'number' ? d.scene : null)
/** Local HH:MM of a server time (UTC, with or without the trailing Z). */
export const hhmm = (at: string) => {
  const d = new Date(/Z$|[+-]\d\d:?\d\d$/.test(at) ? at : `${at}Z`)
  return Number.isNaN(d.getTime()) ? '' : `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function progressRows(log: RunLog): LogRow[] {
  const steps: LogRow[] = log.steps.map((s) => ({
    id: s.id, at: s.created_at, icon: s.status === 'OK' ? '✓' : '✗', level: s.status === 'OK' ? 'ok' : 'error',
    title: `${s.label}${s.attempt > 1 ? ` (lần ${s.attempt})` : ''}`,
    meta: s.duration_ms ? clock(s.duration_ms) : undefined, issues: s.issues,
  }))
  const events: LogRow[] = log.events
    .filter((e) => (e.kind === 'stage' && e.level === 'ok' && !WRITING.has(String(e.data.stage))) || e.kind === 'gate' || e.kind === 'error')
    .map((e) => ({
      id: e.id, at: e.created_at, icon: e.kind === 'stage' ? '✓' : KIND_ICON[e.kind], level: e.level,
      title: e.title.replace(/^Xong: /, ''), meta: typeof e.data.ms === 'number' ? clock(e.data.ms) : undefined,
      detail: typeof e.data.message === 'string' ? e.data.message : undefined,
    }))
  return [...steps, ...events].sort(byTime)
}

export function activityRows(log: RunLog): LogRow[] {
  const events: LogRow[] = log.events.filter((e) => ['ai', 'chain', 'qc'].includes(e.kind)).map((e) => {
    const d = e.data
    const meta = e.kind === 'ai'
      ? [typeof d.ms === 'number' ? clock(d.ms) : '', typeof d.cost_usd === 'number' && d.cost_usd > 0 ? `$${d.cost_usd.toFixed(2)}` : '']
        .filter(Boolean).join(' · ')
      : undefined
    const issues = Array.isArray(d.issues) ? (d.issues as string[]).join(' · ') : undefined
    return { id: e.id, at: e.created_at, icon: KIND_ICON[e.kind], level: e.level, title: e.title, meta,
             detail: issues || (typeof d.message === 'string' ? d.message : undefined), scene: sceneOf(d) }
  })
  const flow: LogRow[] = log.requests.map((r) => {
    const [word, level] = REQ_STATUS[r.status] ?? [r.status, 'info']
    const what = r.scene ? `Cảnh ${r.scene}` : r.entity ?? ''
    return { id: r.id, at: r.created_at, icon: r.type.includes('VIDEO') ? '🎬' : '🖼', level,
             title: `${r.label}${what ? ` · ${what}` : ''}`, meta: word + (r.retries ? ` · thử lại ${r.retries}` : ''),
             detail: r.error ?? undefined, scene: r.scene }
  })
  return [...events, ...flow].sort(byTime)
}

export function errorRows(log: RunLog): LogRow[] {
  return [
    ...progressRows(log).filter((r) => r.level === 'error' || r.level === 'warn'),
    ...activityRows(log).filter((r) => r.level === 'error' || r.level === 'warn'),
  ].sort(byTime)
}

const TONE: Record<Level, string> = {
  ok: 'text-zinc-300', info: 'text-zinc-300', run: 'text-sky-300', warn: 'text-amber-300', error: 'text-red-300',
}

function Row({ r, onScene }: { r: LogRow; onScene: (n: number) => void }) {
  const [open, setOpen] = useState(false)
  const more = !!(r.issues?.length || r.detail)
  return (
    <li className="rounded px-1.5 py-1 hover:bg-zinc-800/60" data-testid="log-row">
      <button className="flex w-full items-start gap-1.5 text-left" onClick={() => more && setOpen(!open)} aria-expanded={more ? open : undefined}>
        <span className="w-4 shrink-0 text-center">{r.icon}</span>
        <span className={`min-w-0 flex-1 ${TONE[r.level]}`}>{r.title}
          {!!r.issues?.length && <span className="ml-1 rounded bg-red-900/70 px-1 text-[10px] text-red-200">{r.issues.length} lỗi</span>}
        </span>
        {r.meta && <span className="shrink-0 tabular-nums text-zinc-500">{r.meta}</span>}
        <span className="w-9 shrink-0 text-right tabular-nums text-zinc-600" title={r.at}>{hhmm(r.at)}</span>
        {more && <span className="shrink-0 text-zinc-500">{open ? '▾' : '▸'}</span>}
      </button>
      {r.scene != null && !open && !r.issues?.length && (
        <button className="ml-6 text-[10px] text-sky-400 hover:underline" onClick={() => onScene(r.scene!)}>→ Cảnh {r.scene}</button>
      )}
      {open && (
        <div className="ml-6 mt-1 flex flex-col gap-1">
          {r.issues?.map((i, k) => <Issue key={k} i={i} onScene={onScene} />)}
          {r.detail && <div className="whitespace-pre-wrap rounded bg-zinc-950 px-2 py-1 text-[10px] text-zinc-400">{r.detail}</div>}
        </div>
      )}
    </li>
  )
}

function Issue({ i, onScene }: { i: RunLogIssue; onScene: (n: number) => void }) {
  const [en, setEn] = useState(false)
  return (
    <div className={`rounded border-l-2 ${i.severity === 'error' ? 'border-red-500' : 'border-amber-400'} bg-zinc-950 px-2 py-1`}>
      <div className="flex items-center gap-1">
        <span className="font-medium text-zinc-200">⚠ {i.label}</span>
        {i.scene != null && (
          <button className="ml-auto shrink-0 rounded bg-zinc-800 px-1.5 text-[10px] text-sky-300 hover:bg-zinc-700"
                  onClick={() => onScene(i.scene!)}>Cảnh {i.scene} →</button>
        )}
      </div>
      <button className="text-[10px] text-zinc-500 hover:text-zinc-300" onClick={() => setEn(!en)}>{en ? 'ẩn chi tiết' : 'chi tiết'}</button>
      {en && <div className="text-[10px] text-zinc-400">{i.message}</div>}
    </div>
  )
}

export function RunLogPanel({ projectId, runIds, onScene, onClose }: {
  projectId: string; runIds: string[]; onScene: (n: number) => void; onClose: () => void
}) {
  const [tab, setTab] = useState<LogTab>('progress')
  const [pick, setPick] = useState(0)
  const rid = runIds[Math.min(pick, runIds.length - 1)]
  const q = useQuery({
    queryKey: ['p', projectId, 'runlog', rid], queryFn: () => api.runLog(rid!), enabled: !!rid,
    refetchInterval: (query) => (query.state.data?.status === 'RUNNING' ? 5000 : false),
  })
  const log = q.data
  const errors = log ? errorRows(log) : []
  const rows = !log ? [] : tab === 'progress' ? progressRows(log) : tab === 'activity' ? activityRows(log) : errors
  const tabs: [LogTab, string][] = [['progress', 'Tiến trình'], ['activity', 'AI & Flow'], ['errors', `Lỗi${errors.length ? ` ${errors.length}` : ''}`]]
  const running = log?.status === 'RUNNING'
  return (
    <aside className="flex w-[380px] shrink-0 flex-col border-l border-zinc-800 bg-zinc-900 text-[11px]" aria-label="Nhật ký" data-testid="runlog">
      <div className="flex items-center gap-2 border-b border-zinc-800 px-3 py-2">
        <span className="font-semibold text-zinc-200">📋 Nhật ký</span>
        {runIds.length > 1 && (
          <select aria-label="Chọn lần chạy" className="rounded bg-zinc-800 px-1 text-[10px]" value={pick} onChange={(e) => setPick(Number(e.target.value))}>
            {runIds.map((id, i) => <option key={id} value={i}>{i === 0 ? 'Lần chạy mới nhất' : `Lần chạy trước ${i}`}</option>)}
          </select>
        )}
        <button className="ml-auto text-zinc-500 hover:text-white" onClick={onClose} aria-label="Đóng nhật ký">✕</button>
      </div>
      <div className="flex gap-1 border-b border-zinc-800 px-2 py-1.5" role="tablist">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                  className={`rounded px-2 py-0.5 ${tab === k ? (k === 'errors' && errors.length ? 'bg-red-800 text-white' : 'bg-sky-700 text-white') : 'text-zinc-400 hover:bg-zinc-800'}`}>{label}</button>
        ))}
      </div>
      {running && log && (
        <div className="border-b border-zinc-800 px-3 py-1 text-sky-300"><span className="animate-pulse">⏳</span> Đang: {log.stage_label}…</div>
      )}
      <ol className="nowheel min-h-0 flex-1 overflow-y-auto px-1.5 py-1">
        {!rid && <li className="p-2 text-zinc-500">Project này chưa có lần chạy đạo diễn.</li>}
        {rid && !log && <li className="p-2 text-zinc-500">{q.error ? `Chưa tải được nhật ký: ${q.error.message}` : 'Đang tải…'}</li>}
        {log && !rows.length && <li className="p-2 text-zinc-500">{tab === 'errors' ? 'Không có lỗi.' : 'Chưa có gì.'}</li>}
        {rows.map((r) => <Row key={r.id} r={r} onScene={onScene} />)}
      </ol>
    </aside>
  )
}
