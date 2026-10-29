import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { FilmMode } from '../api/types'
import { AmbientOptions, DEFAULT_FILM_MODE, FILM_MODE_HELP, FILM_MODE_HINT, FILM_MODE_LABEL, FilmModeSelect } from './FilmModeSelect'

afterEach(() => vi.restoreAllMocks())

describe('FilmModeSelect', () => {
  it('explains every mode in Vietnamese: what it suits, how it is made, what it costs (directive G2)', () => {
    const modes = Object.keys(FILM_MODE_LABEL) as FilmMode[]
    expect(modes).toContain('ambient')
    for (const m of modes) {
      expect(FILM_MODE_HINT[m].length).toBeGreaterThan(20)
      const h = FILM_MODE_HELP[m]
      expect(h.suits.length).toBeGreaterThan(20)
      expect(h.how.length).toBeGreaterThan(40)
      expect(h.cost).toMatch(/credit/)
    }
  })

  it('marks continuous as the default and opens the explanation of the chosen mode', () => {
    expect(DEFAULT_FILM_MODE).toBe('continuous')           // directive B12, repeated 24/10
    render(<FilmModeSelect value="ambient" onChange={() => {}} />)
    expect(screen.getByRole('option', { name: /Liền mạch.*\(mặc định\)/ })).toBeTruthy()
    fireEvent.click(screen.getByText('ℹ️ Chế độ này làm gì?'))
    expect(screen.getByText(FILM_MODE_HELP.ambient.how)).toBeTruthy()
  })
})

describe('AmbientOptions', () => {
  it('lists the venues from the backend with their explanation and the reel length with its credit', async () => {
    vi.spyOn(api, 'listVenues').mockResolvedValue([
      { id: 'jazz-club', name: 'Quán jazz', explain: 'Đêm jazz trong quán nhỏ: bàn tròn, khói mờ.', place: '', look: '', details: '' }])
    const onChange = vi.fn()
    render(<QueryClientProvider client={new QueryClient()}><AmbientOptions value={{}} onChange={onChange} /></QueryClientProvider>)
    expect(await screen.findByText('Đêm jazz trong quán nhỏ: bàn tròn, khói mờ.')).toBeTruthy()
    expect(screen.getByRole('option', { name: /Vòng hình 1 phút \(≈ 8 clip, ≈ 120 credit\)/ })).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Độ dài vòng hình'), { target: { value: '60' } })
    expect(onChange).toHaveBeenCalledWith({ venue: 'jazz-club', reel_s: 60, loop_s: 1800 })
    fireEvent.change(screen.getByLabelText('Độ dài video cuối'), { target: { value: '3600' } })
    expect(onChange).toHaveBeenLastCalledWith({ venue: 'jazz-club', reel_s: 120, loop_s: 3600 })
  })
})
