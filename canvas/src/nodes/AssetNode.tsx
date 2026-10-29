import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { NodeFrame } from '../components/NodeFrame'
import { useEffect, useState } from 'react'
import { useCanvasActions } from '../canvas/actions-context'
import { InlineEdit } from '../components/InlineEdit'
import { MediaView } from '../components/MediaView'
import { VersionStrip } from '../components/VersionStrip'
import { useCompact } from '../canvas/zoom'
import { TYPE_ICON } from '../graph/colors'
import type { AssetNodeData } from '../graph/mapping'

const TYPE_LABEL: Record<string, string> = {
  character: 'Nhân vật', location: 'Bối cảnh', visual_asset: 'Đạo cụ',
  creature: 'Sinh vật', generic_troop: 'Nhóm', faction: 'Phe',
}

/**
 * The name drives server-side rename cascades across every project that
 * shares this asset — autosaving per keystroke-pause (like InlineEdit)
 * would cascade on every partial name, and a partial name can collide
 * with another asset's name/slug mid-typing. Save on blur/Enter only.
 */
function NameField({ characterId, name, onSave }: { characterId: string; name: string; onSave: (v: string) => void }) {
  const [draft, setDraft] = useState(name)
  useEffect(() => setDraft(name), [characterId, name])
  const commit = () => { if (draft.trim() && draft !== name) onSave(draft) }
  return (
    <div className="nodrag nowheel">
      <div className="mb-0.5 text-[10px] uppercase tracking-wide text-zinc-400">Tên</div>
      <input aria-label="Tên" value={draft} onChange={(e) => setDraft(e.target.value)}
             onBlur={commit} onKeyDown={(e) => { if (e.key === 'Enter') { commit(); e.currentTarget.blur() } }}
             className="w-full rounded bg-zinc-800/80 px-2 py-1 text-xs text-zinc-100 outline-none focus:ring-1 focus:ring-sky-500" />
    </div>
  )
}

export function AssetNode({ id, data, selected }: NodeProps<Node<AssetNodeData>>) {
  const a = useCanvasActions()
  const c = data.character
  const [over, setOver] = useState(false)
  const save = (field: 'description' | 'image_prompt' | 'voice_description') =>
    (v: string) => a.patchCharacter(c.id, { [field]: v })
  const compact = useCompact()
  const missing = !c.media_id && !data.busy
  const header = (
    <div className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-[10px] font-semibold uppercase text-zinc-950"
         style={{ background: data.color }}>
      <span>{TYPE_ICON[c.entity_type] ?? '•'} {TYPE_LABEL[c.entity_type] ?? c.entity_type}</span>
      <span className="ml-auto normal-case">{missing ? '⚠️ Chưa có ảnh · ' : ''}dùng ở {data.uses} cảnh</span>
    </div>
  )
  // 20/10: an asset with no picture must be impossible to miss — even zoomed out, with its own Gen button.
  const genButton = (
    <button disabled={!a.canGenerate || data.busy}
            className={`nodrag rounded px-2 py-1 font-semibold disabled:opacity-40 ${c.media_id ? 'bg-sky-700 text-[11px]' : 'bg-amber-600 text-sm text-zinc-950'}`}
            onClick={() => void a.run({ kind: 'asset-image', character: c })}>
      {c.media_id ? 'Gen lại ảnh' : '🖼 Gen ảnh (≈1 credit)'}
    </button>
  )
  const out = <Handle type="source" position={Position.Right} id="out" className="!h-3 !w-3" style={{ background: data.color }} />
  if (compact) {
    return (
      <div data-testid={`node-${id}`} className={`flex h-full w-full flex-col overflow-y-auto gap-2 rounded-xl border-4 bg-zinc-900 p-2 ${missing ? 'border-dashed' : ''}`}
           style={{ borderColor: missing ? '#f59e0b' : data.color }}>
        <NodeFrame selected={selected} minWidth={180} minHeight={160} />
        {header}
        <div className="truncate text-2xl font-bold" style={{ color: data.color }}>{c.name}</div>
        <MediaView url={c.reference_image_url} kind="image" busy={data.busy} />
        {!c.media_id && genButton}
        {out}
      </div>
    )
  }
  return (
    <div data-testid={`node-${id}`}
         className={`flex h-full w-full flex-col overflow-y-auto gap-2 rounded-xl border-2 bg-zinc-900 p-2 shadow ${over ? '!border-sky-400' : ''}`}
         style={{ borderColor: over ? undefined : missing ? '#f59e0b' : data.color }}
         onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setOver(true) } }}
         onDragLeave={() => setOver(false)}
         onDrop={(e) => {
           const f = e.dataTransfer.files[0]
           if (!f) return
           e.preventDefault(); e.stopPropagation(); setOver(false)
           void a.uploadCharacterImage(c.id, f)
         }}>
      <NodeFrame selected={selected} minWidth={180} minHeight={160} />
      {header}
      <NameField characterId={c.id} name={c.name} onSave={(v) => void a.patchCharacter(c.id, { name: v })} />
      <MediaView url={c.reference_image_url} kind="image" busy={data.busy} />
      <InlineEdit label="Mô tả" value={c.description} updatedAt={c.updated_at} onSave={save('description')} />
      <InlineEdit label="Prompt ảnh" value={c.image_prompt} updatedAt={c.updated_at} onSave={save('image_prompt')} />
      {c.entity_type === 'character' && (
        <InlineEdit label="Giọng nói" value={c.voice_description} updatedAt={c.updated_at} onSave={save('voice_description')} />
      )}
      <div className="nodrag flex gap-1 [&>button]:flex-1">
        {genButton}
        <label className="cursor-pointer rounded bg-zinc-700 px-2 py-1 text-[11px]">
          Upload
          <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
                 onChange={(e) => { const f = e.target.files?.[0]; if (f) void a.uploadCharacterImage(c.id, f); e.target.value = '' }} />
        </label>
      </div>
      <VersionStrip target={{ kind: 'character', id: c.id }} currentMediaId={c.media_id} />
      {out}
    </div>
  )
}
