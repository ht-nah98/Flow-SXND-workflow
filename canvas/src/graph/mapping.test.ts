import { describe, expect, it } from 'vitest'
import { buildGraph, matchesName, sceneMedia, type ScriptNodeData } from './mapping'
import { nodeKey, parseKey } from './keys'
import { character, layout, project, request, scene, video } from '../test/fixtures'

const input = (over = {}) => ({
  project,
  videos: [video()],
  scenesByVideo: { v1: [scene(), scene({ id: 's2', display_order: 1, parent_scene_id: 's1', chain_type: 'CONTINUATION' as const })] },
  characters: [character()],
  layout: [layout(nodeKey.character('c1'), 0, 0), layout(nodeKey.scene('s1'), 300, 0), layout('note:n1', 5, 5, { text: 'hi' })],
  requests: [],
  ...over,
})

describe('keys', () => {
  it('round-trips', () => {
    expect(parseKey(nodeKey.scene('abc'))).toEqual({ kind: 'scene', id: 'abc' })
  })
})

describe('buildGraph', () => {
  it('creates one node per asset, scene, video and note', () => {
    const g = buildGraph(input(), new Set())
    expect(g.nodes.map((n) => n.id).sort()).toEqual(
      ['character:c1', 'note:n1', 'scene:s1', 'scene:s2', 'script:p1', 'video:v1'])
    expect(g.nodes.find((n) => n.id === 'note:n1')!.data).toEqual({ kind: 'note', text: 'hi' })
  })

  it('uses stored positions and lists nodes without layout', () => {
    const g = buildGraph(input(), new Set())
    expect(g.nodes.find((n) => n.id === 'scene:s1')!.position).toEqual({ x: 300, y: 0 })
    expect(g.missingLayout.sort()).toEqual(['scene:s2', 'script:p1', 'video:v1'])
  })

  it('creates ref, chain and member edges', () => {
    const ids = buildGraph(input(), new Set()).edges.map((e) => e.id).sort()
    expect(ids).toEqual([
      'chain:s1->s2', 'member:s1->v1', 'member:s2->v1', 'ref:c1->s1', 'ref:c1->s2', 'script:v1',
    ].sort())
  })

  it('matches character_names by slug as well as name (Review Focus 1)', () => {
    const g = buildGraph(input({ scenesByVideo: { v1: [scene({ character_names: ['teacher-lan'] })] } }), new Set())
    expect(g.edges.map((e) => e.id)).toContain('ref:c1->s1')
  })

  it('ignores names that match no attached asset', () => {
    const g = buildGraph(input({ scenesByVideo: { v1: [scene({ character_names: ['Nobody'] })] } }), new Set())
    expect(g.edges.filter((e) => e.id.startsWith('ref:'))).toEqual([])
  })

  it('shows vertical media for a VERTICAL video (Review Focus 3)', () => {
    const g = buildGraph(input({ videos: [video({ orientation: 'VERTICAL' })] }), new Set())
    const d = g.nodes.find((n) => n.id === 'scene:s1')!.data
    expect(d.kind === 'scene' && d.orientation).toBe('VERTICAL')
    expect(sceneMedia(scene(), 'VERTICAL').imageUrl).toBe('https://img/s1-v')
  })

  it('marks stale scenes and exposes the latest failure', () => {
    const g = buildGraph(input({
      requests: [request({ id: 'r9', status: 'FAILED', error_message: 'PUBLIC_ERROR_UNSAFE_GENERATION', updated_at: '2026-10-14T09:00:00Z' })],
    }), new Set(['s2']))
    const s1 = g.nodes.find((n) => n.id === 'scene:s1')!.data
    const s2 = g.nodes.find((n) => n.id === 'scene:s2')!.data
    expect(s1.kind === 'scene' && s1.lastError).toBe('PUBLIC_ERROR_UNSAFE_GENERATION')
    expect(s2.kind === 'scene' && s2.stale).toBe(true)
  })

  it('hides an old failure while a newer attempt is running', () => {
    const g = buildGraph(input({
      requests: [
        request({ id: 'a', status: 'FAILED', error_message: 'held', created_at: '2026-10-14T09:00:00Z', updated_at: '2026-10-14T09:30:00Z' }),
        request({ id: 'b', status: 'PROCESSING', created_at: '2026-10-14T09:10:00Z', updated_at: '2026-10-14T09:10:00Z' }),
      ],
    }), new Set())
    const s1 = g.nodes.find((n) => n.id === 'scene:s1')!.data
    expect(s1.kind === 'scene' && s1.lastError).toBeNull()
  })

  it('adds a finished-film node fed by its video only once the film exists', () => {
    expect(buildGraph(input({ videos: [video({ horizontal_url: null })] }), new Set()).nodes
      .some((n) => n.type === 'final')).toBe(false)
    const g = buildGraph(input({ videos: [video({ horizontal_url: 'file:///out/film.mp4' })] }), new Set())
    const film = g.nodes.find((n) => n.type === 'final')!
    expect(film.id).toBe('final:v1')
    expect(film.data.kind === 'final' && film.data.url).toBe('file:///out/film.mp4')
    expect(g.edges.find((e) => e.target === 'final:v1')?.source).toBe('video:v1')
  })

  it('clears lastError once a later request completed', () => {
    const g = buildGraph(input({
      requests: [
        request({ id: 'a', status: 'FAILED', error_message: 'x', updated_at: '2026-10-14T09:00:00Z' }),
        request({ id: 'b', status: 'COMPLETED', updated_at: '2026-10-14T09:05:00Z' }),
      ],
    }), new Set())
    const s1 = g.nodes.find((n) => n.id === 'scene:s1')!.data
    expect(s1.kind === 'scene' && s1.lastError).toBeNull()
  })

  it('matchesName is exact on name or slug', () => {
    expect(matchesName(character(), 'Teacher Lan')).toBe(true)
    expect(matchesName(character(), 'teacher-lan')).toBe(true)
    expect(matchesName(character(), 'teacher lan')).toBe(false)
  })

  it('flags busy scenes and assets from active requests', () => {
    const g = buildGraph(input({ requests: [
      request({ status: 'PROCESSING' }),
      request({ id: 'r2', scene_id: null, character_id: 'c1', type: 'GENERATE_CHARACTER_IMAGE', status: 'PENDING' }),
    ] }), new Set())
    const s1 = g.nodes.find((n) => n.id === 'scene:s1')!.data
    const c1 = g.nodes.find((n) => n.id === 'character:c1')!.data
    expect(s1.kind === 'scene' && s1.busy).toBe(true)
    expect(c1.kind === 'asset' && c1.busy).toBe(true)
  })

  it('passes stale ids to the video node', () => {
    const v = buildGraph(input(), new Set(['s2'])).nodes.find((n) => n.id === 'video:v1')!.data
    expect(v.kind === 'video' && v.staleIds).toEqual(['s2'])
  })

  it('passes busy scene ids to the video node', () => {
    const g = buildGraph(input({ requests: [request({ status: 'PROCESSING' })] }), new Set())
    const v = g.nodes.find((n) => n.id === 'video:v1')!.data
    expect(v.kind === 'video' && v.busyIds).toEqual(['s1'])
  })
})

