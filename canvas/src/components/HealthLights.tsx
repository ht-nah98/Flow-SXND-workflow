import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { CreditMeter } from './CreditMeter'

/** Always-visible system light: green when every part works; click for each part and how to fix it. */
export function HealthLights() {
  const [open, setOpen] = useState(false)
  const q = useQuery({ queryKey: ['system-check'], queryFn: api.systemCheck, refetchInterval: 10_000, retry: false })
  const items = q.data?.items ?? []
  const bad = q.error ? -1 : items.filter((i) => !i.ok).length
  const label = q.isLoading ? 'Đang kiểm tra…' : bad === -1 ? 'Backend không phản hồi' : bad ? `${bad} mục cần xử lý` : 'Hệ thống ổn'
  const dot = q.isLoading ? 'bg-zinc-500' : bad ? 'bg-red-500' : 'bg-emerald-500'
  return (
    <div className="fixed bottom-3 left-1/2 z-40 -translate-x-1/2 text-xs">
      {open && (
        <div role="dialog" aria-label="Tình trạng hệ thống"
             className="mb-2 w-[360px] rounded-lg border border-zinc-700 bg-zinc-900 p-3 shadow-xl">
          {bad === -1 && <p className="text-red-200">Backend chưa chạy. Chạy <code>./start.sh</code> trong thư mục flow-canvas.</p>}
          <ul className="flex flex-col gap-1.5">
            {items.map((i) => (
              <li key={i.key}>
                <div className="flex items-center gap-2">
                  <span>{i.ok ? '✅' : '❌'}</span>
                  <span className="whitespace-nowrap font-semibold">{i.label}</span>
                  <span className="ml-auto truncate text-zinc-400" title={i.detail}>{i.detail}</span>
                </div>
                {!i.ok && i.fix && <p className="ml-6 text-amber-200">{i.fix}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex items-center justify-center gap-2">
        <button onClick={() => setOpen((o) => !o)} aria-expanded={open}
                className="flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-900/90 px-3 py-1 shadow">
          <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
          {label}
        </button>
        <CreditMeter />
      </div>
    </div>
  )
}
