export type KeyKind = 'character' | 'scene' | 'video' | 'final' | 'script' | 'idea' | 'note' | 'review'

export const nodeKey = {
  character: (id: string) => `character:${id}`,
  scene: (id: string) => `scene:${id}`,
  video: (id: string) => `video:${id}`,
  final: (id: string) => `final:${id}`,
  script: (projectId: string) => `script:${projectId}`,
  idea: (runId: string) => `idea:${runId}`,
  note: (id: string) => `note:${id}`,
  review: (runId: string) => `review:${runId}`,
}

export function parseKey(key: string): { kind: KeyKind; id: string } {
  const i = key.indexOf(':')
  return { kind: key.slice(0, i) as KeyKind, id: key.slice(i + 1) }
}
