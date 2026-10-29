import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CanvasActionsContext, type CanvasActions } from '../canvas/actions-context'
import { scene } from '../test/fixtures'
import { ReviewPanel } from './ReviewPanel'

describe('ReviewPanel', () => {
  it('runs a review and appends the fix guide to the video prompt', async () => {
    const review = vi.fn().mockResolvedValue({ scene_id: 's1', overall_score: 6.5, verdict: 'NEEDS_FIX',
      errors: [{}, {}], fix_guide: 'Keep the glasses on.', has_critical_errors: false })
    const patchScene = vi.fn().mockResolvedValue(scene())
    render(<CanvasActionsContext.Provider value={{ review, patchScene } as unknown as CanvasActions}>
      <ReviewPanel scene={scene({ video_prompt: 'vp' })} hasVideo />
    </CanvasActionsContext.Provider>)
    fireEvent.click(screen.getByText('Claude đánh giá'))
    expect(await screen.findByText(/6.5/)).toBeInTheDocument()
    expect(screen.getByText(/2 lỗi/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('Chèn gợi ý vào prompt video'))
    expect(patchScene).toHaveBeenCalledWith('s1', { video_prompt: 'vp\n\nFix: Keep the glasses on.' })
  })

  it('lists every error worst first and lets Claude rewrite a director scene from them', async () => {
    const r = { scene_id: 's1', overall_score: 6.8, verdict: 'acceptable', fix_guide: 'Regenerate video',
      has_critical_errors: false, errors: [
        { severity: 'MINOR', time_range: '1s-2s', description: 'grain flickers' },
        { severity: 'HIGH', time_range: '6s-8s', description: 'lamp light turns blue' },
        { severity: 'CRITICAL', time_range: '3s-5s', description: 'hand merges with the photo' }] }
    const onRewrite = vi.fn()
    render(<CanvasActionsContext.Provider value={{ review: vi.fn().mockResolvedValue(r) } as unknown as CanvasActions}>
      <ReviewPanel scene={scene()} hasVideo onRewrite={onRewrite} />
    </CanvasActionsContext.Provider>)
    fireEvent.click(screen.getByText('Claude đánh giá'))
    const items = await screen.findAllByRole('listitem')
    expect(items.map((li) => li.textContent)).toEqual([
      '3s-5s · Nặng — hand merges with the photo', '6s-8s · Rõ — lamp light turns blue', '1s-2s · Nhẹ — grain flickers'])
    expect(screen.queryByText('Chèn gợi ý vào prompt video')).toBeNull()
    fireEvent.click(screen.getByText(/Claude viết lại prompt theo đánh giá/))
    expect(onRewrite).toHaveBeenCalledWith(r)
  })

  it('is disabled without a video', () => {
    render(<CanvasActionsContext.Provider value={{} as CanvasActions}>
      <ReviewPanel scene={scene()} hasVideo={false} />
    </CanvasActionsContext.Provider>)
    expect(screen.getByText('Claude đánh giá')).toBeDisabled()
  })
})
