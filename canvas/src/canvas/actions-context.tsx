import { createContext, useContext } from 'react'
import type { Character, Orientation, Project, Scene, SceneReview, Version, Video } from '../api/types'
import type { GenAction } from '../lib/actions'

export type VersionTarget =
  | { kind: 'character'; id: string }
  | { kind: 'scene'; id: string; media: 'image' | 'video'; orientation: Orientation }

export interface XY { x: number; y: number }

export interface CanvasActions {
  projectId: string
  family: string
  canGenerate: boolean
  patchScene(id: string, patch: Partial<Scene>): Promise<Scene>
  patchCharacter(id: string, patch: Partial<Character>): Promise<Character>
  patchVideo(id: string, patch: Partial<Video>): Promise<Video>
  patchProject(patch: Partial<Project>): Promise<Project>
  run(a: GenAction): Promise<void>
  concat(v: Video): Promise<void>
  uploadCharacterImage(cid: string, file: File): Promise<void>
  restore(t: VersionTarget, v: Version): Promise<void>
  review(s: Scene): Promise<SceneReview>
  refreshUrls(): Promise<void>
  setNoteText(key: string, text: string): Promise<{ updated_at: string }>
  addNote(at: XY): Promise<void>
  addScene(video: Video, at: XY): Promise<void>
  addContinuation(parent: Scene, at: XY): Promise<void>
  moveScene(video: Video, scenes: Scene[], sceneId: string, dir: -1 | 1): Promise<void>
  placeCharacter(cid: string, at: XY): Promise<void>
  createAsset(input: { name: string; entity_type: string; description: string }, at: XY, file?: File): Promise<void>
  exportProject(): Promise<void>
}

export const CanvasActionsContext = createContext<CanvasActions | null>(null)

export function useCanvasActions(): CanvasActions {
  const a = useContext(CanvasActionsContext)
  if (!a) throw new Error('CanvasActionsContext missing')
  return a
}
