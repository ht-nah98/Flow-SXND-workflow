import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactFlowProvider } from '@xyflow/react'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { FlowRequest } from '../api/types'
import { ChoiceDialogProvider } from '../components/ChoiceDialog'
import { ToastProvider } from '../components/Toast'
import { project, scene, video } from '../test/fixtures'
import type { GraphInput } from '../graph/mapping'
import type { GenAction } from '../lib/actions'
import { useActions } from './useActions'

afterEach(() => vi.useRealTimers())

// These waves (image first, then video) only exist when the project opted into image → video.
const imageMode = { project: { ...project, video_mode: 'image' } } as unknown as GraphInput

function Harness({ action }: { action: GenAction }) {
  const actions = useActions('p1', imageMode)
  return <button onClick={() => void actions.run(action)}>run</button>
}

function setup(action: GenAction) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ReactFlowProvider>
        <ToastProvider>
          <ChoiceDialogProvider>
            <Harness action={action} />
          </ChoiceDialogProvider>
        </ToastProvider>
      </ReactFlowProvider>
    </QueryClientProvider>,
  )
}

function ExportHarness() {
  const actions = useActions('p1', undefined)
  return <button onClick={() => void actions.exportProject()}>export</button>
}

function setupExport() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ReactFlowProvider>
        <ToastProvider>
          <ChoiceDialogProvider>
            <ExportHarness />
          </ChoiceDialogProvider>
        </ToastProvider>
      </ReactFlowProvider>
    </QueryClientProvider>,
  )
}

const req = (o: Partial<FlowRequest>): FlowRequest => ({
  id: 'r1', type: 'GENERATE_IMAGE', status: 'PENDING', project_id: 'p1', video_id: 'v1', scene_id: 's1',
  character_id: null, orientation: 'HORIZONTAL', media_id: null, output_url: null, error_message: null,
  created_at: null, updated_at: null, ...o,
})

describe('useActions.run — video-stale waves', () => {
  it('submits images, waits for them, then submits video only for scenes whose image succeeded', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ status: 'ok', extension_connected: true, media_provider: 'flow' })
    const submit = vi.spyOn(api, 'submitRequests')
      .mockResolvedValueOnce([req({ id: 'img-s1', type: 'REGENERATE_IMAGE', scene_id: 's1' })])
      .mockResolvedValueOnce([req({ id: 'vid-s1', type: 'REGENERATE_VIDEO', scene_id: 's1' })])
    vi.spyOn(api, 'getRequest')
      .mockResolvedValueOnce(req({ id: 'img-s1', type: 'REGENERATE_IMAGE', scene_id: 's1', status: 'PROCESSING' }))
      .mockResolvedValue(req({ id: 'img-s1', type: 'REGENERATE_IMAGE', scene_id: 's1', status: 'COMPLETED' }))

    const s1 = scene({ id: 's1' })
    const v1 = video({ id: 'v1' })
    setup({ kind: 'video-stale', video: v1, scenes: [s1], stale: new Set(['s1']) })

    fireEvent.click(screen.getByText('run'))
    await screen.findByRole('dialog')
    fireEvent.click(screen.getByRole('button', { name: /Tạo 1 video/ }))
    vi.useFakeTimers()

    // first wave (images) goes out immediately
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(submit).toHaveBeenNthCalledWith(1, [expect.objectContaining({ type: 'REGENERATE_IMAGE', scene_id: 's1' })])
    expect(submit).toHaveBeenCalledTimes(1)

    // second wave (video) must not be submitted before the image is terminal
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(submit).toHaveBeenCalledTimes(2)
    expect(submit).toHaveBeenNthCalledWith(2, [expect.objectContaining({ type: 'REGENERATE_VIDEO', scene_id: 's1' })])
  })

  it('skips the video wave for a scene whose image request failed', async () => {
    vi.spyOn(api, 'health').mockResolvedValue({ status: 'ok', extension_connected: true, media_provider: 'flow' })
    const submit = vi.spyOn(api, 'submitRequests')
      .mockResolvedValueOnce([req({ id: 'img-s1', type: 'REGENERATE_IMAGE', scene_id: 's1' })])
    vi.spyOn(api, 'getRequest').mockResolvedValue(
      req({ id: 'img-s1', type: 'REGENERATE_IMAGE', scene_id: 's1', status: 'FAILED', error_message: 'boom' }))

    const s1 = scene({ id: 's1' })
    const v1 = video({ id: 'v1' })
    setup({ kind: 'video-stale', video: v1, scenes: [s1], stale: new Set(['s1']) })

    fireEvent.click(screen.getByText('run'))
    await screen.findByRole('dialog')
    fireEvent.click(screen.getByRole('button', { name: /Tạo 1 video/ }))
    vi.useFakeTimers()
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })

    expect(submit).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/thất bại/)).toBeInTheDocument()
  })
})

describe('useActions.exportProject', () => {
  it('downloads the zip and reports how many files were skipped', async () => {
    vi.spyOn(api, 'exportProject').mockResolvedValue({
      project_dir: 'file:///out/p', zip_path: 'file:///out/p/_export/p-1.zip',
      downloaded: 3, skipped: [{ kind: 'scene_video', id: 's1', reason: 'unreachable or expired' }],
    })
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)

    setupExport()
    fireEvent.click(screen.getByText('export'))

    await screen.findByText(/Đã xuất 3 file.*bỏ qua 1/)
    expect(open).toHaveBeenCalledWith(
      `http://127.0.0.1:8110/api/files?path=${encodeURIComponent('file:///out/p/_export/p-1.zip')}`, '_blank')
  })

  it('shows the error toast when export fails', async () => {
    vi.spyOn(api, 'exportProject').mockRejectedValue(new Error('Project not found'))
    setupExport()
    fireEvent.click(screen.getByText('export'))
    await screen.findByText(/Project not found/)
  })
})
