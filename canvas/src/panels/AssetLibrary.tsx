import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, mediaCrossOrigin, mediaUrl } from '../api/client'
import { refreshProjectUrls } from '../lib/refreshUrls'
import { useLibrary } from '../api/queries'
import { useCanvasActions, type XY } from '../canvas/actions-context'

const TABS = [
  { id: 'character', label: 'Nhân vật', types: ['character', 'creature', 'generic_troop', 'faction'] },
  { id: 'location', label: 'Bối cảnh', types: ['location'] },
  { id: 'visual_asset', label: 'Đạo cụ', types: ['visual_asset'] },
] as const
export const CHARACTER_MIME = 'application/x-flowkit-character'

function readPref(): boolean {
  try { return localStorage.getItem('fc.library.open') !== '0' } catch { return true }
}
function writePref(open: boolean) {
  try { localStorage.setItem('fc.library.open', open ? '1' : '0') } catch { /* private mode */ }
}

const brokenUrl = new Map<string, string>()   // asset id → the link that failed (a re-signed link is shown again)

export function AssetLibrary({ attachedIds, dropPoint }: { attachedIds: Set<string>; dropPoint: () => XY }) {
  const a = useCanvasActions()
  const lib = useLibrary()
  const [open, setOpen] = useState(readPref)
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('character')
  const [search, setSearch] = useState('')
  const [form, setForm] = useState<{ name: string; description: string } | null>(null)
  const qc = useQueryClient()
  const [broken, setBroken] = useState<ReadonlySet<string>>(new Set())
  // Flow links expire after ~6h. A library picture can belong to another film, so re-sign through the film that
  // holds the asset; one try per asset, then the empty tile (no broken-image icon).
  const onImgError = (id: string) => {
    if (broken.has(id)) return
    setBroken((b) => new Set(b).add(id))
    void api.characterProjects(id)
      .then((ps) => ps[0] && refreshProjectUrls(ps[0].id))
      .then(() => qc.invalidateQueries({ queryKey: ['library'] }))
      .catch(() => {})
  }
  const types = TABS.find((t) => t.id === tab)!.types as readonly string[]
  const term = search.trim().toLowerCase()
  const items = (lib.data ?? []).filter((c) => types.includes(c.entity_type) &&
    (!term || c.name.toLowerCase().includes(term) || (c.description ?? '').toLowerCase().includes(term)))

  const toggle = () => { setOpen(!open); writePref(!open) }

  if (!open) {
    return <button onClick={toggle} className="absolute left-2 top-2 z-10 rounded bg-zinc-800 px-2 py-1 text-xs">Thư viện ▸</button>
  }

  return (
    <aside data-testid="asset-library"
           className="absolute left-2 top-2 z-10 flex max-h-[calc(100%-16px)] w-[min(280px,calc(100vw-32px))] flex-col gap-2 rounded-xl border border-zinc-800 bg-zinc-950/95 p-2 text-xs"
           onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) e.preventDefault() }}
           onDrop={(e) => {
             const f = e.dataTransfer.files[0]
             if (!f) return
             e.preventDefault()
             void a.createAsset({ name: f.name.replace(/\.[^.]+$/, ''), entity_type: 'visual_asset', description: '' }, dropPoint(), f)
           }}>
      <div className="flex items-center justify-between">
        <span className="font-semibold">Thư viện asset</span>
        <button onClick={toggle} aria-label="Thu gọn thư viện" className="px-1">◂</button>
      </div>
      <div role="tablist" className="flex gap-1">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
                  className={`rounded px-2 py-0.5 ${tab === t.id ? 'bg-sky-700' : 'bg-zinc-800'}`}>{t.label}</button>
        ))}
      </div>
      <input placeholder="Tìm asset…" value={search} onChange={(e) => setSearch(e.target.value)}
             className="rounded bg-zinc-800 px-2 py-1" />
      <div className="grid grid-cols-2 gap-2 overflow-y-auto">
        {items.map((c) => (
          <div key={c.id} draggable data-testid={`lib-${c.id}`}
               onDragStart={(e) => { e.dataTransfer.setData(CHARACTER_MIME, c.id); e.dataTransfer.effectAllowed = 'copy' }}
               className="cursor-grab overflow-hidden rounded border border-zinc-800 bg-zinc-900">
            {c.reference_image_url && !(broken.has(c.id) && c.reference_image_url === brokenUrl.get(c.id))
              ? <img src={mediaUrl(c.reference_image_url)!} crossOrigin={mediaCrossOrigin(c.reference_image_url)} alt="" className="aspect-square w-full object-cover" draggable={false}
                     onError={() => { brokenUrl.set(c.id, c.reference_image_url!); onImgError(c.id) }} />
              : <div className="aspect-square w-full bg-zinc-800" />}
            <div className="flex items-center gap-1 p-1">
              <span className="flex-1 truncate">{c.name}</span>
              {attachedIds.has(c.id) && <span aria-label="Đã dùng trong project" className="text-emerald-400">✓</span>}
            </div>
          </div>
        ))}
      </div>
      {form ? (
        <form className="flex flex-col gap-1" onSubmit={(e) => {
          e.preventDefault()
          if (!form.name.trim()) return
          const type = tab === 'character' ? 'character' : tab
          void a.createAsset({ name: form.name.trim(), entity_type: type, description: form.description }, dropPoint())
          setForm(null)
        }}>
          <input aria-label="Tên asset" placeholder="Tên" value={form.name}
                 onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded bg-zinc-800 px-2 py-1" />
          <textarea aria-label="Mô tả asset" placeholder="Mô tả ngoại hình (tiếng Anh cho Flow)" rows={3} value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })} className="rounded bg-zinc-800 px-2 py-1" />
          <div className="flex gap-1">
            <button type="submit" className="flex-1 rounded bg-sky-700 px-2 py-1">Tạo asset</button>
            <button type="button" onClick={() => setForm(null)} className="rounded bg-zinc-800 px-2 py-1">Huỷ</button>
          </div>
        </form>
      ) : (
        <button onClick={() => setForm({ name: '', description: '' })} className="rounded bg-zinc-800 px-2 py-1">+ Asset mới</button>
      )}
    </aside>
  )
}
