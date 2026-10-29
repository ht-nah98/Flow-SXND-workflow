import { useStore } from '@xyflow/react'

/** Below this zoom the editors are unreadable: nodes collapse to their picture and essentials. */
export const COMPACT_ZOOM = 0.45

export const useCompact = () => useStore((s) => s.transform[2] < COMPACT_ZOOM)
