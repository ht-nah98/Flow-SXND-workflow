import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { FlowAccountsButton, MoveAccount, type FlowAccount } from './FlowAccounts'

const acc = (o: Partial<FlowAccount>): FlowAccount => ({ email: 'a@gmail.com', name: null, label: null, status: 'ACTIVE',
  priority: 0, exhausted_at: null, last_error: null, connected: 0, ...o })

describe('Flow accounts (rotation step 1)', () => {
  it('shows who is connected, the order, and old extensions that cannot say', async () => {
    vi.spyOn(api, 'flowAccounts').mockResolvedValue({ unidentified_connections: 1, unidentified_reasons: ['Timeout (5s) waiting for get_account'], accounts: [
      acc({ email: 'hot@gmail.com', connected: 1, priority: 0 }), acc({ email: 'olya@gmail.com', name: 'Olya', priority: 1, status: 'EXHAUSTED' })] })
    const patch = vi.spyOn(api, 'patchFlowAccount').mockResolvedValue({})
    render(<QueryClientProvider client={new QueryClient()}><FlowAccountsButton /></QueryClientProvider>)
    fireEvent.click(await screen.findByText('👤 hot'))
    expect(screen.getByText(/hot@gmail.com · 🟢 1 kết nối/)).toBeInTheDocument()
    expect(screen.getByLabelText('Trạng thái olya@gmail.com')).toHaveValue('EXHAUSTED')
    expect(screen.getByText(/extension cũ/)).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Lên olya@gmail.com'))
    await waitFor(() => expect(patch).toHaveBeenCalledWith('olya@gmail.com', { priority: 0 }))
    expect(patch).toHaveBeenCalledWith('hot@gmail.com', { priority: 1 })
  })
})

describe('Move a film to another account (rotation step 4)', () => {
  it('offers only the other connected accounts and moves the film there', async () => {
    vi.spyOn(api, 'flowAccounts').mockResolvedValue({ unidentified_connections: 0, accounts: [
      acc({ email: 'hoang@gmail.com', connected: 0 }), acc({ email: 'olya@gmail.com', name: 'Olya', connected: 1 }),
      acc({ email: 'off@gmail.com', connected: 0 })] })
    const move = vi.spyOn(api, 'moveFlowAccount').mockResolvedValue({ from: 'hoang@gmail.com', to: 'olya@gmail.com', flow_project_id: 'n', pictures: ['A', 'B', 'C'] })
    render(<QueryClientProvider client={new QueryClient()}><MoveAccount projectId="p1" current="hoang@gmail.com" /></QueryClientProvider>)
    fireEvent.click(screen.getByText('đổi tài khoản'))
    fireEvent.click(await screen.findByText(/→ Olya/))
    expect(screen.queryByText(/off@gmail.com/)).toBeNull()
    await waitFor(() => expect(move).toHaveBeenCalledWith('p1', 'olya@gmail.com'))
    expect(await screen.findByText(/Đã chuyển sang olya@gmail.com · tải lại 3 ảnh/)).toBeInTheDocument()
  })
})
