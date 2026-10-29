import { useState } from 'react'
import { mediaCrossOrigin, mediaUrl } from '../api/client'
import { TYPE_ICON } from '../graph/colors'
import type { AssetChip } from '../graph/mapping'

/** The reference assets a clip is made from: a ring in each asset's colour around its picture. */
export function AssetChips({ assets, size = 'sm' }: { assets: AssetChip[]; size?: 'sm' | 'lg' }) {
  if (!assets.length) return null
  const box = size === 'lg' ? 'h-9 w-9' : 'h-6 w-6'
  return (
    <div className="flex flex-wrap items-center gap-1" aria-label="Asset dùng trong cảnh">
      {assets.map((a) => {
        const src = mediaUrl(a.url)
        return (
          <span key={a.id} title={a.name} data-testid={`chip-${a.id}`}
                className="flex items-center gap-1 rounded-full bg-zinc-800 py-0.5 pl-0.5 pr-2 text-[10px] text-zinc-200"
                style={{ boxShadow: `inset 0 0 0 2px ${a.color}` }}>
            <span className={`${box} shrink-0 overflow-hidden rounded-full bg-zinc-700`} style={{ outline: `2px solid ${a.color}` }}>
              <ChipPicture src={src} url={a.url} icon={TYPE_ICON[a.type] ?? '•'} />
            </span>
            <span className="max-w-[90px] truncate">{a.name}</span>
          </span>
        )
      })}
    </div>
  )
}

/** An expired picture link shows the asset's type icon, not a broken-image glyph (22/10 Storyboard review). */
function ChipPicture({ src, url, icon }: { src: string | null; url: string | null; icon: string }) {
  const [bad, setBad] = useState(false)
  return src && !bad
    ? <img src={src} crossOrigin={mediaCrossOrigin(url)} alt="" className="h-full w-full object-cover" onError={() => setBad(true)} />
    : <span className="flex h-full items-center justify-center">{icon}</span>
}
