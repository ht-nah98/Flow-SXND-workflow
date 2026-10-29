import { useMemo, useRef, useState } from 'react'
import { mediaCrossOrigin, mediaUrl } from '../api/client'
import { useCanvasActions } from '../canvas/actions-context'
import { FILM_MODE_LABEL } from '../components/FilmModeSelect'
import { TYPE_ICON } from '../graph/colors'
import { sceneMedia, type AssetNodeData, type FinalNodeData, type SceneNodeData } from '../graph/mapping'
import { STATUS_TEXT, SceneBody, sceneStatus } from '../nodes/SceneNode'
import { sceneTitle } from '../nodes/ScriptNode'
import { JOIN_ICON, JOIN_LABEL, filmTimeline, segmentAt, type Segment } from './filmTimeline'

const TYPE_LABEL: Record<string, string> = { character: 'Nhân vật', location: 'Bối cảnh', visual_asset: 'Đạo cụ' }
const STATUS_TONE = { done: 'bg-emerald-700', busy: 'bg-sky-700', failed: 'bg-red-700', stale: 'bg-amber-700', todo: 'bg-zinc-700' }
type SceneRow = { id: string; data: SceneNodeData }
type AssetRow = { id: string; data: AssetNodeData }
/** play() returns a promise in modern browsers, undefined in older ones; a refused autoplay is not an error here. */
const safePlay = (v: HTMLVideoElement | null) => { try { void v?.play()?.catch(() => {}) } catch { /* not supported */ } }
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

/** Storyboard (rebuilt 22/10 — "khung lệch, kết quả nằm tít dưới"): laid out like the user's Kling/Artlist sample —
 *  the cut film on top, the shots below as a grid of equal cards that light up while the film plays, a timeline of
 *  the cut with how each shot is entered, and a detail panel with the same tools as the canvas node. The asset ×
 *  scene matrix moved to its own tab. */
