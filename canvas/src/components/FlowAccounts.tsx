import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'

export type FlowAccount = {
  email: string; name: string | null; label: string | null; status: 'ACTIVE' | 'EXHAUSTED' | 'DISABLED'
  priority: number; exhausted_at: string | null; last_error: string | null; connected: number
}
const STATUS = { ACTIVE: '✅ Dùng được', EXHAUSTED: '⛔ Hết credit', DISABLED: '⏸ Tạm tắt' } as const

/** Account rotation, step 1 (19/10): which Google accounts run Flow, which are connected now, in what order. */
export function FlowAccountsButton() {
  const [open, setOpen] = useState(false)
  const q = useQuery({ queryKey: ['flow-accounts'], queryFn: api.flowAccounts, refetchInterval: open ? 10000 : 60000 })
  const live = (q.data?.accounts ?? []).filter((a) => a.connected > 0)
  return (
    <div className="relative">
      <button onClick={() => setOpen((o) => !o)} className="rounded-lg bg-zinc-800 px-3 py-1.5 text-sm">
        👤 {live.length ? live.map((a) => a.label || a.email.split('@')[0]).join(', ') : 'Tài khoản Flow'}
      </button>
      {open && <AccountsPanel data={q.data} onClose={() => setOpen(false)} />}
    </div>
  )
}

type AccountsData = { accounts: FlowAccount[]; unidentified_connections: number; unidentified_reasons?: string[] }
const REASON: Record<string, string> = {
  NO_FLOW_TAB: 'profile này chưa mở tab flow.google.com — mở Flow ở profile đó',
}

