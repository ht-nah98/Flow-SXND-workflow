import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { DirectorRun } from '../api/types'
import { ChoiceDialogProvider } from '../components/ChoiceDialog'
import { ToastProvider } from '../components/Toast'
import { RunControls, ScriptSummary, ShotFailed } from './RunControls'

afterEach(() => vi.restoreAllMocks())

const run = (o: Partial<DirectorRun> = {}): DirectorRun => ({
  id: 'r1', project_id: 'p1', stage: 'STORY', status: 'RUNNING', gate: null, error: null,
  brief: { text: 'Hai bạn trẻ làm bánh kem', target_s: 30, orientation: 'HORIZONTAL',
           images: [{ file: '/out/ideas/1-cafe.jpg', note: 'quán của tôi' }] },
  budget: {}, spent: {},
  plan: { brief: { images: [{ file: '/out/ideas/1-cafe.jpg', use: 'location', name: 'Old Cafe', description: 'cafe' }] } },
  created_at: null, updated_at: null, ...o,
})

function setup(r: DirectorRun, progress: { label: string; done: number; total: number } | null = null) {
  render(
    <QueryClientProvider client={new QueryClient()}><ToastProvider><ChoiceDialogProvider>
      <ScriptSummary run={r} /><RunControls run={r} progress={progress} />
    </ChoiceDialogProvider></ToastProvider></QueryClientProvider>,
  )
}

const atScript = () => run({
  status: 'WAITING_GATE', gate: 'SCRIPT', stage: 'INGEST',
  plan: { story: { synopsis: 's', cast: [{ name: 'Bố', entity_type: 'character' }, { name: 'Phòng ngủ', entity_type: 'location' }] },
          shotlist: { shots: [{}, {}, {}] },
          gate_payload: { shots: 3, refs: 2, provided: 1, credits_est: 2, videos: 3, regens: 1, video_credits_est: 60,
                          total_credits_est: 62 } },
})

