export interface FlowEvent { type: string; data: Record<string, unknown> }

export function connectEvents(opts: {
  url: string
  onEvent: (e: FlowEvent) => void
  onStatus: (open: boolean) => void
  WebSocketImpl?: typeof WebSocket
  maxDelayMs?: number
}): () => void {
  const WS = opts.WebSocketImpl ?? WebSocket
  const maxDelay = opts.maxDelayMs ?? 10_000
  let delay = 1000
  let stopped = false
  let socket: WebSocket | null = null
  let timer: ReturnType<typeof setTimeout> | null = null

  const open = () => {
    socket = new WS(opts.url)
    socket.onopen = () => { delay = 1000; opts.onStatus(true) }
    socket.onmessage = (m: MessageEvent | { data: string }) => {
      try {
        const e = JSON.parse(String(m.data)) as FlowEvent
        if (e && typeof e.type === 'string') opts.onEvent(e)
      } catch { /* ignore non-JSON frames */ }
    }
    socket.onclose = () => {
      opts.onStatus(false)
      if (stopped) return
      timer = setTimeout(open, delay)
      delay = Math.min(delay * 2, maxDelay)
    }
  }
  open()
  return () => {
    stopped = true
    if (timer) clearTimeout(timer)
    socket?.close()
  }
}
