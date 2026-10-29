import { useQueries, useQuery, type UseQueryResult } from '@tanstack/react-query'
import { useMemo } from 'react'
import type { GraphInput } from '../graph/mapping'
import { api } from './client'
import type { Scene } from './types'
import { useConnection } from './connection'

export const projectKey = (pid: string) => ['p', pid] as const

function usePoll() {
  const { wsOpen, wsDownSince } = useConnection()
  return !wsOpen && wsDownSince !== null && Date.now() - wsDownSince > 10_000 ? 5000 : false
}

export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 5000, retry: false })
export const useProjects = () => useQuery({ queryKey: ['projects'], queryFn: api.listProjects })
export const useVenues = () => useQuery({ queryKey: ['venues'], queryFn: api.listVenues, staleTime: Infinity })
export const useStyles = () => useQuery({ queryKey: ['styles'], queryFn: api.listStyles, staleTime: Infinity })
export const useLibrary = () => useQuery({ queryKey: ['library'], queryFn: api.listAllCharacters })
export const useMaterials = () =>
  useQuery({ queryKey: ['materials'], queryFn: api.listMaterials, staleTime: Infinity })

// Stable reference: TanStack only re-runs combine when a query result changed.
const combineScenes = (rs: UseQueryResult<Scene[]>[]) => ({
  data: rs.map((r) => r.data), isLoading: rs.some((r) => r.isLoading), error: rs.find((r) => r.error)?.error,
})

export function useProjectData(pid: string) {
  const refetchInterval = usePoll()
  const base = projectKey(pid)
  const project = useQuery({ queryKey: [...base, 'project'], queryFn: () => api.getProject(pid), refetchInterval })
  const videos = useQuery({ queryKey: [...base, 'videos'], queryFn: () => api.listVideos(pid), refetchInterval })
  const characters = useQuery({ queryKey: [...base, 'characters'], queryFn: () => api.listProjectCharacters(pid), refetchInterval })
  const canvas = useQuery({ queryKey: [...base, 'canvas'], queryFn: () => api.getCanvas(pid), refetchInterval })
  const vids = videos.data ?? []
  const scenes = useQueries({ queries: vids.map((v) => ({
    queryKey: [...base, 'scenes', v.id], queryFn: () => api.listScenes(v.id), refetchInterval })),
    combine: combineScenes })
  const requests = useQuery({ queryKey: [...base, 'requests'], queryFn: () => api.listProjectRequests(pid), refetchInterval })
  const runs = useQuery({ queryKey: [...base, 'runs'], queryFn: () => api.listRuns(pid), refetchInterval })

  const all = [project, videos, characters, canvas, requests]
  const data = useMemo<GraphInput | undefined>(() => {
    if (!project.data || !videos.data || !characters.data || !canvas.data || !requests.data) return undefined
    if (scenes.data.some((d) => d === undefined)) return undefined
    return {
      project: project.data,
      videos: videos.data,
      scenesByVideo: Object.fromEntries(videos.data.map((v, i) => [v.id, scenes.data[i]!])),
      characters: characters.data,
      layout: canvas.data.nodes,
      requests: requests.data,
      runs: runs.data ?? [],
    }
  }, [project.data, videos.data, characters.data, canvas.data, requests.data, scenes.data, runs.data])
  return {
    data,
    isLoading: all.some((q) => q.isLoading) || scenes.isLoading,
    error: all.find((q) => q.error)?.error ?? scenes.error,
  }
}
