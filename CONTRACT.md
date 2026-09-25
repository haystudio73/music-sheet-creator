# V0 implementation contract

Windows 11, local browser UI, Python API. Real runtime and data only. Root owns `backend/app.py`, `backend/storage.py`, `backend/schemas.py`, configuration/launcher/dependencies. Frontend agent owns `frontend/**`. Notation agent owns `backend/notation.py`, `tests/test_notation.py`. Model agent owns `backend/transcription.py`, `workers/**`, `models/**`, `scripts/setup-model.ps1`, `docs/model-setup.md`. Do not edit other owners' files without coordination.

## Python score data (JSON serializable dictionaries)

`ScoreDocument`: `{schema_version:1, revision:int, title:str, tempo:float, meter:[int,int], key:str, notes:Note[], harmonies:Harmony[], diagnostics:str[], source_engine:str, review_status:'needs_review'|'reviewed', melody_role:'instrumental'|'vocal'}`.

`Note`: `{id:str, pitch:int (MIDI 0..127), start:str, duration:str, velocity:int (1..127), source_start:float|null, source_end:float|null}`. `start`/`duration` are exact fractions of quarter notes e.g. `'3/2'`, `'1'`. Global score-time start, not measure-local. Notes must have nonnegative start and positive duration. Lead melody is monophonic; flag overlaps instead of silently discarding raw notes. Key uses music21 tonic strings e.g. C, G, F, Am. Simple fixed tempo/meter v0, explicitly disclosed; do not claim rubato support.

`Harmony`: `{id:str, root:str, quality:str, bass:str|null, start:str, duration:str, kind:'chord'|'no_chord'|'unknown'}`. Qualities: major, minor, dominant-seventh, major-seventh, minor-seventh, diminished, augmented, suspended-second, suspended-fourth. Global quarter fractions. Root C/C#/Db etc. Keep no_chord/unknown distinct.

## Optional lyrics extension

Backwards-compatible schema version1: `lyrics` defaults `[]`; tokens `{id,text,note_id:str|null,verse:int(1..20),syllabic:'single'|'begin'|'middle'|'end',source_start:float|null,source_end:float|null}`. Maximum20,000 tokens, text1..200 chars, one token per note/verse. Null bindings preserved with review warnings. `lyric_source` defaults null or `{filename,format:'srt'|'lrc',offset_seconds,cue_count}`. MusicXML/PDF engrave first attack only. GET supplies defaults without rewriting legacy revisions.

`POST /api/projects/{id}/lyrics`: multipart `file`, `expected_revision`, `offset_seconds`; returns new saved ScoreDocument200; stale409, >1MiB413, suffix415, invalid422. Replaces lyric layer only, preserving melody/harmonies and old revisions; resets review status. UI requires no unsaved edits. `backend.lyrics.parse_and_align` returns `{lyrics,lyric_source,warnings}`.

## Python adapter modules

Notation functions (root imports): `validate_score(score:dict)->list[str]` diagnostic warnings, raises ValueError for invalid; `export_musicxml(score:dict,path:Path)->None`; `export_midi(score:dict,path:Path,accompaniment:bool=False)->None`; `export_pdf(score:dict,path:Path,musescore_path:str|None=None)->None` subprocess MuseScore with timeout/Windows hidden window; `transpose_score(score:dict,semitones:int)->dict`.

Transcription functions: `engine_status()->list[dict]` each `{id,name,available,description,reason}` (sheetsage2, monophonic); `transcribe(audio_path:Path,options:dict,work_dir:Path,progress:Callable[[str,str],None],cancelled:Callable[[],bool])->dict` ScoreDocument. Options `{engine,tempo:float,meter:[int,int],key:str,melody_role}`. Store raw output in work_dir. Real unavailable model raises descriptive error, never simulate. Optional actual DSP monophonic analyzer clearly labeled experimental, not AI or full-mix support. Model process cannot touch project revisions; root owns persistence.

## HTTP `/api`

