import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CanvasActionsContext, type CanvasActions } from '../canvas/actions-context'
import { MediaView } from './MediaView'

afterEach(() => vi.useRealTimers())

const actions = { refreshUrls: vi.fn().mockResolvedValue(undefined) } as unknown as CanvasActions
const img = (container: HTMLElement) => container.querySelector('img')!

describe('MediaView', () => {
  it('retries a transient failure, then auto-refreshes the link once, then shows the expired state', async () => {
    vi.useFakeTimers()
    const refreshUrls = vi.fn().mockResolvedValue(undefined)
    const a = { refreshUrls } as unknown as CanvasActions
    const { container } = render(<CanvasActionsContext.Provider value={a}>
      <MediaView url="https://x/y.jpg" kind="image" />
    </CanvasActionsContext.Provider>)
    const failAll = async () => {
      for (let i = 0; i < 3; i++) {
        fireEvent.error(img(container))
        await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
      }
    }
    await failAll()
    expect(refreshUrls).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Link hết hạn')).toBeNull()
    await failAll()
    expect(refreshUrls).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Link hết hạn')).toBeInTheDocument()
  })

  it('resets retry state when the url prop changes', async () => {
    vi.useFakeTimers()
    const { container, rerender } = render(<CanvasActionsContext.Provider value={actions}>
      <MediaView url="https://x/a.jpg" kind="image" />
    </CanvasActionsContext.Provider>)
    for (let i = 0; i < 6; i++) {
      fireEvent.error(img(container))
      await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    }
    expect(screen.getByText('Link hết hạn')).toBeInTheDocument()
    rerender(<CanvasActionsContext.Provider value={actions}>
      <MediaView url="https://x/b.jpg" kind="image" />
    </CanvasActionsContext.Provider>)
    expect(screen.queryByText('Link hết hạn')).toBeNull()
    expect(img(container)).toBeInTheDocument()
  })

  it('retries with the same src (signed URLs must not be altered)', async () => {
    vi.useFakeTimers()
    const { container } = render(<CanvasActionsContext.Provider value={actions}>
      <MediaView url="https://x/y.jpg?Expires=1&Signature=abc" kind="image" />
    </CanvasActionsContext.Provider>)
    const before = img(container).getAttribute('src')
    fireEvent.error(img(container))
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(img(container).getAttribute('src')).toBe(before)
  })

  it('sets crossorigin only for local file:// media', () => {
    const wrap = (url: string) => render(<CanvasActionsContext.Provider value={actions}>
      <MediaView url={url} kind="image" />
    </CanvasActionsContext.Provider>)
    expect(img(wrap('file:///tmp/a.png').container).getAttribute('crossorigin')).toBe('anonymous')
    expect(img(wrap('https://flow-content.google/a.png').container).hasAttribute('crossorigin')).toBe(false)
  })
})