function AccountsPanel({ data, onClose }: { data?: AccountsData; onClose: () => void }) {
  const qc = useQueryClient()
  const save = async (email: string, patch: Partial<FlowAccount>) => {
    await api.patchFlowAccount(email, patch)
    await qc.invalidateQueries({ queryKey: ['flow-accounts'] })
  }
  const rows = data?.accounts ?? []
  const swap = (a: FlowAccount, b: FlowAccount) =>   // positions in the list, so equal priorities still move
    Promise.all([save(a.email, { priority: rows.indexOf(b) }), save(b.email, { priority: rows.indexOf(a) })])
  return (
    <div role="dialog" aria-label="Tài khoản Flow"
         className="absolute right-0 z-40 mt-2 flex w-[460px] max-w-[92vw] flex-col gap-2 rounded-xl bg-zinc-900 p-3 text-xs shadow-2xl ring-1 ring-zinc-700">
      <div className="flex items-center justify-between">
        <span className="font-semibold">👤 Tài khoản Google chạy Flow</span>
        <button onClick={onClose} className="rounded bg-zinc-800 px-2 py-0.5">Đóng</button>
      </div>
      <p className="text-zinc-400">Mỗi Chrome profile có extension FlowKit là một tài khoản. Thứ tự dưới đây là thứ tự dùng khi một tài khoản hết credit.</p>
      {!data && <p className="text-zinc-400">⏳ Đang hỏi các extension…</p>}
      {data && rows.length === 0 && <p className="text-zinc-400">Chưa nhận diện tài khoản nào.</p>}
      {rows.map((a, i) => (
        <div key={a.email} className="flex items-center gap-2 rounded bg-zinc-800/70 p-2">
          <span className="w-4 text-zinc-500">{i + 1}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate font-semibold">{a.label || a.name || a.email}</span>
            <span className="block truncate text-zinc-400">{a.email}{a.connected ? ` · 🟢 ${a.connected} kết nối` : ' · ⚪ không kết nối'}</span>
            {a.last_error && <span className="block truncate text-red-300" title={a.last_error}>{a.last_error}</span>}
          </span>
          <select aria-label={`Trạng thái ${a.email}`} value={a.status} className="rounded bg-zinc-900 px-1 py-0.5"
                  onChange={(e) => void save(a.email, { status: e.target.value as FlowAccount['status'] })}>
            {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <span className="flex flex-col">
            <button aria-label={`Lên ${a.email}`} disabled={i === 0} className="px-1 disabled:opacity-30"
                    onClick={() => void swap(a, rows[i - 1])}>▲</button>
            <button aria-label={`Xuống ${a.email}`} disabled={i === rows.length - 1} className="px-1 disabled:opacity-30"
                    onClick={() => void swap(a, rows[i + 1])}>▼</button>
          </span>
        </div>
      ))}
      {(data?.unidentified_connections ?? 0) > 0 && (
        <div className="rounded bg-amber-950 p-2 text-amber-200">
          ⚠️ {data!.unidentified_connections} kết nối chưa cho biết tài khoản:
          <ul className="list-disc pl-4">
            {(data!.unidentified_reasons ?? []).map((r, i) => (
              <li key={i}>{REASON[r] ?? (/timeout|unknown/i.test(r)
                ? 'extension cũ — mở chrome://extensions ở profile đó, bấm ↻ tải lại FlowKit (0.6.0), rồi F5 tab Flow' : r)}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/** Account rotation, step 4 (22/10: Google flagged Hoang mid-film): move this film to another connected account.
 *  No credit — the asset pictures already made are uploaded there again; queued work goes on in that account. */
export function MoveAccount({ projectId, current }: { projectId: string; current?: string | null }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const q = useQuery({ queryKey: ['flow-accounts'], queryFn: api.flowAccounts, enabled: open })
  const others = (q.data?.accounts ?? []).filter((a) => a.email !== current && a.connected > 0 && a.status === 'ACTIVE')
  const move = async (to: string) => {
    setBusy(true); setMsg(null)
    try {
      const r = await api.moveFlowAccount(projectId, to)
      setMsg(`✓ Đã chuyển sang ${r.to} · tải lại ${r.pictures.length} ảnh asset, không tốn credit`)
      setOpen(false)
      await qc.invalidateQueries({ queryKey: ['p', projectId] })
      await qc.invalidateQueries({ queryKey: ['flow-accounts'] })
    } catch (e) {
      setMsg(`✗ ${(e as Error).message}`)
    } finally { setBusy(false) }
  }
  return (
    <span className="nodrag relative inline-flex flex-col">
      <button className="text-[10px] text-sky-400 hover:underline" onClick={() => setOpen((o) => !o)}>đổi tài khoản</button>
      {open && (
        <div role="dialog" aria-label="Chuyển phim sang tài khoản khác"
             className="absolute left-0 top-4 z-40 flex w-[300px] flex-col gap-1 rounded-lg bg-zinc-950 p-2 text-[11px] font-normal text-zinc-200 shadow-xl ring-1 ring-zinc-700">
          <span className="text-zinc-400">Chuyển phim sang tài khoản đang kết nối. Ảnh asset đã có được tải lên lại (miễn phí); việc đang chờ chạy tiếp ở tài khoản mới.</span>
          {!q.data && <span className="text-zinc-500">⏳ Đang hỏi các extension…</span>}
          {q.data && !others.length && <span className="text-amber-300">Chưa có tài khoản nào khác đang kết nối — mở Chrome profile của tài khoản đó (tab Flow + FlowKit).</span>}
          {others.map((a) => (
            <button key={a.email} disabled={busy} className="rounded bg-emerald-800 px-2 py-1 text-left hover:bg-emerald-700 disabled:opacity-50"
                    onClick={() => void move(a.email)}>{busy ? '⏳ Đang chuyển…' : `→ ${a.label || a.name || a.email}`} <span className="text-zinc-300">{a.email}</span></button>
          ))}
        </div>
      )}
      {msg && <span className={`text-[10px] font-normal ${msg.startsWith('✓') ? 'text-emerald-300' : 'text-red-300'}`}>{msg}</span>}
    </span>
  )
}
