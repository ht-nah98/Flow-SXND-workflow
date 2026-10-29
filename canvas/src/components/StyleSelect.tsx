import { useStyles } from '../api/queries'

/** One look for the whole film (style packs, gonghaosnail skill library, 19/10). Empty = the director picks. */
export function StyleSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const packs = useStyles().data ?? []
  const pick = packs.find((p) => p.id === value)
  return (
    <span className="flex flex-col gap-0.5">
      <select aria-label="Gói phong cách" value={value} onChange={(e) => onChange(e.target.value)}
              className="rounded bg-zinc-800 px-1 py-1">
        <option value="">🎨 Để đạo diễn chọn theo câu chuyện</option>
        {packs.map((p) => <option key={p.id} value={p.id}>🎨 {p.name} — {p.suits}</option>)}
      </select>
      {pick && <span className="text-[10px] text-zinc-400">{pick.core.join(' · ')}</span>}
    </span>
  )
}
