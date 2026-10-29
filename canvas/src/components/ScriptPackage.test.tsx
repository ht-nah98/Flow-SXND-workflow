import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { DirectorRun } from '../api/types'
import { ScriptPackageButton } from './ScriptPackage'
import { ToastProvider } from './Toast'

describe('script package (SciCloud sample)', () => {
  it('opens the three files and switches between them', async () => {
    vi.spyOn(api, 'scriptPackage').mockResolvedValue({ folder: '/phim/x/kich-ban', files: [
      { name: 'README.md', content: '# Ý đồ của đạo diễn' }, { name: 'kich-ban.md', content: '## Màn 1' },
      { name: 'phan-canh-prompt.md', content: '### Clip 1' }] })
    render(<ToastProvider><ScriptPackageButton run={{ id: 'r1' } as DirectorRun} /></ToastProvider>)
    fireEvent.click(screen.getByText('📦 Gói kịch bản (.md)'))
    await waitFor(() => expect(screen.getByText('# Ý đồ của đạo diễn')).toBeInTheDocument())
    expect(screen.getByText('/phim/x/kich-ban')).toBeInTheDocument()
    fireEvent.click(screen.getByText('🎬 Phân cảnh & prompt'))
    expect(screen.getByText('### Clip 1')).toBeInTheDocument()
  })
})