describe('script node', () => {
  it('lists every clip in order with its status, newest request deciding failures', () => {
    const g = buildGraph(input({
      scenesByVideo: { v1: [scene({ id: 's2', display_order: 1 }), scene({ horizontal_video_status: 'COMPLETED' }),
                            scene({ id: 's3', display_order: 2 })] },
      requests: [request({ id: 'r9', scene_id: 's2', status: 'FAILED', error_message: 'MEDIA_REMOVED' }),
                 request({ id: 'r8', scene_id: 's3', status: 'PROCESSING' })],
    }), new Set())
    const s = g.nodes.find((n) => n.id === 'script:p1')!
    expect(s.deletable).toBe(false)
    const items = (s.data as ScriptNodeData).parts[0].items
    expect(items.map((i) => [i.scene.id, i.status, i.error])).toEqual([
      ['s1', 'done', null], ['s2', 'failed', 'MEDIA_REMOVED'], ['s3', 'busy', null]])
  })

  it('carries the latest run that has a script, with its generation progress', () => {
    const mk = (id: string, created: string, withScript: boolean) => ({
      id, project_id: 'p1', stage: 'REFS', status: 'RUNNING' as const, gate: null, error: null,
      brief: { text: 'x' }, budget: {}, spent: {}, created_at: created, updated_at: null,
      plan: withScript ? { shotlist: { shots: [] }, requests: { 'ref:Bố': 'q1', 'ref:Phòng': 'q2' } } : {},
    })
    const g = buildGraph(input({
      runs: [mk('old', '2026-01-01', true), mk('new', '2026-02-01', true), mk('draft', '2026-03-01', false)],
      requests: [request({ id: 'q1', status: 'COMPLETED' }), request({ id: 'q2', status: 'PENDING' })],
    }), new Set())
    const d = g.nodes.find((n) => n.id === 'script:p1')!.data as ScriptNodeData
    expect(d.run?.id).toBe('new')
    expect(d.progress).toEqual({ label: 'Ảnh asset', done: 1, total: 2 })
  })

  it('marks the director video so its manual generate buttons stay hidden', () => {
    const run = { id: 'r', project_id: 'p1', stage: 'REFS', status: 'RUNNING' as const, gate: null, error: null,
                  brief: { text: 'x' }, budget: {}, spent: {}, created_at: null, updated_at: null,
                  plan: { ids: { video_id: 'v1' } } }
    const d = (runs: typeof run[]) => buildGraph(input({ runs }), new Set()).nodes.find((n) => n.id === 'video:v1')!.data
    expect((d([run]) as { directed: boolean }).directed).toBe(true)
    expect((d([]) as { directed: boolean }).directed).toBe(false)
  })

  it('shows the film node for a director video before the film exists', () => {
    const run = { id: 'r', project_id: 'p1', stage: 'CUT', status: 'FAILED' as const, gate: null, error: 'x',
                  brief: { text: 'x' }, budget: {}, spent: {}, created_at: null, updated_at: null,
                  plan: { ids: { video_id: 'v1' } } }
    const film = (runs: typeof run[]) => buildGraph(input({ runs }), new Set()).nodes.find((n) => n.id === nodeKey.final('v1'))
    expect(film([run])?.data).toMatchObject({ url: null, run: { id: 'r' } })
    expect(film([])).toBeUndefined()
  })

  it('a scripted director film gets an Agent Review node wired from the film node', () => {
    const run = { id: 'r', project_id: 'p1', stage: 'DONE', status: 'DONE' as const, gate: null, error: null,
                  brief: { text: 'x' }, budget: {}, spent: {}, created_at: null, updated_at: null,
                  plan: { ids: { video_id: 'v1', scenes: { SH01: 's1' } }, shotlist: { shots: [] } } }
    const g = buildGraph(input({ runs: [run] }), new Set())
    const review = g.nodes.find((n) => n.id === nodeKey.review('r'))!
    expect(review.data).toMatchObject({ kind: 'review', sceneKeys: { SH01: nodeKey.scene('s1') } })
    expect(g.edges.find((e) => e.target === review.id)?.source).toBe(nodeKey.final('v1'))
  })
})


describe('resizable boxes (directive G1)', () => {
  it('a box gets its saved size back, or its default width with a free height', () => {
    const sized = { ...layout(nodeKey.scene('s1'), 300, 0), w: 640, h: 500 }
    const g = buildGraph(input({ layout: [layout(nodeKey.character('c1'), 0, 0), sized] }), new Set())
    const s1 = g.nodes.find((n) => n.id === nodeKey.scene('s1'))!
    expect([s1.width, s1.height]).toEqual([640, 500])
    const c1 = g.nodes.find((n) => n.id === nodeKey.character('c1'))!
    expect(c1.width).toBe(220)
    expect(c1.height).toBeUndefined()
  })
})
