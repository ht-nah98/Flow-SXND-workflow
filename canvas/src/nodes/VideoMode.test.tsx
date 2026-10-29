import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { VideoModeToggle } from './ScriptNode'
import { videoModeOf } from '../graph/mapping'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactFlowProvider } from '@xyflow/react'
import { CanvasActionsContext, type CanvasActions } from '../canvas/actions-context'
import { scene, video } from '../test/fixtures'
import { SceneNode } from './SceneNode'
import type { SceneNodeData } from '../graph/mapping'

describe('video mode (directive D1: prompt + assets by default)', () => {
  it('a project without a choice is prompt + assets', () => {
    expect(videoModeOf({})).toBe('refs')
    expect(videoModeOf({ video_mode: 'image' })).toBe('image')
  })

  it('a hand-made project can opt into image → video', () => {
    const onChange = vi.fn()
    render(<VideoModeToggle mode="refs" directed={false} onChange={onChange} />)
    expect(screen.getByRole('button', { name: /Prompt \+ asset/ })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: /Ảnh → video/ }))
    expect(onChange).toHaveBeenCalledWith('image')
  })

  it('an AI-director film offers no image mode', () => {
    render(<VideoModeToggle mode="refs" directed onChange={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /Ảnh → video/ })).toBeNull()
    expect(screen.getByText(/không tạo ảnh trước/)).toBeInTheDocument()
  })

  it('a directed keyframe film says its clips come from the pinned stills', () => {
    // 23/10: every directed film read "prompt + asset", keyframe films too
    render(<VideoModeToggle mode="image" directed onChange={vi.fn()} />)
    expect(screen.getByText(/Video từ ảnh keyframe/)).toBeInTheDocument()
    expect(screen.queryByText(/prompt \+ asset/)).toBeNull()
  })
})

function renderScene(videoMode: 'refs' | 'image', assets: SceneNodeData['assets']) {
  const actions = { projectId: 'p1', canGenerate: true, run: vi.fn(), patchScene: vi.fn() } as unknown as CanvasActions
  const data: SceneNodeData = { kind: 'scene', scene: scene({ id: 's1' }), video: video(), orientation: 'HORIZONTAL',
    videoMode, stale: false, lastError: null, busy: false, assets, shot: null }
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ReactFlowProvider>
        <CanvasActionsContext.Provider value={actions}>
          <SceneNode id="scene:s1" data={data} type="scene" selected={false} dragging={false} zIndex={0} isConnectable
                     deletable selectable draggable positionAbsoluteX={0} positionAbsoluteY={0} />
        </CanvasActionsContext.Provider>
      </ReactFlowProvider>
    </QueryClientProvider>,
  )
}

const lan = [{ id: 'c1', name: 'Teacher Lan', color: '#a78bfa', url: null, type: 'character' }]

describe('SceneNode by video mode', () => {
  it('default mode shows the shot idea and video prompt, never an image prompt or image button', () => {
    renderScene('refs', lan)
    expect(screen.queryByText('Prompt ảnh')).toBeNull()
    expect(screen.getByText('Ý tưởng shot')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Gen ảnh|Gen lại ảnh/ })).toBeNull()
    expect(screen.getByText('🎬 prompt + asset')).toBeInTheDocument()
  })

  it('without any asset the video button waits for one', () => {
    renderScene('refs', [])
    expect(screen.getByText('⚠️ chưa gắn asset')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /video/ })).toBeDisabled()
  })

  it('image → video mode keeps the image prompt and image button', () => {
    renderScene('image', lan)
    expect(screen.getByText('Prompt ảnh')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Gen lại ảnh|Gen ảnh/ })).toBeInTheDocument()
  })
})
