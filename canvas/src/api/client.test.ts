import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_BASE, FlowKitError, api, mediaUrl } from './client'

const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200 })

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('sends JSON PATCH for scene updates', async () => {
    const f = vi.fn().mockResolvedValue(ok({ id: 's1' }))
    vi.stubGlobal('fetch', f)
    await api.patchScene('s1', { prompt: 'x' })
    expect(f).toHaveBeenCalledWith(`${API_BASE}/api/scenes/s1`, expect.objectContaining({
      method: 'PATCH', body: JSON.stringify({ prompt: 'x' }),
    }))
  })

  it('turns FastAPI detail into FlowKitError with a Flow error code', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'PUBLIC_ERROR_UNSAFE_GENERATION: blocked' }), { status: 502 })))
    const err = await api.health().catch((e) => e)
    expect(err).toBeInstanceOf(FlowKitError)
    expect(err.status).toBe(502)
    expect(err.code).toBe('PUBLIC_ERROR_UNSAFE_GENERATION')
  })

  it('reports NETWORK when FlowKit is down', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const err = await api.listProjects().catch((e) => e)
    expect(err.code).toBe('NETWORK')
  })

  it('sends multipart upload without forcing a JSON content type', async () => {
    const f = vi.fn().mockResolvedValue(ok({ id: 'c1' }))
    vi.stubGlobal('fetch', f)
    await api.uploadCharacterImage('c1', 'p1', new File(['x'], 'a.png', { type: 'image/png' }))
    const init = f.mock.calls[0][1]
    expect(init.body).toBeInstanceOf(FormData)
    expect(init.headers).toBeUndefined()
  })

  it('rewrites file:// media to the /api/files endpoint', () => {
    expect(mediaUrl('file:///home/u/out/a.mp4'))
      .toBe(`${API_BASE}/api/files?path=${encodeURIComponent('file:///home/u/out/a.mp4')}`)
    expect(mediaUrl('https://x/y.jpg')).toBe('https://x/y.jpg')
    expect(mediaUrl(null)).toBeNull()
  })
})
