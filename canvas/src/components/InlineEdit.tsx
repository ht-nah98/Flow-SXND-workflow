import { useEffect, useRef, useState } from 'react'

interface Props {
  value: string | null
  updatedAt: string | null
  onSave: (text: string) => Promise<{ updated_at?: string | null } | void>
  label?: string
  placeholder?: string
  single?: boolean
}

export function InlineEdit({ value, updatedAt, onSave, label, placeholder, single }: Props) {
  const incoming = value ?? ''
  const [draft, setDraft] = useState(incoming)
  const [editing, setEditing] = useState(false)
  const [conflict, setConflict] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const base = useRef({ value: incoming, updatedAt })
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const draftRef = useRef(draft)
  draftRef.current = draft
  const conflictRef = useRef(conflict)
  conflictRef.current = conflict

  useEffect(() => {
    if (!editing) {
      // Props older than our own last save are a refetch still in flight; don't revert to them.
      if (updatedAt && base.current.updatedAt && updatedAt < base.current.updatedAt) return
      setDraft(incoming)
      base.current = { value: incoming, updatedAt }
      return
    }
    if (updatedAt !== base.current.updatedAt && incoming !== base.current.value && incoming !== draftRef.current) {
      setConflict(incoming)
    }
  }, [incoming, updatedAt, editing])

  const save = async (text: string) => {
    if (timer.current) { clearTimeout(timer.current); timer.current = null }
    if (text === base.current.value) return
    setSaving(true)
    try {
      const res = await onSave(text)
      base.current = { value: text, updatedAt: (res && res.updated_at) ?? base.current.updatedAt }
    } catch {
      /* the caller already showed the error; keep the draft */
    } finally {
      setSaving(false)
    }
  }

  const onChange = (text: string) => {
    setDraft(text)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => { if (conflictRef.current === null) void save(text) }, 1000)
  }

  const onBlur = async () => {
    if (conflictRef.current !== null) return
    await save(draftRef.current)
    setEditing(false)
  }

  const keepMine = async () => {
    base.current = { value: conflict ?? '', updatedAt }
    setConflict(null)
    await save(draftRef.current)
  }

  const takeTheirs = () => {
    const t = conflict ?? ''
    setConflict(null)
    setDraft(t)
    base.current = { value: t, updatedAt }
  }

  const common = {
    'aria-label': label ?? placeholder ?? 'text',
    value: draft,
    placeholder,
    onFocus: () => setEditing(true),
    onBlur: () => void onBlur(),
    className: 'w-full resize-y rounded bg-zinc-800/80 px-2 py-1 text-xs text-zinc-100 outline-none focus:ring-1 focus:ring-sky-500',
  }

  return (
    <div className="nodrag nowheel">
      {label && (
        <div className="mb-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
          {label}{saving && ' · đang lưu…'}
        </div>
      )}
      {single
        ? <input {...common} onChange={(e) => onChange(e.target.value)} />
        : <textarea {...common} rows={3} onChange={(e) => onChange(e.target.value)} />}
      {conflict !== null && (
        <div role="alert" className="mt-1 rounded bg-amber-900/80 p-2 text-[11px] text-amber-100">
          <div className="mb-1">Có thay đổi từ nơi khác</div>
          <div className="flex gap-2">
            <button className="rounded bg-zinc-700 px-2 py-0.5" onClick={() => void keepMine()}>Giữ bản của tôi</button>
            <button className="rounded bg-sky-700 px-2 py-0.5" onClick={takeTheirs}>Lấy bản mới</button>
          </div>
        </div>
      )}
    </div>
  )
}
