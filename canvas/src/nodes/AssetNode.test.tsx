import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactFlowProvider } from '@xyflow/react'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CanvasActionsContext, type CanvasActions } from '../canvas/actions-context'
import { character } from '../test/fixtures'
import { AssetNode } from './AssetNode'

function setup(patchCharacter = vi.fn().mockResolvedValue(character())) {
  const actions = { projectId: 'p1', canGenerate: true, patchCharacter } as unknown as CanvasActions
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ReactFlowProvider>
        <CanvasActionsContext.Provider value={actions}>
          <AssetNode id="character:c1" data={{ kind: 'asset', character: character(), busy: false, color: '#a78bfa', uses: 2 }}
                     type="asset" selected={false} dragging={false} zIndex={0} isConnectable
                     deletable selectable draggable
                     positionAbsoluteX={0} positionAbsoluteY={0} />
        </CanvasActionsContext.Provider>
      </ReactFlowProvider>
    </QueryClientProvider>,
  )
  return { patchCharacter }
}

afterEach(() => vi.useRealTimers())

describe('AssetNode name field', () => {
  it('does not autosave while typing, even past the usual debounce window', async () => {
    vi.useFakeTimers()
    const { patchCharacter } = setup()
    const input = screen.getByLabelText('Tên')
    fireEvent.change(input, { target: { value: 'T' } })
    fireEvent.change(input, { target: { value: 'Te' } })
    fireEvent.change(input, { target: { value: 'Teacher Lan 2' } })
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(patchCharacter).not.toHaveBeenCalled()
    fireEvent.blur(input)
    expect(patchCharacter).toHaveBeenCalledTimes(1)
    expect(patchCharacter).toHaveBeenCalledWith('c1', { name: 'Teacher Lan 2' })
  })

  it('saves on Enter without waiting for blur', () => {
    const { patchCharacter } = setup()
    const input = screen.getByLabelText('Tên')
    fireEvent.change(input, { target: { value: 'Co Lan' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(patchCharacter).toHaveBeenCalledWith('c1', { name: 'Co Lan' })
  })

  it('does not save an unchanged value on blur', () => {
    const { patchCharacter } = setup()
    const input = screen.getByLabelText('Tên')
    fireEvent.focus(input)
    fireEvent.blur(input)
    expect(patchCharacter).not.toHaveBeenCalled()
  })
})
