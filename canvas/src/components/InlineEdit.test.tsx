import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { InlineEdit } from './InlineEdit'

afterEach(() => vi.useRealTimers())

describe('InlineEdit', () => {
  it('saves once, 1 s after typing stops', async () => {
    vi.useFakeTimers()
    const onSave = vi.fn().mockResolvedValue({ updated_at: 't2' })
    render(<InlineEdit label="Prompt" value="a" updatedAt="t1" onSave={onSave} />)
    const box = screen.getByLabelText('Prompt')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: 'ab' } })
    fireEvent.change(box, { target: { value: 'abc' } })
    await act(async () => { await vi.advanceTimersByTimeAsync(999) })
    expect(onSave).not.toHaveBeenCalled()
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave).toHaveBeenCalledWith('abc')
  })

  it('shows a conflict banner when the value changes elsewhere while editing', () => {
    const { rerender } = render(<InlineEdit label="Prompt" value="a" updatedAt="t1" onSave={vi.fn()} />)
    const box = screen.getByLabelText('Prompt')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: 'mine' } })
    rerender(<InlineEdit label="Prompt" value="theirs" updatedAt="t2" onSave={vi.fn()} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Có thay đổi từ nơi khác')
    fireEvent.click(screen.getByText('Lấy bản mới'))
    expect(box).toHaveValue('theirs')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('keep-mine re-saves the local draft', async () => {
    const onSave = vi.fn().mockResolvedValue({ updated_at: 't3' })
    const { rerender } = render(<InlineEdit label="Prompt" value="a" updatedAt="t1" onSave={onSave} />)
    const box = screen.getByLabelText('Prompt')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: 'mine' } })
    rerender(<InlineEdit label="Prompt" value="theirs" updatedAt="t2" onSave={onSave} />)
    await act(async () => { fireEvent.click(screen.getByText('Giữ bản của tôi')) })
    expect(onSave).toHaveBeenLastCalledWith('mine')
  })

  it('does not flag its own saved value as a conflict', async () => {
    vi.useFakeTimers()
    const onSave = vi.fn().mockResolvedValue({ updated_at: 't2' })
    const { rerender } = render(<InlineEdit label="Prompt" value="a" updatedAt="t1" onSave={onSave} />)
    const box = screen.getByLabelText('Prompt')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: 'b' } })
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    rerender(<InlineEdit label="Prompt" value="b" updatedAt="t2" onSave={onSave} />)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('updates from props when not editing', () => {
    const { rerender } = render(<InlineEdit label="Prompt" value="a" updatedAt="t1" onSave={vi.fn()} />)
    rerender(<InlineEdit label="Prompt" value="z" updatedAt="t2" onSave={vi.fn()} />)
    expect(screen.getByLabelText('Prompt')).toHaveValue('z')
  })

  it('keeps the saved text after blur while the refetch is still in flight', async () => {
    const onSave = vi.fn().mockResolvedValue({ updated_at: '2026-10-14T09:00:05Z' })
    render(<InlineEdit label="Prompt" value="a" updatedAt="2026-10-14T09:00:00Z" onSave={onSave} />)
    const box = screen.getByLabelText('Prompt')
    fireEvent.focus(box)
    fireEvent.change(box, { target: { value: 'b' } })
    await act(async () => { fireEvent.blur(box) })
    expect(onSave).toHaveBeenCalledWith('b')
    expect(box).toHaveValue('b')
  })
})
