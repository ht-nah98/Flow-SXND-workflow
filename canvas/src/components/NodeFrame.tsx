import { NodeResizer } from '@xyflow/react'

/** Directive G1: every box on the canvas can be stretched in width and height; the size is saved with its
 *  position (CanvasPage persists the resize). The handles show on the selected node. */
export function NodeFrame({ selected, minWidth = 200, minHeight = 120 }: {
  selected?: boolean; minWidth?: number; minHeight?: number
}) {
  return (
    <NodeResizer isVisible={!!selected} minWidth={minWidth} minHeight={minHeight}
                 color="#38bdf8" handleClassName="!h-3 !w-3 !rounded-sm" lineClassName="!border-sky-400/60" />
  )
}