describe('RunControls', () => {
  it('cancels the whole run only after the confirmation', async () => {
    const cancel = vi.spyOn(api, 'cancelRun').mockResolvedValue(run({ status: 'CANCELLED' }))
    setup(atScript())
    fireEvent.click(screen.getByText('🛑 Huỷ toàn bộ run'))
    expect(cancel).not.toHaveBeenCalled()
    fireEvent.click(await screen.findByText('🛑 Huỷ toàn bộ'))
    await waitFor(() => expect(cancel).toHaveBeenCalledWith('r1'))
  })

  it('in keyframe mode "run all" says it stops to look at the stills', () => {
    // 23/10 Blue Morning: "Chạy toàn bộ" sent 21 videos before anyone had seen the keyframes
    const r = atScript()
    setup({ ...r, plan: { ...r.plan, brief: { film_mode: 'keyframe' } } })
    expect(screen.getByText(/keyframe \(dừng cho bạn duyệt\)/)).toBeTruthy()
  })

  it('a keyframe film counts its stills in the credit estimate', () => {
    const r = atScript()
    setup({ ...r, plan: { ...r.plan, brief: { film_mode: 'keyframe' },
                          gate_payload: { ...r.plan.gate_payload, keyframes: 3, keyframe_credits_est: 3, total_credits_est: 65 } } })
    expect(screen.getByText('ảnh ≈2 · 3 keyframe ≈3 · video ≈60 · tổng ≈65')).toBeTruthy()
  })

  it('a cancelled run shows no actions', () => {
    setup(run({ status: 'CANCELLED', stage: 'REFS' }))
    expect(screen.getByText(/Run đã huỷ/)).toBeTruthy()
    expect(screen.queryByText('🛑 Huỷ toàn bộ run')).toBeNull()
    expect(screen.queryByText('Chạy tiếp')).toBeNull()
  })

  it('summarises the script with credit estimates', () => {
    setup(atScript())
    expect(screen.getByText('~30s chọn → phim ước ~17s (3 clip × 10s, dựng theo nhịp truyện) · 16:9')).toBeTruthy()
    expect(screen.getByText('Bố')).toBeTruthy()
    expect(screen.getByText('Phòng ngủ')).toBeTruthy()
    expect(screen.getByText('ảnh ≈2 · video ≈60 · tổng ≈62')).toBeTruthy()
  })

  it('holds a film whose account ran out of credit and resumes it on request', async () => {
    vi.spyOn(api, 'flowAccounts').mockResolvedValue({ unidentified_connections: 0, accounts: [
      { email: 'a@gmail.com', name: null, label: null, status: 'EXHAUSTED', priority: 0, exhausted_at: 'x', last_error: 'q', connected: 1 },
      { email: 'b@gmail.com', name: null, label: 'Phụ', status: 'ACTIVE', priority: 1, exhausted_at: null, last_error: null, connected: 1 },
    ] })
    const approve = vi.spyOn(api, 'approveRun').mockResolvedValue(run())
    setup(run({ status: 'WAITING_GATE', gate: 'ACCOUNT_EXHAUSTED', stage: 'VIDEOS',
                plan: { gate_payload: { account: 'a@gmail.com', waiting: 4, stage: 'VIDEOS' } } }))
    expect(screen.getByText(/Tài khoản a@gmail.com hết credit\. 4 việc đang giữ lại/)).toBeTruthy()
    expect(await screen.findByText('Tài khoản còn credit đang kết nối: Phụ.')).toBeTruthy()
    fireEvent.click(screen.getByText('Tài khoản này đã có credit lại — chạy tiếp'))
    await waitFor(() => expect(approve).toHaveBeenCalledWith('r1', 'ACCOUNT_EXHAUSTED'))
  })

  it('a failed clip offers to merge after re-making it, or without it', async () => {
    const resolve = vi.spyOn(api, 'resolveShotFailure').mockResolvedValue(run())
    setup(run({ status: 'WAITING_GATE', gate: 'SHOT_FAILED', stage: 'CUT', plan: { gate_payload: { shots: ['SH04'], scenes: [4] } } }))
    expect(screen.getByText(/Cảnh 4 chưa có video/)).toBeTruthy()
    fireEvent.click(screen.getByText('🎬 Ghép phim — đã tạo lại cảnh 4 (miễn phí)'))
    await waitFor(() => expect(resolve).toHaveBeenCalledWith('r1', 'retry'))
    fireEvent.click(screen.getByText('🎬 Ghép phim, bỏ cảnh 4 (miễn phí)'))
    await waitFor(() => expect(resolve).toHaveBeenCalledWith('r1', 'drop'))
  })

  it('a failed clip re-made since says so and offers one merge button', async () => {
    const resolve = vi.spyOn(api, 'resolveShotFailure').mockResolvedValue(run())
    const r = run({ status: 'WAITING_GATE', gate: 'SHOT_FAILED', stage: 'CUT', plan: { gate_payload: { shots: ['SH04'], scenes: [4] } } })
    render(<QueryClientProvider client={new QueryClient()}><ToastProvider><ChoiceDialogProvider><ShotFailed run={r} done={[1, 2, 3, 4]} /></ChoiceDialogProvider></ToastProvider></QueryClientProvider>)
    expect(screen.getByText(/Cảnh 4 đã có video/)).toBeTruthy()
    expect(screen.queryByText(/bỏ cảnh 4/)).toBeNull()
    fireEvent.click(screen.getByText('🎬 Ghép phim (miễn phí)'))
    await waitFor(() => expect(resolve).toHaveBeenCalledWith('r1', 'retry'))
  })

  it('approves step by step', async () => {
    const approve = vi.spyOn(api, 'approveRun').mockResolvedValue(run())
    setup(atScript())
    fireEvent.click(screen.getByText(/Tạo từng bước — tạo 2 ảnh asset trước \(≈2 credit\)/))
    await waitFor(() => expect(approve).toHaveBeenCalledWith('r1', 'SCRIPT', { mode: 'step' }))
  })

  it('approves the whole film at once', async () => {
    const approve = vi.spyOn(api, 'approveRun').mockResolvedValue(run())
    setup(atScript())
    fireEvent.click(screen.getByText(/Chạy toàn bộ — ảnh → 3 video → dựng phim \(≈62 credit/))
    await waitFor(() => expect(approve).toHaveBeenCalledWith('r1', 'SCRIPT', { mode: 'auto' }))
  })

  it('sends a revision request from the script gate', async () => {
    const revise = vi.spyOn(api, 'reviseRun').mockResolvedValue(run())
    setup(atScript())
    fireEvent.click(screen.getByText('Yêu cầu sửa kịch bản'))
    fireEvent.change(screen.getByLabelText('Góp ý cho kịch bản'), { target: { value: 'thêm cảnh biển' } })
    fireEvent.click(screen.getByText('Gửi góp ý — viết lại'))
    await waitFor(() => expect(revise).toHaveBeenCalledWith('r1', 'thêm cảnh biển'))
  })

  it('blocks videos while an asset image is missing', () => {
    render(<QueryClientProvider client={new QueryClient()}><ToastProvider>
      <RunControls run={run({ status: 'WAITING_GATE', gate: 'ASSETS', plan: { gate_payload: { videos: 6, credits_est: 120 } } })}
                   progress={null} missingRefs={['Gia Hân', 'Minh Tuấn']} />
    </ToastProvider></QueryClientProvider>)
    expect(screen.getByText(/Còn thiếu ảnh: Gia Hân, Minh Tuấn/)).toBeTruthy()
    expect((screen.getByText(/Ảnh ổn — tạo 6 video/) as HTMLButtonElement).disabled).toBe(true)
  })

  it('makes the missing asset images from the script node', async () => {
    const make = vi.spyOn(api, 'makeMissingRefs').mockResolvedValue(run())
    render(<QueryClientProvider client={new QueryClient()}><ToastProvider>
      <RunControls run={run({ status: 'WAITING_GATE', gate: 'ASSETS', plan: { gate_payload: {} } })}
                   progress={null} missingRefs={['Gia Hân', 'Minh Tuấn']} />
    </ToastProvider></QueryClientProvider>)
    fireEvent.click(screen.getByText(/Tạo 2 ảnh còn thiếu/))
    await waitFor(() => expect(make).toHaveBeenCalledWith('r1'))
  })

  it('asks for video credit at the assets gate', async () => {
    const approve = vi.spyOn(api, 'approveRun').mockResolvedValue(run())
    setup(run({ status: 'WAITING_GATE', gate: 'ASSETS',
                plan: { gate_payload: { videos: 6, credits_est: 120, failed_refs: ['x'] } } }))
    fireEvent.click(screen.getByText('Ảnh ổn — tạo 6 video (≈120 credit)'))
    await waitFor(() => expect(approve).toHaveBeenCalledWith('r1', 'ASSETS'))
  })

  it('shows progress and can pause a running production', async () => {
    const pause = vi.spyOn(api, 'pauseRun').mockResolvedValue(run())
    setup(run({ stage: 'VIDEOS', plan: { mode: 'auto' } }), { label: 'Video', done: 3, total: 6 })
    expect(screen.getByText('Video 3/6')).toBeTruthy()
    expect(screen.getByText(/chạy toàn bộ/)).toBeTruthy()
    fireEvent.click(screen.getByText(/Tạm dừng/))
    await waitFor(() => expect(pause).toHaveBeenCalledWith('r1'))
  })

  it('shows the error and retries a failed step', async () => {
    const retry = vi.spyOn(api, 'retryRun').mockResolvedValue(run())
    setup(run({ status: 'FAILED', stage: 'CUT', error: 'ffmpeg' }))
    expect(screen.getByText(/Lỗi ở bước CUT: ffmpeg/)).toBeTruthy()
    fireEvent.click(screen.getByText('Chạy lại bước'))
    await waitFor(() => expect(retry).toHaveBeenCalledWith('r1'))
  })
})