export function Storyboard({ scenes, assets, films, onOpen }: {
  scenes: SceneRow[]
  assets: AssetRow[]
  films: FinalNodeData[]
  onOpen: (nodeId: string) => void
}) {
  const [tab, setTab] = useState<'board' | 'assets'>('board')
  const [selected, setSelected] = useState<string | null>(null)
  const [t, setT] = useState(0)
  const player = useRef<HTMLVideoElement>(null)
  const film = films.find((f) => f.url) ?? films[0]
  const segs = useMemo(() => filmTimeline(film?.run), [film?.run])
  const playing = segmentAt(segs, t)
  const segOf = useMemo(() => new Map(segs.map((s, i) => [s.sceneId, i])), [segs])
  const vertical = scenes[0]?.data.orientation === 'VERTICAL'
  const counts = scenes.reduce<Record<string, number>>((c, s) => ({ ...c, [sceneStatus(s.data)]: (c[sceneStatus(s.data)] ?? 0) + 1 }), {})
  const detail = scenes.find((s) => s.id === selected)

  const seek = (i: number) => {
    const v = player.current
    if (!v || !segs[i]) return
    v.currentTime = segs[i].start + 0.05
    setT(v.currentTime)
    safePlay(v)
  }

  if (!scenes.length) return <p className="p-6 text-zinc-400">Project chưa có cảnh nào.</p>
  return (
    <div className="flex h-full min-h-0" data-testid="storyboard">
      <div className="nowheel flex min-w-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
        <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-base font-semibold text-zinc-100">🎞 {film?.video.title ?? 'Phim'}</h2>
          <span className="text-xs text-zinc-400">
            {film?.video.duration != null && `${fmt(film.video.duration)} · `}{scenes.length} shot
            {film?.run?.plan.brief?.film_mode && ` · ${FILM_MODE_LABEL[film.run.plan.brief.film_mode].split(' — ')[0]}`}
          </span>
          <span className="flex gap-1 text-[11px]">
            {(Object.keys(STATUS_TEXT) as (keyof typeof STATUS_TEXT)[]).filter((k) => counts[k]).map((k) => (
              <span key={k} className={`rounded px-1.5 py-0.5 text-white ${STATUS_TONE[k]}`}>{STATUS_TEXT[k]} {counts[k]}</span>
            ))}
          </span>
        </header>

        <section className="flex flex-col items-center gap-2">
          <div className={`w-full ${vertical ? 'max-w-[min(360px,calc(52vh*9/16))]' : 'max-w-[min(880px,calc(46vh*16/9))]'}`}>
            {film?.url ? (
              <video ref={player} src={mediaUrl(film.url) ?? undefined} crossOrigin={mediaCrossOrigin(film.url)} controls playsInline
                     aria-label="Phim hoàn chỉnh" onTimeUpdate={(e) => setT(e.currentTarget.currentTime)}
                     className={`w-full rounded-lg bg-black ${vertical ? 'aspect-[9/16]' : 'aspect-video'}`} />
            ) : (
              <div className={`flex w-full items-center justify-center rounded-lg border border-dashed border-zinc-700 text-sm text-zinc-500 ${vertical ? 'aspect-[9/16]' : 'aspect-video'}`}>
                Phim chưa ghép — đủ clip thì bấm "🎬 Ghép phim" trên node 🎞 ở canvas
              </div>
            )}
          </div>
          {segs.length > 0 && <Timeline segs={segs} playing={playing} t={t} scenes={scenes} onSeek={seek} />}
        </section>

        <div className="flex gap-1 border-b border-zinc-800" role="tablist">
          {([['board', '🎬 Storyboard'], ['assets', '🧩 Asset × cảnh']] as const).map(([k, label]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                    className={`rounded-t px-3 py-1.5 text-xs ${tab === k ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-zinc-200'}`}>{label}</button>
          ))}
        </div>

        {tab === 'board' ? (
          <div className={`grid gap-3 ${vertical ? 'grid-cols-[repeat(auto-fill,minmax(150px,1fr))]' : 'grid-cols-[repeat(auto-fill,minmax(220px,1fr))]'}`}>
            {scenes.map((s) => {
              const i = segOf.get(s.data.scene.id)
              return (
                <ShotCard key={s.id} row={s} seg={i != null ? segs[i] : undefined} selected={selected === s.id}
                          progress={i != null && i === playing ? (t - segs[i].start) / segs[i].len : null}
                          onSelect={() => { setSelected(s.id); if (i != null) seek(i) }} />
              )
            })}
          </div>
        ) : (
          <AssetMatrix scenes={scenes} assets={assets} onSelect={setSelected} />
        )}
      </div>

      {detail && (
        <aside className="nowheel flex w-[420px] shrink-0 flex-col gap-2 overflow-y-auto border-l border-zinc-800 bg-zinc-900 p-3 text-[12px]"
               aria-label="Chi tiết shot">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-zinc-100">Shot {detail.data.scene.display_order + 1}</span>
            <span className="min-w-0 flex-1 truncate text-zinc-400">{sceneTitle(detail.data.scene.prompt)}</span>
            <button className="rounded bg-zinc-800 px-2 py-0.5 text-[11px] hover:bg-zinc-700" onClick={() => onOpen(detail.id)}>Mở trên canvas</button>
            <button className="text-zinc-500 hover:text-white" aria-label="Đóng chi tiết" onClick={() => setSelected(null)}>✕</button>
          </div>
          <SceneBody key={detail.id} data={detail.data} />
        </aside>
      )}
    </div>
  )
}

