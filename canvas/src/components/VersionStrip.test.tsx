import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { CanvasActionsContext, type CanvasActions } from '../canvas/actions-context'
import { VersionStrip } from './VersionStrip'

const versions = [
  { request_id: 'r2', type: 'REGENERATE_IMAGE', media_id: 'm2', output_url: 'https://i/2', prompt_snapshot: 'new', created_at: null, updated_at: '2' },
  { request_id: 'r1', type: 'GENERATE_IMAGE', media_id: 'm1', output_url: 'https://i/1', prompt_snapshot: null, created_at: null, updated_at: '1' },
]

describe('VersionStrip', () => {
  it('lists versions, marks the current one and restores on click', async () => {
    vi.spyOn(api, 'sceneVersions').mockResolvedValue(versions)
    const restore = vi.fn().mockResolvedValue(undefined)
    const actions = { projectId: 'p1', restore } as unknown as CanvasActions
    render(
      <QueryClientProvider client={new QueryClient()}>
        <CanvasActionsContext.Provider value={actions}>
          <VersionStrip target={{ kind: 'scene', id: 's1', media: 'image', orientation: 'HORIZONTAL' }} currentMediaId="m2" />
        </CanvasActionsContext.Provider>
      </QueryClientProvider>,
    )
    const items = await screen.findAllByRole('button', { name: /Phiên bản/ })
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveAttribute('aria-current', 'true')
    expect(items[1]).toHaveAttribute('title', 'không rõ prompt')
    fireEvent.click(items[1])
    expect(restore).toHaveBeenCalledWith(
      { kind: 'scene', id: 's1', media: 'image', orientation: 'HORIZONTAL' }, versions[1])
  })

  it('re-signs an expired thumbnail once and hides the broken image meanwhile', async () => {
    vi.spyOn(api, 'sceneVersions').mockResolvedValue(versions)
    const refreshUrls = vi.fn().mockResolvedValue(undefined)
    const actions = { projectId: 'p1', refreshUrls } as unknown as CanvasActions
    const { container } = render(
      <QueryClientProvider client={new QueryClient()}>
        <CanvasActionsContext.Provider value={actions}>
          <VersionStrip target={{ kind: 'scene', id: 's1', media: 'image', orientation: 'HORIZONTAL' }} currentMediaId="m2" />
        </CanvasActionsContext.Provider>
      </QueryClientProvider>,
    )
    await screen.findAllByRole('button', { name: /Phiên bản/ })
    fireEvent.error(container.querySelector('img[src="https://i/1"]')!)
    expect(refreshUrls).toHaveBeenCalledTimes(1)
    expect(container.querySelector('img[src="https://i/1"]')).toBeNull()
    expect(container.querySelector('img[src="https://i/2"]')).not.toBeNull()
  })
})
