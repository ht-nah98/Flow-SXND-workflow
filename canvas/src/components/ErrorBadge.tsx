import { explainError } from '../lib/errors'

export function ErrorBadge({ error }: { error: string | null }) {
  if (!error) return null
  const { message, hint } = explainError(error)
  return (
    <div role="alert" className="rounded border border-red-700 bg-red-950/70 p-2 text-[11px] text-red-100">
      <div className="font-medium">Lần tạo gần nhất bị lỗi</div>
      <div className="break-words opacity-80">{message}</div>
      {hint && <div className="mt-1">{hint}</div>}
    </div>
  )
}
