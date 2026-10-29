import type { Creativity } from '../api/types'

/** Directive B9: how freely the writer develops the idea. Shown on the 💡 node and the new-idea dialog. */
export const CREATIVITY_LABEL: Record<Creativity, string> = {
  faithful: '🎯 Bám sát ý tưởng',
  balanced: '⚖️ Cân bằng — dựng thế giới quanh ý tưởng',
  bold: '🚀 Bay bổng — tự do sáng tạo',
}

export function CreativitySelect({ value, onChange }: { value: Creativity; onChange: (v: Creativity) => void }) {
  return (
    <select aria-label="Mức sáng tạo" value={value} onChange={(e) => onChange(e.target.value as Creativity)}
            className="rounded bg-zinc-800 px-1 py-1">
      {(Object.keys(CREATIVITY_LABEL) as Creativity[]).map((k) => <option key={k} value={k}>{CREATIVITY_LABEL[k]}</option>)}
    </select>
  )
}
