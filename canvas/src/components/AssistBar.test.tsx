import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { CanvasActionsContext, type CanvasActions } from '../canvas/actions-context'
import { AssistBar } from './AssistBar'
import { ToastProvider } from './Toast'

function setup(targets = [{ kind: 'scene' as const, id: 's1', label: 'Cảnh 1' }]) {
  const actions = { patchScene: vi.fn().mockResolvedValue({}), patchCharacter: vi.fn() } as unknown as CanvasActions
  render(<ToastProvider><CanvasActionsContext.Provider value={actions}>
    <AssistBar projectId="p1" targets={targets} />
  </CanvasActionsContext.Provider></ToastProvider>)
  fireEvent.click(screen.getByText(/🤖 Hỏi AI/))
  return actions
}

describe('ask-AI bar (SciCloud sample)', () => {
  it('sends the selected nodes and applies a proposal only when asked', async () => {
    const ask = vi.spyOn(api, 'assist').mockResolvedValue({ answer: 'Đã tối ưu.', changes: [
      { kind: 'scene', id: 's1', field: 'video_prompt', value: 'References: Old Gus', why: 'rõ máy quay' }] })
    const actions = setup()
    expect(screen.getByText('@Cảnh 1')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Model'), { target: { value: 'opus' } })
    fireEvent.click(screen.getByText('✨ Tối ưu prompt video'))
    await waitFor(() => expect(screen.getByText('Đã tối ưu.')).toBeInTheDocument())
    expect(ask).toHaveBeenCalledWith(expect.objectContaining({ project_id: 'p1', model: 'opus', targets: [{ kind: 'scene', id: 's1' }] }))
    expect(actions.patchScene).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Áp dụng'))
    await waitFor(() => expect(actions.patchScene).toHaveBeenCalledWith('s1', { video_prompt: 'References: Old Gus' }))
    expect(screen.getByText('✓ Đã áp dụng')).toBeInTheDocument()
  })

  it('quick actions wait for a selection', () => {
    setup([])
    expect(screen.getByText('✨ Tối ưu prompt video')).toBeDisabled()
  })
})
