import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { RunLog } from '../api/types'
import { activityRows, errorRows, progressRows, RunLogPanel } from './RunLogPanel'

const log: RunLog = {
  run_id: 'r1', status: 'RUNNING', stage: 'VIDEOS', stage_label: 'Tạo video', gate: null,
  steps: [
    { id: 's1', stage: 'STORY', label: 'Viết câu chuyện', attempt: 1, status: 'LINT_FAILED', duration_ms: 164000,
      created_at: '2026-10-21T09:34:00.000Z',
      issues: [{ rule: 'prop_single', label: 'Ảnh đạo cụ chứa nhiều vật', shot_id: null, scene: null, message: "prop 'B&W Photograph' shows several objects", severity: 'error' }] },
    { id: 's2', stage: 'STORY', label: 'Viết câu chuyện', attempt: 2, status: 'OK', duration_ms: 159000, created_at: '2026-10-21T09:37:00.000Z', issues: [] },
    { id: 's3', stage: 'SHOTLIST', label: 'Chia cảnh', attempt: 1, status: 'LINT_FAILED', duration_ms: 312000,
      created_at: '2026-10-21T09:42:00.000Z',
      issues: [{ rule: 'entrance', label: 'Nhân vật xuất hiện từ hư không', shot_id: 'SH03', scene: 3, message: 'Eddie Brooks is not in SH02', severity: 'error' }] },
  ],
  events: [
    { id: 'e1', kind: 'ai', level: 'info', title: 'Biên kịch · opus', data: { role: 'writer', ms: 164000, cost_usd: 0.78 }, created_at: '2026-10-21T09:34:00.100Z' },
    { id: 'e2', kind: 'gate', level: 'warn', title: 'Dừng chờ anh: duyệt kịch bản', data: { gate: 'SCRIPT' }, created_at: '2026-10-21T09:50:00.000Z' },
    { id: 'e3', kind: 'chain', level: 'ok', title: 'Nối chuỗi: khung cuối cảnh 1 → ảnh #1 của cảnh 2', data: { scene: 2 }, created_at: '2026-10-21T10:05:00.000Z' },
  ],
  requests: [
    { id: 'q1', type: 'GENERATE_VIDEO_REFS', label: 'Tạo video', status: 'FAILED', scene: 2, entity: null, error: 'NO_MEDIA_CREATED', retries: 1,
      created_at: '2026-10-21T10:06:00Z', updated_at: '2026-10-21T10:13:00Z' },
    { id: 'q2', type: 'GENERATE_CHARACTER_IMAGE', label: 'Tạo ảnh asset', status: 'COMPLETED', scene: null, entity: 'Old Walt', error: null, retries: 0,
      created_at: '2026-10-21T09:55:00Z', updated_at: '2026-10-21T09:56:00Z' },
  ],
}

afterEach(() => vi.restoreAllMocks())

describe('run log rows', () => {
  it('progress shows each attempt with its reasons and the gates, in time order', () => {
    const rows = progressRows(log)
    expect(rows.map((r) => r.title)).toEqual(['Viết câu chuyện', 'Viết câu chuyện (lần 2)', 'Chia cảnh', 'Dừng chờ anh: duyệt kịch bản'])
    expect(rows[2].issues?.[0].label).toBe('Nhân vật xuất hiện từ hư không')
  })

  it('activity mixes AI calls, Flow requests and chain links with what each was for', () => {
    const titles = activityRows(log).map((r) => r.title)
    expect(titles).toEqual(['Biên kịch · opus', 'Tạo ảnh asset · Old Walt', 'Nối chuỗi: khung cuối cảnh 1 → ảnh #1 của cảnh 2', 'Tạo video · Cảnh 2'])
  })

  it('errors gather only what went red or needs the user', () => {
    expect(errorRows(log).map((r) => r.title)).toEqual(['Viết câu chuyện', 'Chia cảnh', 'Dừng chờ anh: duyệt kịch bản', 'Tạo video · Cảnh 2'])
  })
})

describe('RunLogPanel', () => {
  it('opens a red step to show the reason in Vietnamese and jumps to its scene', async () => {
    vi.spyOn(api, 'runLog').mockResolvedValue(log)
    const onScene = vi.fn()
    render(<QueryClientProvider client={new QueryClient()}>
      <RunLogPanel projectId="p1" runIds={['r1']} onScene={onScene} onClose={() => {}} />
    </QueryClientProvider>)
    expect(await screen.findByText('Chia cảnh')).toBeTruthy()
    expect(screen.getByText(/Đang: Tạo video/)).toBeTruthy()
    fireEvent.click(screen.getByText('Chia cảnh'))
    expect(screen.getByText('⚠ Nhân vật xuất hiện từ hư không')).toBeTruthy()
    fireEvent.click(screen.getByText('Cảnh 3 →'))
    expect(onScene).toHaveBeenCalledWith(3)
    fireEvent.click(screen.getByRole('tab', { name: 'Lỗi 4' }))
    expect(screen.getByText('Tạo video · Cảnh 2')).toBeTruthy()
  })
})
