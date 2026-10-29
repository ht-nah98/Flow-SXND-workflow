import type { APIRequestContext } from '@playwright/test'

export const FK = 'http://127.0.0.1:8120'

export async function seedProject(request: APIRequestContext, name: string) {
  const post = async (path: string, data: unknown) => (await request.post(FK + path, { data })).json()
  const p = await post('/api/projects', { name, story: 'e2e', material: 'realistic', flow_project_id: 'e2e-flow-project' })
  const v = await post('/api/videos', { project_id: p.id, title: name, orientation: 'HORIZONTAL', display_order: 0 })
  const c = await post('/api/characters', { name: 'Teacher Lan', entity_type: 'character', description: 'elderly teacher' })
  await request.post(`${FK}/api/projects/${p.id}/characters/${c.id}`)
  const s1 = await post('/api/scenes', { video_id: v.id, display_order: 0, chain_type: 'ROOT', prompt: 'enters classroom',
                                         video_prompt: 'walks in', character_names: ['Teacher Lan'] })
  const s2 = await post('/api/scenes', { video_id: v.id, display_order: 1, chain_type: 'CONTINUATION', parent_scene_id: s1.id,
                                         prompt: 'writes on board', video_prompt: 'writes', character_names: ['Teacher Lan'] })
  return { pid: p.id as string, vid: v.id as string, cid: c.id as string, s1: s1.id as string, s2: s2.id as string }
}
