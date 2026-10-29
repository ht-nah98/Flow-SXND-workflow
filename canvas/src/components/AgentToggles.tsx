import type { Agents } from '../api/types'
import { FILM_PER_CLIP_S } from '../lib/duration'

/** Directive A5: the optional AI roles of a film. The writer, director and DP always run. */
export const DEFAULT_AGENTS: Agents = { producer: true, editor: true, qc: true, coach: true }

const ROLES: { key: keyof Agents; label: string; off: string }[] = [
  { key: 'producer', label: '🧾 Producer — đọc ý tưởng thành brief', off: 'lấy thẳng lựa chọn trên 💡 (ý tưởng có ảnh thì vẫn chạy để phân loại ảnh)' },
  { key: 'editor', label: '✏️ Editor — chấm và sửa kịch bản', off: 'kịch bản tới tay bạn không qua duyệt' },
  { key: 'qc', label: '🔍 QC — xem từng clip, chọn đoạn cắt', off: 'mỗi clip lấy đoạn giữa 1–8s, không tự quay lại clip lỗi' },
  { key: 'coach', label: '🎓 Coach — rút bài học sau phim', off: 'không ghi bài học mới' },
]

/** Rough count of AI calls for one film: 3 fixed roles + the optional ones (QC watches every clip). */
export function estimateCalls(a: Agents, targetS: number): number {
  const clips = Math.round(targetS / FILM_PER_CLIP_S)
  return 3 + (a.producer ? 1 : 0) + (a.editor ? 1 : 0) + (a.qc ? clips : 0) + (a.coach ? 1 : 0)
}

export function AgentToggles({ value, onChange, targetS, disabled }: {
  value: Agents; onChange: (a: Agents) => void; targetS: number; disabled?: boolean
}) {
  const on = ROLES.filter((r) => value[r.key]).length
  return (
    <details className="nodrag rounded bg-zinc-800/60 px-2 py-1 text-[11px]">
      <summary className="cursor-pointer select-none">
        🤖 Agent trong luồng ({on}/{ROLES.length} bật) · ~{estimateCalls(value, targetS)} lần gọi AI / phim
      </summary>
      <div className="mt-1 flex flex-col gap-1">
        <span className="text-zinc-400">Luôn chạy: ✍️ Biên kịch · 🎬 Đạo diễn · 📷 DP (viết prompt)</span>
        {ROLES.map((r) => (
          <label key={r.key} className="flex items-start gap-1.5" title={value[r.key] ? '' : r.off}>
            <input type="checkbox" checked={value[r.key]} disabled={disabled} aria-label={r.label}
                   onChange={(e) => onChange({ ...value, [r.key]: e.target.checked })} />
            <span>{r.label}{!value[r.key] && <span className="block text-zinc-500">Tắt: {r.off}</span>}</span>
          </label>
        ))}
      </div>
    </details>
  )
}
