import { describe, expect, it, vi } from 'vitest'
import { connectEvents, type FlowEvent } from './events'

class FakeWS {
  static instances: FakeWS[] = []
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onmessage: ((m: { data: string }) => void) | null = null
  closed = false
  constructor(public url: string) { FakeWS.instances.push(this) }
  close() { this.closed = true; this.onclose?.() }
}

describe('connectEvents', () => {
  it('parses events, reports status and reconnects after a drop', async () => {
    vi.useFakeTimers()
    const events: FlowEvent[] = []
    const status: boolean[] = []
    const stop = connectEvents({
      url: 'ws://x', onEvent: (e) => events.push(e), onStatus: (o) => status.push(o),
      WebSocketImpl: FakeWS as unknown as typeof WebSocket, maxDelayMs: 1000,
    })
    const first = FakeWS.instances.at(-1)!
    first.onopen!()
    first.onmessage!({ data: JSON.stringify({ type: 'entity_changed', data: { entity: 'scene' } }) })
    first.onmessage!({ data: 'not json' })
    expect(events).toEqual([{ type: 'entity_changed', data: { entity: 'scene' } }])

    first.onclose!()               // agent restarted
    expect(status).toEqual([true, false])
    await vi.advanceTimersByTimeAsync(1000)
    const second = FakeWS.instances.at(-1)!
    expect(second).not.toBe(first)
    second.onopen!()
    expect(status).toEqual([true, false, true])

    stop()
    expect(second.closed).toBe(true)
    await vi.advanceTimersByTimeAsync(5000)
    expect(FakeWS.instances.at(-1)).toBe(second)   // no reconnect after stop
    vi.useRealTimers()
  })
})
