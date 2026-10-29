export type Orientation = 'HORIZONTAL' | 'VERTICAL'
export type MediaStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
export type EntityType =
  | 'character' | 'location' | 'visual_asset' | 'creature' | 'generic_troop' | 'faction'

export interface Project {
  id: string
  name: string
  description: string | null
  story: string | null
  material: string | null
  status: string
  video_model_family: string
  /** refs (default): prompt + asset references. image: first-frame image, then video (opt-in). */
  video_mode?: 'refs' | 'image'
  /** The Google account whose Flow holds this project and its media (account rotation). */
  flow_account?: string | null
  user_paygate_tier: string
  created_at: string | null
  updated_at: string | null
}

export interface Character {
  id: string
  name: string
  slug: string | null
  entity_type: EntityType
  description: string | null
  image_prompt: string | null
  voice_description: string | null
  reference_image_url: string | null
  media_id: string | null
  created_at: string | null
  updated_at: string | null
}

export interface Video {
  id: string
  project_id: string
  title: string
  display_order: number
  status: string
  orientation: Orientation | null
  horizontal_url: string | null
  vertical_url: string | null
  duration: number | null
  updated_at: string | null
}

export interface Scene {
  id: string
  video_id: string
  display_order: number
  prompt: string | null
  image_prompt: string | null
  video_prompt: string | null
  transition_prompt: string | null
  character_names: string[] | null
  parent_scene_id: string | null
  chain_type: 'ROOT' | 'CONTINUATION' | 'INSERT'
  horizontal_image_url: string | null
  horizontal_image_media_id: string | null
  horizontal_image_status: MediaStatus | null
  horizontal_video_url: string | null
  horizontal_video_media_id: string | null
  horizontal_video_status: MediaStatus | null
  vertical_image_url: string | null
  vertical_image_media_id: string | null
  vertical_image_status: MediaStatus | null
  vertical_video_url: string | null
  vertical_video_media_id: string | null
  vertical_video_status: MediaStatus | null
  duration?: number | null
  updated_at: string | null
}

export interface FlowRequest {
  id: string
  type: string
  status: MediaStatus
  project_id: string | null
  video_id: string | null
  scene_id: string | null
  character_id: string | null
  orientation: Orientation | null
  media_id: string | null
  output_url: string | null
  error_message: string | null
  prompt_snapshot?: string | null
  created_at: string | null
  updated_at: string | null
}

export interface RequestCreate {
  type: string
  project_id: string
  video_id?: string
  scene_id?: string
  character_id?: string
  orientation?: Orientation
}

export interface Version {
  request_id: string
  type: string
  media_id: string | null
  output_url: string | null
  prompt_snapshot: string | null
  created_at: string | null
  updated_at: string | null
}

export interface CanvasNodeRecord {
  project_id: string
  node_key: string
  x: number
  y: number
  w: number | null
  h: number | null
  data: Record<string, unknown>
  updated_at: string
}

export interface Health {
  status: string
  extension_connected: boolean
  media_provider: string
}

export interface SystemCheck {
  ok: boolean
  items: { key: string; label: string; ok: boolean; detail: string; fix: string }[]
}

export interface SampleMeta {
  id: string; name: string; status: 'ANALYZING' | 'READY' | 'FAILED' | 'ADOPTED'; error: string | null
  created_at: string; title?: string; duration_s?: number; shots?: number; adopted?: number[]; playbook?: string
}
export interface SampleAnalysis {
  title: string; summary: string; structure: string
  shots: { start_s: number; end_s: number; content: string; framing: string; angle: string; movement: string;
           transition_in: string; look: string }[]
  techniques: { name: string; scope: string; rule: string; how: string; example: string }[]
}

export interface CreditSummary {
  today: number; cap: number; left_today: number | null; prices: Record<string, number>; estimated: boolean
  project?: number
}

/** CapCut-style effects the cut can use (agent/director/effects.py). */
export interface EffectOption { id: string; label: string; use: string }
export interface EffectsCatalog { looks: EffectOption[]; transitions: EffectOption[]; fx: EffectOption[] }
export interface ClipEditChoice { shot_id: string; fx?: string[]; transition_out?: string | null }
export interface FilmEdit { look: string | null; clips: ClipEditChoice[] }

export interface RunTimeline {
  status: DirectorRun['status']; stage: string; gate: string | null; edit_loops: number; since: string | null
  steps: { stage: string; attempt: number; status: string; duration_ms: number | null; created_at: string }[]
  typical_ms: Record<string, number>
}

export interface Material { id: string; name: string; scene_prefix?: string | null }

/** One fault the video reviewer saw in the clip (video_reviewer.py). */
export interface ReviewError { severity?: 'CRITICAL' | 'HIGH' | 'MINOR' | string; time_range?: string; description?: string; type?: string }
export type FilmMode = 'continuous' | 'cut' | 'keyframe' | 'ambient'
/** Ambient mode (directive B14): a live-performance venue, served by GET /api/director/venues (agent/director/venues.py). */
export interface Venue { id: string; name: string; explain: string; place: string; look: string; details: string }
/** The ambient choices on the idea: venue id, reel length (60–120s), looped length (null = the music's length). */
export interface AmbientChoice { venue?: string; reel_s?: number; loop_s?: number | null }
export interface SceneReview {
  scene_id: string
  overall_score: number
  verdict: string
  errors: ReviewError[]
  fix_guide: string
  has_critical_errors: boolean
}