function Timeline({ segs, playing, t, scenes, onSeek }: {
  segs: Segment[]; playing: number; t: number; scenes: SceneRow[]; onSeek: (i: number) => void
}) {
  const byScene = new Map(scenes.map((s) => [s.data.scene.id, s.data]))
  return (
    <div className="flex w-full max-w-[880px] items-stretch gap-0.5" aria-label="Dòng thời gian phim">
      {segs.map((s, i) => {
        const d = byScene.get(s.sceneId)
        return (
          <div key={`${s.sceneId}-${i}`} className="flex min-w-0 items-stretch gap-0.5" style={{ flex: `${Math.max(s.len, 0.5)} 1 0` }}>
            {i > 0 && (
              <span className="flex w-4 shrink-0 items-center justify-center text-[10px] text-zinc-400" title={JOIN_LABEL[s.join]}>
                {JOIN_ICON[s.join]}
              </span>
            )}
            <button onClick={() => onSeek(i)} title={`Shot ${s.order} · ${s.len.toFixed(1)}s`}
                    className={`relative h-7 min-w-0 flex-1 overflow-hidden rounded text-[10px] ${i === playing ? 'bg-amber-600 text-black' : `${d ? STATUS_TONE[sceneStatus(d)] : 'bg-zinc-700'} text-white`}`}>
              {i === playing && <span className="absolute inset-y-0 left-0 bg-amber-300/60" style={{ width: `${Math.min(100, ((t - s.start) / s.len) * 100)}%` }} />}
              <span className="relative">{s.order} · {s.len.toFixed(1)}s</span>
            </button>
          </div>
        )
      })}
    </div>
  )
}

function ShotCard({ row, seg, selected, progress, onSelect }: {
  row: SceneRow; seg?: Segment; selected: boolean; progress: number | null; onSelect: () => void
}) {
  const { data: d } = row
  const m = sceneMedia(d.scene, d.orientation)
  const st = sceneStatus(d)
  const vertical = d.orientation === 'VERTICAL'
  return (
    <button onClick={onSelect} aria-label={`Shot ${d.scene.display_order + 1}`} aria-pressed={selected}
            className={`group flex flex-col gap-1.5 rounded-lg bg-zinc-900 p-1.5 text-left ring-2 transition ${progress != null ? 'ring-amber-400' : selected ? 'ring-sky-500' : 'ring-transparent hover:ring-zinc-600'}`}>
      <div className={`relative w-full overflow-hidden rounded bg-zinc-800 ${vertical ? 'aspect-[9/16]' : 'aspect-video'}`}>
        <Thumb video={m.videoUrl} image={m.imageUrl} />
        <span className="absolute left-1 top-1 rounded bg-black/70 px-1.5 text-[11px] font-semibold text-white">
          {String(d.scene.display_order + 1).padStart(2, '0')}
        </span>
        {seg && <span className="absolute right-1 top-1 rounded bg-black/70 px-1.5 text-[10px] text-zinc-200">{seg.len.toFixed(1)}s</span>}
        {seg && seg.join !== 'cut' && (
          <span className="absolute bottom-1 left-1 rounded bg-black/70 px-1 text-[10px]" title={`Vào từ shot trước: ${JOIN_LABEL[seg.join]}`}>
            {JOIN_ICON[seg.join]}
          </span>
        )}
        <span className={`absolute bottom-1 right-1 rounded px-1.5 text-[10px] text-white ${STATUS_TONE[st]}`}>{STATUS_TEXT[st]}</span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded bg-zinc-800">
        {progress != null && <div className="h-full bg-amber-400" style={{ width: `${Math.min(100, progress * 100)}%` }} />}
      </div>
      <div className="line-clamp-2 h-8 text-[11px] font-medium leading-4 text-zinc-200" title={sceneTitle(d.scene.prompt)}>
        {sceneTitle(d.scene.prompt)}
      </div>
      <div className="flex min-h-3 flex-wrap gap-1">
        {d.assets.map((a) => <span key={a.id} title={a.name} className="h-2.5 w-2.5 rounded-full" style={{ background: a.color }} />)}
      </div>
    </button>
  )
}

