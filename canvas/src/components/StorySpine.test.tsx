import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StorySpine } from './StorySpine'

describe('StorySpine', () => {
  it('shows the spine the writer decided, skipping empty parts', () => {
    render(<StorySpine story={{ synopsis: 's', cast: [], story_line: 'Bố tham vàng nên nuôi lớn ác quỷ',
                                message: 'Tình thân là của cải thật', viewer_value: '', rule_and_cost: 'Ăn sắt nhả vàng' }} />)
    expect(screen.getByText('🧵 Tuyến truyện')).toBeTruthy()
    expect(screen.getByText('Tình thân là của cải thật')).toBeTruthy()
    expect(screen.getByText('⚖️ Luật & cái giá')).toBeTruthy()
    expect(screen.queryByText('🎁 Giá trị cho người xem')).toBeNull()
  })

  it('renders nothing for an old script without a spine', () => {
    const { container } = render(<StorySpine story={{ synopsis: 's', cast: [] }} />)
    expect(container.innerHTML).toBe('')
  })

  it('shows how the user’s written story was adapted and what the user must decide', () => {
    render(<StorySpine story={{ synopsis: 's', cast: [], story_line: 'Daniel mất vợ nên khép mình',
      notes_for_user: ['Truyện dài ~4:45; 110s chỉ đủ lướt mỗi hồi'],
      source_map: [{ part: 'Cảnh 1 — cuộc gọi từ bệnh viện', beats: ['B2'], kept: 'full' },
                   { part: 'Người bạn cũ hỏi', beats: [], kept: 'dropped', note: 'gộp vào lời kết' }] }} />)
    expect(screen.getByText(/Truyện dài ~4:45/)).toBeTruthy()
    expect(screen.getByText(/1\/2 phần giữ lại/)).toBeTruthy()
    expect(screen.getByText(/gộp vào lời kết/)).toBeTruthy()
  })
})

describe('director intent and hooks (SciCloud sample)', () => {
  it('shows why the story is built this way and when it grabs the viewer', () => {
    render(<StorySpine story={{ synopsis: 's', cast: [], director_notes: ['Ba kiểu thích thay vì chọn một'],
      hooks: [{ at_s: 75, beat_id: 'B3', moment: '"Anh thua rồi."' }, { at_s: 8, beat_id: 'B1', moment: 'cú ném hỏng' }] }} />)
    expect(screen.getByText('Ba kiểu thích thay vì chọn một')).toBeInTheDocument()
    const items = screen.getAllByRole('listitem').map((li) => li.textContent)
    expect(items.indexOf('0:08 cú ném hỏng')).toBeLessThan(items.indexOf('1:15 "Anh thua rồi."'))
  })
})