export interface ExportSkip { kind: string; id: string; reason: string }
export interface ExportResult {
  project_dir: string
  zip_path: string
  downloaded: number
  skipped: ExportSkip[]
}

export interface ConcatResult { url: string; duration: number; scenes_missing: number }

export type ImageUse = 'character' | 'location' | 'visual_asset' | 'mood'
export interface IdeaImageIn { base64: string; filename: string; note: string | null }

/** An AI Director run: the idea and how far Claude has taken it (backend director_run). */
/** auto: the AI reads it from the idea; the rest are the user's explicit choice. */
export type VoiceChoice = 'auto' | 'none' | 'voiceover' | 'dialogue'
/** The film's language: spoken words and the prompts sent to Flow. */
export type FilmLanguage = 'en' | 'vi'
/** How freely the writer develops the idea (directive B9). */
export type Creativity = 'faithful' | 'balanced' | 'bold'
/** Optional AI roles of a film (directive A5); the writer, director and DP always run. */
export interface Agents { producer: boolean; editor: boolean; qc: boolean; coach: boolean }

export type ReviewLayer = 'story' | 'clips' | 'continuity' | 'edit'
export interface ReviewFinding {
  id: string; layer: ReviewLayer; severity: 'CRITICAL' | 'HIGH' | 'MINOR'
  scene: number | null; shot_id: string | null; clip_t: number | null; film_t: number | null
  title: string; evidence: string; cause: string; cause_detail: string; fix: string; action: string; rule: string | null
}
export interface FilmReviewEntry {
  id: string; created_at: string; final_path: string | null; note: string; film_duration_s: number
  clips: { scene: number; shot_id: string; idea: string; used_in_film_s: [number, number]; film_start_s: number }[]
  summary: string; strengths: string[]; scores: { layer: ReviewLayer; score: number; note: string }[]
  findings: ReviewFinding[]
}
export interface FilmReviewState {
  job: { status: 'RUNNING' | 'FAILED'; error: string | null; started: number; note: string } | null
  reviews: FilmReviewEntry[]
}

export interface DirectorRun {
  id: string
  project_id: string | null
  stage: string
  status: 'RUNNING' | 'WAITING_GATE' | 'PAUSED' | 'FAILED' | 'DONE' | 'CANCELLED'
  gate: string | null
  error: string | null
  brief: { text: string; target_s?: number; orientation?: Orientation; style?: string; voice?: VoiceChoice; language?: FilmLanguage; creativity?: Creativity; style_pack?: string | null; agents?: Agents; film_mode?: FilmMode; venue?: string; reel_s?: number; loop_s?: number | null;
           images?: { file: string; note: string | null }[] }
  budget: Record<string, number>
  spent: Record<string, number>
  plan: {
    brief?: { logline?: string; film_mode?: FilmMode; venue?: string | null; reel_s?: number | null; voice?: 'none' | 'voiceover' | 'dialogue'; voice_style?: string | null; language?: string; images?: { file: string; use: ImageUse; name?: string | null; description: string }[] }
    gate_payload?: Record<string, unknown>
    story?: { synopsis: string; story_line?: string; message?: string; viewer_value?: string; rule_and_cost?: string;
      source_map?: { part: string; beats: string[]; kept: 'full' | 'compressed' | 'dropped'; note?: string }[]
      notes_for_user?: string[]; director_notes?: string[]; hooks?: { at_s: number; beat_id: string; moment: string }[]
      sequences?: { id: string; title: string; act: number; purpose: string; start_s?: number | null; end_s?: number | null }[]
      cast: { name: string; entity_type: 'character' | 'location' | 'visual_asset'; description?: string; personality?: string; signature?: string }[] }
    shotlist?: { shots: unknown[] }
    mode?: 'step' | 'auto'
    edit_loops?: number
    editor?: { score?: number; fixes?: { target_stage: string; shot_id: string | null; issue: string }[] }
    ids?: { project_id?: string; video_id?: string | null; scenes?: Record<string, string> }
    requests?: Record<string, string>
    failed?: Record<string, string>
    trims?: [number, number][]   // the cut: seconds kept of each shot used, in film order
    drop?: string[]              // shots left out of the cut
  }
  created_at: string | null
  updated_at: string | null
}

/** 📋 Nhật ký (21/10): steps with their sent-back reasons, AI calls, Flow requests, gates. */
export interface RunLogIssue { rule: string; label: string; shot_id: string | null; scene: number | null; message: string; severity: string }
export interface RunLogStep { id: string; stage: string; label: string; attempt: number; status: string; duration_ms: number | null; created_at: string; issues: RunLogIssue[] }
export interface RunLogEvent { id: string; kind: 'stage' | 'ai' | 'gate' | 'chain' | 'qc' | 'error'; level: 'info' | 'ok' | 'warn' | 'error'; title: string; data: Record<string, unknown>; created_at: string }
export interface RunLogRequest { id: string; type: string; label: string; status: string; scene: number | null; entity: string | null; error: string | null; retries: number; created_at: string; updated_at: string }
export interface RunLog { run_id: string; status: string; stage: string; stage_label: string; gate: string | null; steps: RunLogStep[]; events: RunLogEvent[]; requests: RunLogRequest[] }
