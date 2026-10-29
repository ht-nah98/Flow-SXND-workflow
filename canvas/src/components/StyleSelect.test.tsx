import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { StyleSelect } from './StyleSelect'

describe('style packs', () => {
  it('lists the packs, defaults to the director, and shows the chosen core rules', async () => {
    vi.spyOn(api, 'listStyles').mockResolvedValue([
      { id: 'warm-indie', name: 'Ấm áp · MV indie', suits: 'tình cảm', core: ['warm golden window light', 'handheld'] }])
    const onChange = vi.fn()
    const { rerender } = render(<QueryClientProvider client={new QueryClient()}><StyleSelect value="" onChange={onChange} /></QueryClientProvider>)
    await screen.findByText(/Ấm áp · MV indie/)
    expect(screen.getByLabelText('Gói phong cách')).toHaveValue('')
    fireEvent.change(screen.getByLabelText('Gói phong cách'), { target: { value: 'warm-indie' } })
    expect(onChange).toHaveBeenCalledWith('warm-indie')
    rerender(<QueryClientProvider client={new QueryClient()}><StyleSelect value="warm-indie" onChange={onChange} /></QueryClientProvider>)
    expect(await screen.findByText('warm golden window light · handheld')).toBeInTheDocument()
  })
})
