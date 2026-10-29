import type { CanvasNodeRecord, Character, FlowRequest, Project, Scene, Video } from '../api/types'

export const project: Project = {
  id: 'p1', name: 'Test', description: null, story: null, material: 'realistic', status: 'ACTIVE',
  video_model_family: 'veo', user_paygate_tier: 'PAYGATE_TIER_ONE', created_at: null, updated_at: null,
}

export const character = (o: Partial<Character> = {}): Character => ({
  id: 'c1', name: 'Teacher Lan', slug: 'teacher-lan', entity_type: 'character', description: 'd',
  image_prompt: null, voice_description: null, reference_image_url: 'https://img/c1', media_id: 'm-c1',
  created_at: null, updated_at: '2026-10-14T08:00:00Z', ...o,
})

export const video = (o: Partial<Video> = {}): Video => ({
  id: 'v1', project_id: 'p1', title: 'V', display_order: 0, status: 'DRAFT', orientation: 'HORIZONTAL',
  horizontal_url: null, vertical_url: null, duration: null, updated_at: null, ...o,
})

export const scene = (o: Partial<Scene> = {}): Scene => ({
  id: 's1', video_id: 'v1', display_order: 0, prompt: 'p', image_prompt: null, video_prompt: 'vp',
  transition_prompt: null, character_names: ['Teacher Lan'], parent_scene_id: null, chain_type: 'ROOT',
  horizontal_image_url: 'https://img/s1-h', horizontal_image_media_id: 'm1', horizontal_image_status: 'COMPLETED',
  horizontal_video_url: null, horizontal_video_media_id: null, horizontal_video_status: 'PENDING',
  vertical_image_url: 'https://img/s1-v', vertical_image_media_id: 'm1v', vertical_image_status: 'COMPLETED',
  vertical_video_url: null, vertical_video_media_id: null, vertical_video_status: 'PENDING',
  updated_at: '2026-10-14T08:00:00Z', ...o,
})

export const request = (o: Partial<FlowRequest> = {}): FlowRequest => ({
  id: 'r1', type: 'GENERATE_IMAGE', status: 'COMPLETED', project_id: 'p1', video_id: 'v1', scene_id: 's1',
  character_id: null, orientation: 'HORIZONTAL', media_id: 'm', output_url: 'https://o', error_message: null,
  created_at: '2026-10-14T08:00:00Z', updated_at: '2026-10-14T08:00:00Z', ...o,
})

export const layout = (node_key: string, x = 0, y = 0, data: Record<string, unknown> = {}): CanvasNodeRecord => ({
  project_id: 'p1', node_key, x, y, w: null, h: null, data, updated_at: '2026-10-14T08:00:00Z',
})
