export interface EngineStatus { id: string; name: string; available: boolean; description: string; reason: string | null }
export interface Health { status: string; version: string; ffmpeg: boolean; musescore: boolean; gpu: string | null; models: EngineStatus[] }
export interface Note { id: string; pitch: number; start: string; duration: string; velocity: number; source_start: number | null; source_end: number | null }
export interface Harmony { id: string; root: string; quality: string; bass: string | null; start: string; duration: string; kind: 'chord' | 'no_chord' | 'unknown' }
export interface LyricToken { id: string; text: string; note_id: string | null; verse: number; syllabic: 'single' | 'begin' | 'middle' | 'end'; source_start: number | null; source_end: number | null }
export interface LyricSource { filename: string; format: 'srt' | 'lrc'; offset_seconds: number; cue_count: number }
export interface ScoreDocument { schema_version: 1; revision: number; title: string; tempo: number; meter: [number, number]; key: string; notes: Note[]; harmonies: Harmony[]; lyrics?: LyricToken[]; lyric_source?: LyricSource | null; diagnostics: string[]; source_engine: string; review_status: 'needs_review' | 'reviewed'; melody_role: 'instrumental' | 'vocal' }
export interface Job { id: string; project_id: string; status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'; stage: string; message: string; error: string | null; created_at: string; updated_at: string; queue_position?: number | null; queue_length?: number; estimated_wait_seconds?: number }
export interface QueueStatus { max_workers: number; max_queue: number; max_active_per_ip: number; running_jobs: number; queued_jobs: number; is_busy: boolean; is_full: boolean; client_ip: string | null; client_active_job_id: string | null; client_can_submit: boolean }
export interface Project { id: string; title: string; created_at: string; updated_at: string; audio_name: string; duration: number; status: 'ready' | 'analyzing' | 'draft' | 'reviewed' | 'failed'; score_revision: number | null; pending_score_revision?: number | null; latest_job: Job | null; lyric_attachment?: LyricSource | null }
export interface AnalyzeOptions { engine: string; tempo: number; meter: [number, number]; key: string; melody_role: 'instrumental' | 'vocal' }
export interface Artifact { id: string; filename: string; url: string }
export interface ExportOptions {
  format: 'musicxml' | 'midi' | 'pdf' | 'abc';
  revision: number;
  accompaniment?: boolean;
  include_chords?: boolean;
  include_lyrics?: boolean;
  scope?: 'full' | 'range';
  bar_start?: number | null;
  bar_end?: number | null;
  custom_title?: string | null;
}
