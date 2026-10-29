import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactFlowProvider } from '@xyflow/react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { DirectorRun } from '../api/types'
import { ToastProvider } from '../components/Toast'
import { IdeaNode } from './IdeaNode'

afterEach(() => vi.restoreAllMocks())

const run = (o: Partial<DirectorRun> = {}): DirectorRun => ({
  id: 'r1', project_id: 'p1', stage: 'STORY', status: 'RUNNING', gate: null, error: null,
  brief: { text: 'Hai bạn trẻ làm bánh kem', target_s: 30, orientation: 'HORIZONTAL',
           images: [{ file: '/out/ideas/1-cafe.jpg', note: 'quán của tôi' }] },
  budget: {}, spent: {},
  plan: { brief: { images: [{ file: '/out/ideas/1-cafe.jpg', use: 'location', name: 'Old Cafe', description: 'cafe' }] } },
  created_at: null, updated_at: null, ...o,
})

function setup(r: DirectorRun) {
  render(
    <QueryClientProvider client={new QueryClient()}><ToastProvider><ReactFlowProvider>
      <IdeaNode id="idea:r1" data={{ kind: 'idea', run: r }} type="idea" selected={false} dragging={false}
                zIndex={0} isConnectable deletable={false} selectable draggable positionAbsoluteX={0} positionAbsoluteY={0} />
    </ReactFlowProvider></ToastProvider></QueryClientProvider>,
  )
}

describe('IdeaNode', () => {
  it('shows the idea, how Claude classified each picture, and the writing timeline', async () => {
    vi.spyOn(api, 'runTimeline').mockResolvedValue({
      status: 'RUNNING', stage: 'STORY', gate: null, edit_loops: 0, since: new Date().toISOString(),
      steps: [{ stage: 'BRIEF', attempt: 1, status: 'OK', duration_ms: 80_000, created_at: new Date().toISOString() }],
      typical_ms: { STORY: 120_000, SHOTLIST: 90_000, PROMPTS: 150_000, EDIT_REVIEW: 60_000 },
    })
    setup(run())
    expect(screen.getByText('Hai bạn trẻ làm bánh kem')).toBeTruthy()
    expect(screen.getByText('Bối cảnh: Old Cafe')).toBeTruthy()
    expect(await screen.findByText('Đọc ý tưởng')).toBeTruthy()
    expect(screen.getByText('1:20')).toBeTruthy()
    expect(screen.getByText('Viết câu chuyện…')).toBeTruthy()
    expect(screen.getByText(/Còn khoảng ~7 phút/)).toBeTruthy()
  })

  it('a new idea is editable and only writes the script on request', async () => {
    const patch = vi.spyOn(api, 'patchIdea').mockResolvedValue(run())
    const approve = vi.spyOn(api, 'approveRun').mockResolvedValue(run())
    setup(run({ status: 'WAITING_GATE', gate: 'IDEA', stage: 'BRIEF' }))
    fireEvent.change(screen.getByLabelText('Ý tưởng'), { target: { value: 'Hai bạn trẻ làm bánh kem ở Đà Lạt' } })
    fireEvent.change(screen.getByLabelText('Ghi chú ảnh'), { target: { value: 'quán thật' } })
    fireEvent.change(screen.getByLabelText('Giọng nói'), { target: { value: 'voiceover' } })
    fireEvent.change(screen.getByLabelText('Ngôn ngữ phim'), { target: { value: 'vi' } })
    fireEvent.change(screen.getByLabelText('Mức sáng tạo'), { target: { value: 'bold' } })
    fireEvent.change(screen.getByLabelText('Chế độ phim'), { target: { value: 'keyframe' } })   // B13: the user picks the mode
    fireEvent.click(screen.getByText('✍️ Viết kịch bản (không tốn credit)'))
    await waitFor(() => expect(approve).toHaveBeenCalledWith('r1', 'IDEA'))
    expect(patch).toHaveBeenCalledWith('r1', { text: 'Hai bạn trẻ làm bánh kem ở Đà Lạt', target_s: 30,
                                               orientation: 'HORIZONTAL', voice: 'voiceover', language: 'vi', creativity: 'bold', style_pack: '', film_mode: 'keyframe', notes: { '/out/ideas/1-cafe.jpg': 'quán thật' } })
  })

  it('an unchanged idea goes straight to writing', async () => {
    const patch = vi.spyOn(api, 'patchIdea').mockResolvedValue(run())
    const approve = vi.spyOn(api, 'approveRun').mockResolvedValue(run())
    setup(run({ status: 'WAITING_GATE', gate: 'IDEA', stage: 'BRIEF' }))
    fireEvent.click(screen.getByText('✍️ Viết kịch bản (không tốn credit)'))
    await waitFor(() => expect(approve).toHaveBeenCalledWith('r1', 'IDEA'))
    expect(patch).not.toHaveBeenCalled()
  })

  it('points to the script node once the script is written', () => {
    setup(run({ status: 'WAITING_GATE', gate: 'SCRIPT', stage: 'INGEST' }))
    expect(screen.getByText(/duyệt và tạo ở node 📜 Kịch bản/)).toBeTruthy()
    expect(screen.queryByText(/Duyệt/)).toBeNull()
  })

  it('retries a failed writing step', async () => {
    const retry = vi.spyOn(api, 'retryRun').mockResolvedValue(run())
    setup(run({ status: 'FAILED', stage: 'SHOTLIST', error: 'lint failed' }))
    expect(screen.getByText(/Lỗi khi viết kịch bản \(SHOTLIST\): lint failed/)).toBeTruthy()
    fireEvent.click(screen.getByText('Viết lại từ bước này'))
    await waitFor(() => expect(retry).toHaveBeenCalledWith('r1'))
  })
})
