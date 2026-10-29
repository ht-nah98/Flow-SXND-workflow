import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { RunTimeline } from '../api/types'

export const WRITING_STEPS: [string, string][] = [
  ['BRIEF', 'Đọc ý tưởng'], ['STORY', 'Viết câu chuyện'], ['SHOTLIST', 'Chia cảnh'],
  ['PROMPTS', 'Viết prompt'], ['EDIT_REVIEW', 'Biên tập duyệt'],
]
const LABEL = Object.fromEntries(WRITING_STEPS)
const ORDER = WRITING_STEPS.map(([k]) => k)

export const clock = (ms: number) => {
  const s = Math.max(0, Math.round(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** Rows to show: every finished step (a step that goes back to an earlier stage is an editor revision). */
export function timelineRows(t: RunTimeline) {
  return t.steps.map((s, i) => {
    const prev = t.steps[i - 1]
    const revision = !!prev && prev.stage === 'EDIT_REVIEW' && ORDER.indexOf(s.stage) < ORDER.indexOf('EDIT_REVIEW')
    return { ...s, label: LABEL[s.stage] ?? s.stage, revision }
  })
}

/** Rough time left: the usual length of the current stage (minus what has passed) and of the ones after it. */
export function etaMs(t: RunTimeline, elapsed: number) {
  const i = ORDER.indexOf(t.stage)
  if (i < 0) return null
  const typ = (k: string) => t.typical_ms[k] ?? 90_000
  return Math.max(0, typ(t.stage) - elapsed) + ORDER.slice(i + 1).reduce((a, k) => a + typ(k), 0)
}

/** Live progress of the script being written: what is done, how long it took, what runs now. */
export function WritingTimeline({ runId }: { runId: string }) {
  const q = useQuery({ queryKey: ['timeline', runId], queryFn: () => api.runTimeline(runId), refetchInterval: 3000 })
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t) }, [])
  const t = q.data
  if (!t) return null
  const running = t.status === 'RUNNING' && ORDER.includes(t.stage)
  const since = t.since ? Date.parse(t.since.endsWith('Z') ? t.since : `${t.since}Z`) : now
  const elapsed = now - since
  const eta = running ? etaMs(t, elapsed) : null
  return (
    <ol className="nodrag flex flex-col gap-0.5 rounded bg-zinc-800/60 px-2 py-1 text-[11px]" aria-label="Tiến trình viết kịch bản">
      {timelineRows(t).map((r, i) => (
        <li key={i} className="flex items-center gap-1.5">
          {r.revision && <span className="text-amber-300" title="Biên tập yêu cầu sửa">↩</span>}
          <span>{r.status === 'OK' ? '✓' : '✗'}</span>
          <span className={r.status === 'OK' ? 'text-zinc-300' : 'text-red-300'}>
            {r.label}{r.attempt > 1 ? ` (lần ${r.attempt})` : ''}
          </span>
          <span className="ml-auto tabular-nums text-zinc-500">{r.duration_ms ? clock(r.duration_ms) : ''}</span>
        </li>
      ))}
      {running && (
        <li className="flex items-center gap-1.5 text-sky-300">
          <span className="animate-pulse">⏳</span>
          <span>{LABEL[t.stage]}…</span>
          <span className="ml-auto tabular-nums">
            {clock(elapsed)}{t.typical_ms[t.stage] ? ` / thường ~${clock(t.typical_ms[t.stage])}` : ''}
          </span>
        </li>
      )}
      {eta !== null && (
        <li className="mt-0.5 border-t border-zinc-700 pt-0.5 text-zinc-400">
          Còn khoảng ~{Math.max(1, Math.round(eta / 60000))} phút{t.edit_loops ? ` · biên tập đã yêu cầu sửa ${t.edit_loops} lần` : ''}
        </li>
      )}
    </ol>
  )
}
