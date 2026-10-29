import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'

/** Today's estimated Flow spend and the daily cap that holds Flow work once reached. */
export function CreditMeter() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['credits'], queryFn: () => api.credits(), refetchInterval: 15_000, retry: false })
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const c = q.data
  if (!c) return null
  const full = c.cap > 0 && c.today >= c.cap
  const save = async (cap: number) => {
    await api.setDailyCap(cap)
    await qc.invalidateQueries({ queryKey: ['credits'] })
    setOpen(false)
  }
  return (
    <div className="relative text-xs">
      {open && (
        <div role="dialog" aria-label="Trần credit theo ngày"
             className="absolute bottom-9 left-1/2 w-[300px] -translate-x-1/2 rounded-lg border border-zinc-700 bg-zinc-900 p-3 shadow-xl">
          <p className="mb-2 text-zinc-300">
            Hôm nay đã tiêu khoảng <b>{c.today}</b> credit (ước tính: video ~{c.prices.video}, ảnh ~{c.prices.image}).
            Chạm trần thì các lệnh Flow mới sẽ đứng chờ, không bị huỷ.
          </p>
          <label className="flex items-center gap-2">
            Trần mỗi ngày
            <input aria-label="Trần credit" inputMode="numeric" value={draft} placeholder={c.cap ? String(c.cap) : 'không giới hạn'}
                   onChange={(e) => setDraft(e.target.value.replace(/\D/g, ''))}
                   className="w-24 rounded bg-zinc-800 px-2 py-1" />
          </label>
          <div className="mt-2 flex gap-1">
            <button disabled={!draft} className="flex-1 rounded bg-sky-700 px-2 py-1 disabled:opacity-40"
                    onClick={() => void save(Number(draft))}>Lưu</button>
            {c.cap > 0 && <button className="rounded bg-zinc-700 px-2 py-1" onClick={() => void save(0)}>Bỏ trần</button>}
          </div>
        </div>
      )}
      <button onClick={() => { setDraft(''); setOpen((o) => !o) }} aria-expanded={open}
              className={`rounded-full border px-3 py-1 shadow ${full ? 'border-red-500 bg-red-950 text-red-200' : 'border-zinc-700 bg-zinc-900/90'}`}>
        💳 Hôm nay ~{c.today}{c.cap ? ` / ${c.cap}` : ''} credit{full ? ' · đã chạm trần' : ''}
      </button>
    </div>
  )
}
