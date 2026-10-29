import { useEffect, useRef, useState } from 'react'
import { mediaCrossOrigin, mediaUrl } from '../api/client'
import { useCanvasActions } from '../canvas/actions-context'

/** Perf (19/10): a film of 55 finished clips mounted 55 video players at once. A player is made the first time its box
 * comes on screen and then kept (no reload while panning back and forth). Without IntersectionObserver: at once. */
function useSeen(ref: React.RefObject<HTMLElement | null>, wanted: boolean) {
  const [seen, setSeen] = useState(typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    if (!wanted || seen || !ref.current) return
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) setSeen(true) }, { rootMargin: '200px' })
    io.observe(ref.current)
    return () => io.disconnect()
  }, [ref, wanted, seen])
  return seen
}

const MAX_RETRIES = 2
const RETRY_DELAY_MS = 500

/** `vertical` frames 9:16 media in a 9:16 box; the default 16:9 box would crop a vertical clip to its middle. */
export function MediaView({ url, kind, busy, vertical }: { url: string | null; kind: 'image' | 'video'; busy?: boolean; vertical?: boolean }) {
  const actions = useCanvasActions()
  const src = mediaUrl(url)
  const [retries, setRetries] = useState(0)
  const [broken, setBroken] = useState(false)
  const [autoRefreshed, setAutoRefreshed] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // A failed load may be transient (busy local backend, momentary network
  // blip) rather than a truly expired signed URL — retry a couple of times
  // before showing the "expired" state.
  useEffect(() => {
    setRetries(0)
    setBroken(false)
    setAutoRefreshed(false)
    return () => { if (timer.current) clearTimeout(timer.current) }
  }, [url])

  const onError = () => {
    if (retries >= MAX_RETRIES) {
      if (autoRefreshed) { setBroken(true); return }
      // Most likely an expired signed URL: re-sign once on our own before
      // asking the user. A new URL resets this state via the effect above.
      setAutoRefreshed(true)
      void actions.refreshUrls().then(() => setRetries(0))
      return
    }
    timer.current = setTimeout(() => setRetries((r) => r + 1), RETRY_DELAY_MS * (retries + 1))
  }
  const crossOrigin = mediaCrossOrigin(url)
  const box = useRef<HTMLDivElement>(null)
  const seen = useSeen(box, kind === 'video' && !!src)

  return (
    <div ref={box} data-testid={`media-${kind}`} className={`relative ${vertical ? 'mx-auto aspect-[9/16] w-3/4' : 'aspect-video w-full'} overflow-hidden rounded-md bg-zinc-800`}>
      {src && !broken && (kind === 'image'
        ? <img key={retries} src={src} crossOrigin={crossOrigin} alt="" className="h-full w-full object-cover" onError={onError} />
        : seen && <video key={retries} src={src} crossOrigin={crossOrigin} controls preload="metadata" className="nodrag h-full w-full object-contain" onError={onError} />)}
      {!src && <div className="flex h-full items-center justify-center text-[11px] text-zinc-500">
        {kind === 'image' ? 'Chưa có ảnh' : 'Chưa có video'}</div>}
      {src && broken && (
        <div className="flex h-full flex-col items-center justify-center gap-1 text-[11px] text-zinc-300">
          Link hết hạn
          <button className="nodrag rounded bg-zinc-700 px-2 py-0.5"
                  onClick={() => { setBroken(false); setRetries(0); void actions.refreshUrls() }}>
            Làm mới link
          </button>
        </div>
      )}
      {busy && <div className="absolute inset-0 flex items-center justify-center bg-black/50 text-xs">⏳ Đang tạo…</div>}
    </div>
  )
}
