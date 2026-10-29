import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { DirectorRun } from '../api/types'
import { CanvasActionsContext, type CanvasActions } from '../canvas/actions-context'
import type { AssetNodeData, FinalNodeData, SceneNodeData } from '../graph/mapping'
import { character, scene, video } from '../test/fixtures'
import { Storyboard } from './Storyboard'

const hero = character({ id: 'c1', name: 'Thu Hà', entity_type: 'character' })
const garden = character({ id: 'c2', name: 'Rooftop Garden', entity_type: 'location' })
const chip = (c: typeof hero, color: string) => ({ id: c.id, name: c.name, color, url: null, type: c.entity_type })
const sceneData = (order: number, assets: ReturnType<typeof chip>[]): SceneNodeData => ({
  kind: 'scene', videoMode: 'refs', scene: scene({ id: `s${order}`, display_order: order, prompt: `Clip ${order + 1}` }), video: video(),
  orientation: 'HORIZONTAL', stale: false, lastError: null, busy: false, assets, shot: null,
})
const asset = (c: typeof hero, color: string, uses: number): AssetNodeData => ({ kind: 'asset', character: c, busy: false, color, uses })
const run = { plan: { brief: { film_mode: 'continuous' }, trims: [[0, 10], [1, 8]], ids: { scenes: { a: 's0', b: 's1' } },
                      shotlist: { shots: [{ id: 'a', order: 1 }, { id: 'b', order: 2, continues: true }] } } } as unknown as DirectorRun
const film: FinalNodeData = { kind: 'final', video: video({ title: 'Old Walt', duration: 17 }), url: 'file:///f.mp4', run, doneScenes: [1, 2] }

function setup(films: FinalNodeData[] = [film]) {
  const onOpen = vi.fn()
  const actions = { refreshUrls: vi.fn(), canGenerate: true, run: vi.fn(), patchScene: vi.fn(), review: vi.fn() } as unknown as CanvasActions
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CanvasActionsContext.Provider value={actions}>
        <Storyboard
          scenes={[{ id: 'scene:s0', data: sceneData(0, [chip(hero, '#a78bfa'), chip(garden, '#34d399')]) },
                   { id: 'scene:s1', data: sceneData(1, [chip(garden, '#34d399')]) }]}
          assets={[{ id: 'character:c1', data: asset(hero, '#a78bfa', 1) }, { id: 'character:c2', data: asset(garden, '#34d399', 2) }]}
          films={films} onOpen={onOpen} />
      </CanvasActionsContext.Provider>
    </QueryClientProvider>,
  )
  return onOpen
}

describe('Storyboard', () => {
  it('puts the film on top and the shots in a grid; the asset matrix is its own tab', () => {
    setup()
    expect(screen.getByLabelText('Phim hoàn chỉnh')).toBeInTheDocument()
    expect(screen.getByLabelText('Shot 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Shot 2')).toBeInTheDocument()
    expect(screen.queryByLabelText('Thu Hà có trong cảnh 1')).toBeNull()
    fireEvent.click(screen.getByRole('tab', { name: '🧩 Asset × cảnh' }))
    expect(screen.getByLabelText('Thu Hà có trong cảnh 1')).toBeInTheDocument()
    expect(screen.queryByLabelText('Thu Hà có trong cảnh 2')).toBeNull()
    expect(screen.getByLabelText('Rooftop Garden có trong cảnh 2')).toBeInTheDocument()
  })

  it('lights the shot that is playing and shows how it is entered on the timeline', () => {
    setup()
    const v = screen.getByLabelText('Phim hoàn chỉnh') as HTMLVideoElement
    Object.defineProperty(v, 'currentTime', { value: 12, configurable: true })
    fireEvent.timeUpdate(v)
    expect(screen.getByLabelText('Shot 2').className).toMatch(/ring-amber-400/)
    expect(screen.getByLabelText('Shot 1').className).not.toMatch(/ring-amber-400/)
    expect(screen.getByTitle('Liền mạch (khung cuối clip trước)')).toBeInTheDocument()
  })

  it('a shot opens a detail panel with the scene tools and a way back to the canvas', () => {
    const onOpen = setup()
    fireEvent.click(screen.getByLabelText('Shot 2'))
    const panel = screen.getByLabelText('Chi tiết shot')
    expect(panel).toHaveTextContent('Shot 2')
    expect(panel).toHaveTextContent('Prompt video')
    fireEvent.click(screen.getByText('Mở trên canvas'))
    expect(onOpen).toHaveBeenCalledWith('scene:s1')
    fireEvent.click(screen.getByLabelText('Đóng chi tiết'))
    expect(screen.queryByLabelText('Chi tiết shot')).toBeNull()
  })

  it('without a cut film it says how to make one', () => {
    setup([])
    expect(screen.getByText(/Phim chưa ghép/)).toBeInTheDocument()
  })
})
