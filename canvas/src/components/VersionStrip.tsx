import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { createPortal } from 'react-dom'
import { MediaView } from './MediaView'
import { api, mediaCrossOrigin, mediaUrl } from '../api/client'
import { projectKey } from '../api/queries'
import { useCanvasActions, type VersionTarget } from '../canvas/actions-context'

export function VersionStrip({ target, currentMediaId }: { target: VersionTarget; currentMediaId: string | null }) {
  const a = useCanvasActions()
  // Keyed by url: a re-signed link is a new key, so it gets rendered again.
  const [failed, setFailed] = useState<ReadonlySet<string>>(new Set())
  const [comparing, setComparing] = useState(false)
  const onError = (url: string) => {
    setFailed((f) => new Set(f).add(url))
    void a.refreshUrls()
  }
  const key = target.kind === 'character' ? ['character', target.id] : ['scene', target.id, target.media, target.orientation]
  const q = useQuery({
    queryKey: [...projectKey(a.projectId), 'versions', ...key],
    queryFn: () => target.kind === 'character'
      ? api.characterVersions(target.id)
      : api.sceneVersions(target.id, target.media, target.orientation),
  })
  // A request the worker skipped as "already completed" points at the same clip: one picture, one version.
  const list = (q.data ?? []).filter((v, i, all) => !v.media_id || all.findIndex((w) => w.media_id === v.media_id) === i)
  if (list.length === 0) return null
  const isVideo = target.kind === 'scene' && target.media === 'video'
  const vertical = 'orientation' in target && target.orientation === 'VERTICAL'
  return (
    <div className="nodrag nowheel">
      <div className="mb-0.5 flex items-center text-[10px] uppercase tracking-wide text-zinc-400">
        Phiên bản {isVideo ? 'video' : 'ảnh'} ({list.length})
        {list.length > 1 && (
          <button className="ml-auto rounded bg-zinc-700 px-1.5 normal-case text-zinc-200" onClick={() => setComparing(true)}>⇔ So sánh</button>
        )}
      </div>
      {comparing && createPortal(
        <div role="dialog" aria-label="So sánh phiên bản" className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6"
             onClick={() => setComparing(false)}>
          <div className="flex max-h-full max-w-full gap-4 overflow-auto rounded-xl bg-zinc-900 p-4" onClick={(e) => e.stopPropagation()}>
            {list.map((v, i) => {
              const current = v.media_id === currentMediaId
              return (
                <div key={v.request_id} className={`flex ${vertical ? 'w-[260px]' : 'w-[420px]'} shrink-0 flex-col gap-2`}>
                  <div className="flex items-center text-sm">
                    <b>Bản {list.length - i}</b>
                    {current && <span className="ml-2 rounded bg-sky-800 px-1.5 text-xs">đang dùng</span>}
                  </div>
                  <MediaView url={v.output_url} kind={isVideo ? 'video' : 'image'} vertical={vertical} />
                  <button disabled={current} className="rounded bg-emerald-700 px-2 py-1 text-sm disabled:opacity-40"
                          onClick={() => { void a.restore(target, v); setComparing(false) }}>
                    {current ? 'Đang dùng bản này' : 'Dùng bản này'}
                  </button>
                </div>
              )
            })}
          </div>
        </div>, document.body)}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {list.map((v, i) => {
          const current = v.media_id === currentMediaId
          const src = v.output_url && !failed.has(v.output_url) ? mediaUrl(v.output_url) : null
          return (
            <button key={v.request_id} aria-label={`Phiên bản ${list.length - i}`} aria-current={current}
                    title={v.prompt_snapshot ?? 'không rõ prompt'}
                    onClick={() => { if (!current) void a.restore(target, v) }}
                    className={`${'orientation' in target && target.orientation === 'VERTICAL' ? 'h-16 w-9' : 'h-10 w-16'} shrink-0 overflow-hidden rounded border ${current ? 'border-sky-400' : 'border-zinc-700 hover:border-zinc-400'}`}>
              {src && (isVideo
                ? <video src={src} crossOrigin={mediaCrossOrigin(v.output_url)} preload="metadata" muted className="h-full w-full object-cover"
                         onError={() => onError(v.output_url!)} />
                : <img src={src} crossOrigin={mediaCrossOrigin(v.output_url)} alt="" className="h-full w-full object-cover"
                       onError={() => onError(v.output_url!)} />)}
            </button>
          )
        })}
      </div>
    </div>
  )
}
