import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactFlowProvider } from '@xyflow/react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { DirectorRun, FilmReviewState } from '../api/types'
import { ToastProvider } from '../components/Toast'
import type { ReviewNodeData } from '../graph/mapping'
import { video } from '../test/fixtures'
import { ReviewNode } from './ReviewNode'

const run = { id: 'r1', project_id: 'p1', stage: 'DONE', status: 'DONE', gate: null, error: null, brief: { text: 'x' },
              budget: {}, spent: {}, plan: { ids: { scenes: { SH02: 's2' } } } } as unknown as DirectorRun
const state: FilmReviewState = { job: null, reviews: [{
  id: 'a', created_at: '2026-10-21T09:00:00Z', final_path: '/f.mp4', note: '', film_duration_s: 20,
  clips: [{ scene: 1, shot_id: 'SH01', idea: 'a', used_in_film_s: [0, 10], film_start_s: 0 },
          { scene: 2, shot_id: 'SH02', idea: 'b', used_in_film_s: [0, 10], film_start_s: 10 }],
  summary: 'Phim đọc được nhưng cảnh kết lật ngược.', strengths: ['ánh sáng'],
  scores: [{ layer: 'story', score: 6, note: 'ổn' }, { layer: 'continuity', score: 4, note: 'bếp đổi' }],
  findings: [{ id: 'F1', layer: 'clips', severity: 'CRITICAL', scene: 2, shot_id: 'SH02', clip_t: 5, film_t: 15,
               title: 'Bình rót vào cốc xanh', evidence: 'khung 6–9', cause: 'prompt', cause_detail: 'giữ bình ngang miệng cốc',
               fix: 'bình đứng yên trên bàn', action: 'rewrite_prompt', rule: 'Never hold a pourable at a rim.' }],
}] }

function setup(data: Partial<ReviewNodeData> = {}) {
  render(
    <QueryClientProvider client={new QueryClient()}><ToastProvider><ReactFlowProvider>
      <ReviewNode id="review:r1" type="review" selected={false} dragging={false} zIndex={0} isConnectable deletable={false}
                  selectable draggable positionAbsoluteX={0} positionAbsoluteY={0}
                  data={{ kind: 'review', run, video: video(), sceneKeys: { SH02: 'scene:s2' }, filmReady: true, ...data }} />
    </ReactFlowProvider></ToastProvider></QueryClientProvider>,
  )
}

afterEach(() => vi.restoreAllMocks())

describe('ReviewNode (Agent Review)', () => {
  it('shows the scores, the summary and a finding with its cause and fix', async () => {
    vi.spyOn(api, 'filmReviews').mockResolvedValue(state)
    setup()
    expect(await screen.findByText('Phim đọc được nhưng cảnh kết lật ngược.')).toBeTruthy()
    expect(screen.getByText('6/10')).toBeTruthy()
    fireEvent.click(screen.getByText('Bình rót vào cốc xanh'))
    expect(screen.getByText('bình đứng yên trên bàn')).toBeTruthy()
    expect(screen.getByText(/câu chữ prompt/)).toBeTruthy()
    expect(screen.getByText('→ Tới cảnh 2')).toBeTruthy()
  })

  it('sends the user note with a new review', async () => {
    vi.spyOn(api, 'filmReviews').mockResolvedValue({ job: null, reviews: [] })
    const start = vi.spyOn(api, 'startFilmReview').mockResolvedValue({ status: 'RUNNING', error: null, started: 0, note: '' })
    setup()
    fireEvent.change(await screen.findByLabelText('Góp ý cho agent'), { target: { value: 'giây 14 bình thành nồi' } })
    fireEvent.click(screen.getByText('🔍 Đánh giá phim (chỉ tốn lượt Claude)'))
    await waitFor(() => expect(start).toHaveBeenCalledWith('r1', 'giây 14 bình thành nồi'))
  })

  it('cannot review before the film is cut', async () => {
    vi.spyOn(api, 'filmReviews').mockResolvedValue({ job: null, reviews: [] })
    setup({ filmReady: false })
    const b = await screen.findByText('🔍 Đánh giá phim (chỉ tốn lượt Claude)')
    expect((b as HTMLButtonElement).disabled).toBe(true)
  })
})
