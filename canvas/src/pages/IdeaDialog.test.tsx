import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { DirectorRun } from '../api/types'
import { ToastProvider } from '../components/Toast'
import { IdeaDialog } from './IdeaDialog'

beforeEach(() => {
  vi.spyOn(api, 'listMaterials').mockResolvedValue([{ id: 'realistic', name: 'Photorealistic' }])
  URL.createObjectURL = vi.fn(() => `blob:${Math.random()}`)
  URL.revokeObjectURL = vi.fn()
})
afterEach(() => vi.restoreAllMocks())

function setup() {
  render(<QueryClientProvider client={new QueryClient()}><ToastProvider><MemoryRouter>
    <IdeaDialog open onOpenChange={() => {}} />
  </MemoryRouter></ToastProvider></QueryClientProvider>)
}

const file = (name: string, type = 'image/jpeg', size = 4) => new File([new Uint8Array(size)], name, { type })

it('sends the idea with its pictures and notes', async () => {
  const create = vi.spyOn(api, 'createRun').mockResolvedValue({ id: 'r1', project_id: 'p9' } as DirectorRun)
  setup()
  fireEvent.change(screen.getByPlaceholderText(/Hai bạn trẻ/), { target: { value: 'Quán cà phê của tôi' } })
  fireEvent.change(screen.getByLabelText('Chọn ảnh'), { target: { files: [file('cafe.jpg')] } })
  fireEvent.change(screen.getByLabelText('Ghi chú ảnh 1'), { target: { value: 'quán thật' } })
  fireEvent.click(screen.getByText('Lưu ý tưởng lên canvas'))
  await waitFor(() => expect(create).toHaveBeenCalled())
  const body = create.mock.calls[0][0]
  expect(body).toMatchObject({ text: 'Quán cà phê của tôi', target_s: 60, orientation: 'HORIZONTAL', style: 'realistic' })
  expect(body.images).toEqual([{ base64: 'AAAAAA==', filename: 'cafe.jpg', note: 'quán thật' }])
})

it('rejects unsupported or oversized pictures and caps the count', () => {
  setup()
  fireEvent.change(screen.getByLabelText('Chọn ảnh'), {
    target: { files: [file('a.gif', 'image/gif'), file('big.jpg', 'image/jpeg', 11 * 1024 * 1024),
                      ...Array.from({ length: 7 }, (_, i) => file(`${i}.png`, 'image/png'))] } })
  expect(screen.getAllByLabelText(/^Ghi chú ảnh/)).toHaveLength(6)
})

it('a template fills the skeleton, length, frame and voice', async () => {
  const create = vi.spyOn(api, 'createRun').mockResolvedValue({ id: 'r1', project_id: 'p9' } as DirectorRun)
  setup()
  fireEvent.click(screen.getByText(/Quảng cáo sản phẩm/))
  expect((screen.getByPlaceholderText(/Hai bạn trẻ/) as HTMLTextAreaElement).value).toMatch(/^Quảng cáo \[tên sản phẩm\]/)
  fireEvent.click(screen.getByText('Lưu ý tưởng lên canvas'))
  await waitFor(() => expect(create).toHaveBeenCalled())
  expect(create.mock.calls[0][0]).toMatchObject({ target_s: 30, orientation: 'VERTICAL', voice: 'voiceover' })
})