/** A still for the card: the clip's frame at 0.5s (no player until hovered), else the keyframe/scene image. */
function Thumb({ video, image }: { video: string | null; image: string | null }) {
  const actions = useCanvasActions()
  const ref = useRef<HTMLVideoElement>(null)
  const [broken, setBroken] = useState(false)
  const v = mediaUrl(video)
  const img = mediaUrl(image)
  if (v && !broken) {
    return (
      <video ref={ref} src={`${v}#t=0.5`} crossOrigin={mediaCrossOrigin(video)} preload="metadata" muted playsInline loop
             className="h-full w-full object-cover"
             onMouseEnter={() => safePlay(ref.current)}
             onMouseLeave={() => { ref.current?.pause() }}
             onError={() => { setBroken(true); void actions.refreshUrls() }} />
    )
  }
  if (img) return <img src={img} crossOrigin={mediaCrossOrigin(image)} alt="" className="h-full w-full object-cover" />
  return <span className="flex h-full items-center justify-center text-[11px] text-zinc-500">{broken ? '↻ đang làm mới link…' : 'chưa có hình'}</span>
}

function Avatar({ a }: { a: AssetNodeData }) {
  const [bad, setBad] = useState(false)
  const src = mediaUrl(a.character.reference_image_url)
  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-zinc-800 text-[11px] font-bold"
          style={{ outline: `2px solid ${a.color}`, color: a.color }}>
      {src && !bad
        ? <img src={src} crossOrigin={mediaCrossOrigin(a.character.reference_image_url)} alt="" className="h-full w-full object-cover" onError={() => setBad(true)} />
        : a.character.name.slice(0, 1).toUpperCase()}
    </span>
  )
}

function AssetMatrix({ scenes, assets, onSelect }: { scenes: SceneRow[]; assets: AssetRow[]; onSelect: (id: string) => void }) {
  const [hover, setHover] = useState<{ asset?: string; scene?: string }>({})
  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-0 text-[11px]">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-20 min-w-[200px] bg-zinc-950 p-1.5 text-left font-normal text-zinc-500">Asset ╲ Shot</th>
            {scenes.map((s) => (
              <th key={s.id} className={`sticky top-0 z-10 w-9 min-w-9 bg-zinc-950 p-1 font-semibold ${hover.scene === s.id ? 'text-white' : 'text-zinc-400'}`}>
                <button onClick={() => onSelect(s.id)} title={sceneTitle(s.data.scene.prompt)}>{s.data.scene.display_order + 1}</button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {assets.map(({ id: aid, data: a }) => (
            <tr key={aid} onMouseEnter={() => setHover({ asset: aid })} onMouseLeave={() => setHover({})}>
              <td className={`sticky left-0 z-10 border-t border-zinc-800 px-1.5 py-1 ${hover.asset === aid ? 'bg-zinc-800' : 'bg-zinc-950'}`}>
                <div className="flex items-center gap-2">
                  <Avatar a={a} />
                  <div className="min-w-0">
                    <div className="truncate font-semibold" style={{ color: a.color }}>{a.character.name}</div>
                    <div className="text-[10px] text-zinc-500">
                      {TYPE_ICON[a.character.entity_type]} {TYPE_LABEL[a.character.entity_type] ?? a.character.entity_type} · {a.uses} shot
                    </div>
                  </div>
                </div>
              </td>
              {scenes.map(({ id: sid, data: d }) => {
                const used = d.assets.some((x) => x.id === a.character.id)
                return (
                  <td key={sid} onMouseEnter={() => setHover({ asset: aid, scene: sid })}
                      className={`border-t border-zinc-800 text-center ${hover.asset === aid || hover.scene === sid ? 'bg-zinc-800/60' : ''}`}
                      aria-label={used ? `${a.character.name} có trong cảnh ${d.scene.display_order + 1}` : undefined}>
                    {used ? <span className="inline-block h-3 w-3 rounded-full align-middle" style={{ background: a.color }} />
                          : <span className="text-zinc-800">·</span>}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
