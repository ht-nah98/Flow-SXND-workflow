import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactFlowProvider } from '@xyflow/react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CanvasActionsContext, type CanvasActions } from '../canvas/actions-context'
import type { ScriptNodeData } from '../graph/mapping'
import { project, scene, video } from '../test/fixtures'
import { sceneTitle, ScriptNode } from './ScriptNode'

const data: ScriptNodeData = {
  kind: 'script', project: { ...project, story: 'Hai bạn trẻ làm bánh, rồi chia xa.' },
  parts: [{ video: video(), items: [
    { scene: scene({ prompt: 'Cùng làm bánh', video_prompt: 'Oneshot cầm tay trong bếp', duration: 10 }), status: 'done', error: null },
    { scene: scene({ id: 's2', prompt: 'Khóc một mình', character_names: [] }), status: 'failed', error: 'MEDIA_REMOVED' },
  ] }],
  run: null, progress: null, missingRefs: [], missingAssets: [],
}

function setup() {
  const patchProject = vi.fn().mockResolvedValue(project)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ReactFlowProvider>
        <CanvasActionsContext.Provider value={{ projectId: 'p1', patchProject } as unknown as CanvasActions}>
          <ScriptNode id="script:p1" data={data} type="script" selected={false} dragging={false} zIndex={0}
                      isConnectable deletable={false} selectable draggable positionAbsoluteX={0} positionAbsoluteY={0} />
        </CanvasActionsContext.Provider>
      </ReactFlowProvider>
    </QueryClientProvider>,
  )
  return { patchProject }
}

describe('ScriptNode', () => {
  it('shows the synopsis and every clip with duration, refs and status', () => {
    setup()
    expect(screen.getByDisplayValue('Hai bạn trẻ làm bánh, rồi chia xa.')).toBeTruthy()
    expect(screen.getByText('Cùng làm bánh')).toBeTruthy()
    expect(screen.getByText('10s · Teacher Lan')).toBeTruthy()
    expect(screen.getByText('không có ảnh tham chiếu')).toBeTruthy()
    expect(screen.getByLabelText('Lỗi')).toBeTruthy()
  })

  it('opens the full script with each clip prompt and its last error', () => {
    setup()
    fireEvent.click(screen.getByText(/📖 Đọc toàn bộ kịch bản/))
    const dialog = screen.getByRole('dialog', { name: 'Kịch bản' })
    // Wide table by default (directive G1): one row per clip, prompt and error side by side.
    expect(dialog.querySelector('table')).not.toBeNull()
    expect(dialog.textContent).toContain('Oneshot cầm tay trong bếp')
    expect(dialog.textContent).toContain('MEDIA_REMOVED')
    fireEvent.click(screen.getByText('↕ Đọc dọc'))
    expect(dialog.querySelector('table')).toBeNull()
    expect(dialog.textContent).toContain('Lỗi gần nhất: MEDIA_REMOVED')
    fireEvent.click(screen.getByText('Đóng'))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('saves the synopsis to the project on blur', () => {
    const { patchProject } = setup()
    const box = screen.getByDisplayValue('Hai bạn trẻ làm bánh, rồi chia xa.')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: 'Mới' } })
    fireEvent.blur(box)
    expect(patchProject).toHaveBeenCalledWith({ story: 'Mới' })
  })
})

describe('sceneTitle', () => {
  it('drops the material style prefix', () => {
    expect(sceneTitle('Real RAW photograph, 35mm. Cùng làm bánh', 'Real RAW photograph, 35mm.')).toBe('Cùng làm bánh')
    expect(sceneTitle('Cùng làm bánh', 'Real RAW photograph, 35mm.')).toBe('Cùng làm bánh')
    expect(sceneTitle(null)).toBe('(chưa có tiêu đề)')
  })
})
