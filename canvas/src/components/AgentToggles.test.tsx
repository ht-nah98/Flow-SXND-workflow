import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AgentToggles, DEFAULT_AGENTS, estimateCalls } from './AgentToggles'

describe('optional agents (directive A5)', () => {
  it('counts AI calls: QC watches every clip', () => {
    expect(estimateCalls(DEFAULT_AGENTS, 60)).toBe(3 + 1 + 1 + 11 + 1)
    expect(estimateCalls({ producer: false, editor: false, qc: false, coach: false }, 60)).toBe(3)
  })

  it('switching a role off sends the whole set and explains what changes', () => {
    const onChange = vi.fn()
    const { rerender } = render(<AgentToggles value={DEFAULT_AGENTS} onChange={onChange} targetS={60} />)
    expect(screen.getByText(/4\/4 bật/)).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText(/Editor/))
    expect(onChange).toHaveBeenCalledWith({ ...DEFAULT_AGENTS, editor: false })
    rerender(<AgentToggles value={{ ...DEFAULT_AGENTS, editor: false }} onChange={onChange} targetS={60} />)
    expect(screen.getByText(/3\/4 bật/)).toBeInTheDocument()
    expect(screen.getByText(/không qua duyệt/)).toBeInTheDocument()
  })
})
