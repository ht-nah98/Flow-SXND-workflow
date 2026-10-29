import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { CanvasActionsContext, type CanvasActions } from '../canvas/actions-context'
import { character } from '../test/fixtures'
import { AssetLibrary } from './AssetLibrary'

function setup(actions: Partial<CanvasActions>) {
  vi.spyOn(api, 'listAllCharacters').mockResolvedValue([
    character(), character({ id: 'c2', name: 'Village Classroom', slug: 'village-classroom', entity_type: 'location' }),
  ])
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <CanvasActionsContext.Provider value={{ projectId: 'p1', ...actions } as CanvasActions}>
        <AssetLibrary attachedIds={new Set(['c1'])} dropPoint={() => ({ x: 1, y: 2 })} />
      </CanvasActionsContext.Provider>
    </QueryClientProvider>,
  )
}

describe('AssetLibrary', () => {
  it('filters by tab and search and marks attached assets', async () => {
    setup({})
    expect(await screen.findByText('Teacher Lan')).toBeInTheDocument()
    expect(screen.getByLabelText('Đã dùng trong project')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Bối cảnh' }))
    expect(screen.queryByText('Teacher Lan')).toBeNull()
    expect(screen.getByText('Village Classroom')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('Tìm asset…'), { target: { value: 'zzz' } })
    expect(screen.queryByText('Village Classroom')).toBeNull()
  })

  it('creates a new asset from the form', async () => {
    const createAsset = vi.fn().mockResolvedValue(undefined)
    setup({ createAsset })
    fireEvent.click(await screen.findByText('+ Asset mới'))
    fireEvent.change(screen.getByLabelText('Tên asset'), { target: { value: 'Mentor' } })
    fireEvent.change(screen.getByLabelText('Mô tả asset'), { target: { value: 'old man' } })
    fireEvent.click(screen.getByText('Tạo asset'))
    expect(createAsset).toHaveBeenCalledWith({ name: 'Mentor', entity_type: 'character', description: 'old man' }, { x: 1, y: 2 })
  })

  it('a dropped image file creates an asset named after the file', async () => {
    const createAsset = vi.fn().mockResolvedValue(undefined)
    setup({ createAsset })
    const file = new File(['x'], 'my product.png', { type: 'image/png' })
    fireEvent.drop(await screen.findByTestId('asset-library'), { dataTransfer: { files: [file], types: ['Files'] } })
    expect(createAsset).toHaveBeenCalledWith({ name: 'my product', entity_type: 'visual_asset', description: '' }, { x: 1, y: 2 }, file)
  })
})