- `GET /health`: `{status:'ok',version,ffmpeg:bool,musescore:bool,gpu:str|null,models:EngineStatus[]}`.
- `GET /projects`: active `Project[]`; `?deleted=true` lists trash.
- `DELETE /projects/{id}`: recoverable deletion,200 `{id,deleted:true}`; running/queued job409. Retains files and revisions in place; excludes project from normal reads and mutations.
- `POST /projects/{id}/restore`: restores project from trash and returns Project. Both operations are idempotent for existing projects and require the local session cookie.
- `POST /projects` multipart `file` and optional `title`: Project. WAV/MP3/FLAC, max200MB/10minutes.
- `GET /projects/{id}`: Project.
- `GET /projects/{id}/audio`: FileResponse.
- `POST /projects/{id}/analyze` JSON `{engine,tempo,meter,key,melody_role}`: Job.
- `GET /jobs/{id}`: Job (poll every1second, stop terminal).
- `POST /jobs/{id}/cancel`: Job.
- `GET /projects/{id}/score`: ScoreDocument or404.
- `POST /projects/{id}/lyrics-source` multipart `file`, `offset_seconds`: Project with `lyric_attachment` metadata; stores validated source before analysis, only without score/active job. Analysis aligns the stored source into the resulting draft.
- `PUT /projects/{id}/score` JSON `{expected_revision:int,score:ScoreDocument}`: saved ScoreDocument;409 conflict. Always new revision, old immutable, forces `needs_review` regardless of client status. Frontend keeps undo stack of full scores, save with current expected_revision.
- `POST /projects/{id}/transpose` JSON `{expected_revision,semitones}`: ScoreDocument.
- `GET /projects/{id}/preview?revision=N`: inline MusicXML for in-app preview, allowed before review; does not create an export artifact.
- `POST /projects/{id}/review` JSON `{expected_revision}`: validates saved score, creates reviewed revision; stale revision or active job409.
- `POST /projects/{id}/exports` JSON `{format:'musicxml'|'midi'|'pdf',revision:int,accompaniment:bool}`: `{id,filename,url}` (synchronous export initially, process timeout). Requires current reviewed revision and no active analysis job, otherwise409.
- `GET /artifacts/{id}`: download, with the same current-revision/review/job gate. Old artifact links are locked after score changes.

`Project`: `{id,title,created_at,updated_at,audio_name,duration:float,status:'ready'|'analyzing'|'draft'|'reviewed'|'failed',score_revision:int|null,latest_job:Job|null}`.
Also includes `lyric_attachment` (null or filename/format/offset_seconds/cue_count metadata), and optional pending analysis revision. Raw staged lyrics stay in local SQLite, not in API project responses.
`Job`: `{id,project_id,status:'queued'|'running'|'completed'|'failed'|'cancelled',stage,message,error:str|null,created_at,updated_at}`. No fabricated percent.

Errors JSON `{detail:str}`. Same-origin API. Vite proxy /api to http://127.0.0.1:8765 during development; production API serves `frontend/dist`. Browser frontend fetch credentials same-origin. Initial `/api/health` may set session cookie; mutations require same-origin. No telemetry/CDNs.

## Frontend direction

Vietnamese Swiss design: white/#F7F7F8 surfaces, Helvetica Neue/Arial sans, cobalt #002FA7 accent, sharp grid/hairlines. Three-zone workspace: slim project sidebar, large score/audio center, review/settings inspector. Big readable score title and measure index motif. No fake projects/data; empty state with upload. OSMD renders XML fetched via preview. Actual audio player, note/harmony/lyrics table edits, undo/save, tempo/key/meter settings. Four steps: upload with optional lyrics, analyze, review/listen, export after explicit confirmation. Six locally bundled FluidR3 GM sample banks provide instrument listening choices; selection does not change exported MIDI instrumentation. Model setup status and experimental monophonic scope clear. Build via npm, dependencies bundled locally. Do not generate bitmap imagery.
