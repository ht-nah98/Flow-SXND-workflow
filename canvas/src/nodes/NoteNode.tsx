import type { Node, NodeProps } from '@xyflow/react'
import { NodeFrame } from '../components/NodeFrame'
import { useState } from 'react'
import { useCanvasActions } from '../canvas/actions-context'
import { InlineEdit } from '../components/InlineEdit'
import type { NoteNodeData } from '../graph/mapping'

export function NoteNode({ id, data, selected }: NodeProps<Node<NoteNodeData>>) {
  const a = useCanvasActions()
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  return (
    <div data-testid={`node-${id}`} className="h-full w-full overflow-y-auto rounded-xl border border-yellow-700 bg-yellow-950/60 p-2">
      <NodeFrame selected={selected} minWidth={160} minHeight={80} />
      <InlineEdit label="Ghi chú" value={data.text} updatedAt={updatedAt}
                  onSave={async (t) => { const r = await a.setNoteText(id, t); setUpdatedAt(r.updated_at); return r }} />
    </div>
  )
}
