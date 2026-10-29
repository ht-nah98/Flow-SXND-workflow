import type { DirectorRun } from '../api/types'

type Story = NonNullable<DirectorRun['plan']['story']>
const ROWS: [keyof Story, string][] = [
  ['story_line', '🧵 Tuyến truyện'], ['message', '💬 Thông điệp'], ['viewer_value', '🎁 Giá trị cho người xem'],
  ['rule_and_cost', '⚖️ Luật & cái giá'],
]

/** The script's spine, decided before any scene: what happens and why, what it means, what the viewer gets. */
const KEPT = { full: '✅ giữ đủ', compressed: '🔸 rút gọn', dropped: '❌ bỏ' } as const

export function StorySpine({ story, compact }: { story?: Story; compact?: boolean }) {
  const rows = ROWS.filter(([k]) => typeof story?.[k] === 'string' && (story[k] as string).trim())
  const notes = story?.notes_for_user ?? []
  const map = story?.source_map ?? []
  const intent = story?.director_notes ?? []
  const hooks = [...(story?.hooks ?? [])].sort((a, b) => a.at_s - b.at_s)
  if (!rows.length && !notes.length && !map.length && !intent.length) return null
  return (
    <div className={`flex flex-col gap-1 ${compact ? 'text-[11px]' : 'text-sm'}`}>
      {notes.length > 0 && (
        <ul className="rounded bg-amber-950 px-2 py-1 text-amber-200">
          {notes.map((n) => <li key={n}>⚠️ {n}</li>)}
        </ul>
      )}
      {rows.length > 0 && (
        <dl className="flex flex-col gap-1 rounded bg-zinc-800/60 p-1.5">
          {rows.map(([k, label]) => (
            <div key={k}>
              <dt className="font-semibold text-sky-300">{label}</dt>
              <dd className={`text-zinc-300 ${compact && k === 'story_line' ? 'line-clamp-3' : ''}`}>{story![k] as string}</dd>
            </div>
          ))}
        </dl>
      )}
      {intent.length > 0 && (
        <details className="rounded bg-zinc-800/60 p-1.5" open={!compact}>
          <summary className="cursor-pointer font-semibold text-violet-300">🎬 Ý đồ của đạo diễn</summary>
          <ul className="mt-1 flex list-disc flex-col gap-0.5 pl-4 text-zinc-300">{intent.map((n) => <li key={n}>{n}</li>)}</ul>
        </details>
      )}
      {hooks.length > 0 && (
        <details className="rounded bg-zinc-800/60 p-1.5" open={!compact}>
          <summary className="cursor-pointer font-semibold text-violet-300">⏱ Khoảnh khắc giữ chân ({hooks.length})</summary>
          <ul className="mt-1 flex flex-col gap-0.5 text-zinc-300">
            {hooks.map((h) => (
              <li key={`${h.at_s}-${h.beat_id}`}><span className="text-zinc-400">{clock(h.at_s)}</span> {h.moment}</li>
            ))}
          </ul>
        </details>
      )}
      {map.length > 0 && (
        <details className="rounded bg-zinc-800/60 p-1.5" open={!compact}>
          <summary className="cursor-pointer font-semibold text-sky-300">
            📖 Truyện gốc của bạn → kịch bản ({map.filter((m) => m.kept !== 'dropped').length}/{map.length} phần giữ lại)
          </summary>
          <ul className="mt-1 flex flex-col gap-0.5 text-zinc-300">
            {map.map((m) => (
              <li key={m.part}>
                <span className="text-zinc-400">{KEPT[m.kept]}</span> {m.part}
                {m.beats.length > 0 && <span className="text-zinc-500"> · {m.beats.join(', ')}</span>}
                {m.note && <span className="text-zinc-400"> — {m.note}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

/** 75 → "1:15". */
export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`
