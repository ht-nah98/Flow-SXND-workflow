import { useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../api/client'
import type { DirectorRun } from '../api/types'
import { useToast } from './Toast'

type Pkg = { folder: string | null; files: { name: string; content: string }[] }
const LABEL: Record<string, string> = { 'README.md': '📘 README', 'kich-ban.md': '📜 Kịch bản', 'phan-canh-prompt.md': '🎬 Phân cảnh & prompt' }

/** SciCloud sample (19/10): the script as a handover package — three Markdown files, also saved next to the film. */
export function ScriptPackageButton({ run }: { run: DirectorRun }) {
  const toast = useToast()
  const [pkg, setPkg] = useState<Pkg | null>(null)
  const open = async () => {
    try { setPkg(await api.scriptPackage(run.id)) } catch (e) { toast(e instanceof Error ? e.message : String(e), 'error') }
  }
  return (
    <>
      <button className="nodrag rounded bg-zinc-700 px-2 py-1 text-[11px]" onClick={() => void open()}>📦 Gói kịch bản (.md)</button>
      {pkg && createPortal(<PackageDialog pkg={pkg} onClose={() => setPkg(null)} />, document.body)}
    </>
  )
}

function PackageDialog({ pkg, onClose }: { pkg: Pkg; onClose: () => void }) {
  const [tab, setTab] = useState(pkg.files[0]?.name ?? '')
  const file = pkg.files.find((f) => f.name === tab)
  const download = (f: { name: string; content: string }) => {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([f.content], { type: 'text/markdown;charset=utf-8' }))
    a.download = f.name
    a.click()
    URL.revokeObjectURL(a.href)
  }
  return (
    <div role="dialog" aria-label="Gói kịch bản" className="fixed inset-0 z-50 flex justify-center bg-black/70 p-4" onClick={onClose}>
      <article className="flex w-full max-w-[96vw] flex-col gap-3 rounded-xl bg-zinc-900 p-5 text-sm text-zinc-200"
               onClick={(e) => e.stopPropagation()}>
        <header className="flex flex-wrap items-center justify-between gap-2">
          <nav className="flex gap-1">
            {pkg.files.map((f) => (
              <button key={f.name} onClick={() => setTab(f.name)} aria-pressed={tab === f.name}
                      className={`rounded px-2 py-1 ${tab === f.name ? 'bg-sky-700 text-white' : 'bg-zinc-800'}`}>
                {LABEL[f.name] ?? f.name}
              </button>
            ))}
          </nav>
          <span className="flex gap-1">
            {file && <button onClick={() => download(file)} className="rounded bg-zinc-800 px-2 py-1">⬇ Tải {file.name}</button>}
            {file && <button onClick={() => void navigator.clipboard?.writeText(file.content)} className="rounded bg-zinc-800 px-2 py-1">⧉ Sao chép</button>}
            <button onClick={onClose} className="rounded bg-zinc-800 px-2 py-1">Đóng</button>
          </span>
        </header>
        {pkg.folder && <p className="text-xs text-zinc-400">Đã lưu cạnh phim: <code>{pkg.folder}</code></p>}
        <pre className="max-h-[78vh] overflow-auto whitespace-pre-wrap rounded bg-zinc-950 p-4 text-[13px] leading-relaxed">{file?.content}</pre>
      </article>
    </div>
  )
}
