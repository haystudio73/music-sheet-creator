"""Windows-first, same-origin local API for audio transcription and score review."""
import hashlib
import json
import json
import logging
import os
import secrets
import shutil
import subprocess
import threading
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path, PureWindowsPath
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool

from .schemas import (ActivateScoreRequest, AnalyzeRequest, ExportRequest,
                      SaveScoreRequest, ScoreDocument, TransposeRequest, ReviewRequest, SaveEditorRequest,
                      UpdateProjectRequest)
from .storage import ConflictError, Store, atomic_json
from .queue_manager import IpActiveSessionError, QueueBusyError, QueueManager

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 200 * 1024 * 1024
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
LOGGER = logging.getLogger("sheet_studio")


def subproc_kwargs():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def executable(name, env_name=None, fallback=None):
    configured = os.environ.get(env_name) if env_name else None
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which(name)
    if found:
        return found
    if fallback and Path(fallback).is_file():
        return fallback
    return None


def probe_audio(path):
    command = executable("ffprobe")
    if not command:
        raise ValueError("Chưa có ffprobe. Hãy cài FFmpeg và thêm thư mục bin vào PATH.")
    result = subprocess.run([command, "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)], capture_output=True, timeout=30, **subproc_kwargs())
    if result.returncode:
        raise ValueError("Không đọc được audio. Hãy kiểm tra file WAV, MP3 hoặc FLAC.")
    try:
        info = json.loads(result.stdout)
        duration = float(info["format"]["duration"])
        if not any(stream.get("codec_type") == "audio" for stream in info.get("streams", [])):
            raise ValueError()
        if not 0 < duration <= 600:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError("Audio phải có thời lượng lớn hơn 0 và không quá 10 phút.") from None
    return duration


def gpu_name():
    command = shutil.which("nvidia-smi")
    if not command:
        return None
    try:
        result = subprocess.run([command, "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True, timeout=5, **subproc_kwargs())
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


def get_client_session(request: Request) -> str:
    return (
        request.headers.get("x-client-session")
        or request.cookies.get("studio_client_session")
        or ""
    ).strip()


def create_app(data_dir: Path | None = None):
    store = Store(data_dir or Path(os.environ.get("SHEET_STUDIO_DATA", ROOT / "data")))
    queue_mgr = QueueManager(store)
    token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        store.recover_jobs()
        app.state.gpu = gpu_name()
        yield
        queue_mgr.shutdown()

    app = FastAPI(title="Sheet Studio Local", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.queue_mgr = queue_mgr
    app.state.gpu = None
    network_mode = os.environ.get("SHEET_STUDIO_NETWORK_MODE", "0") in ("1", "true", "yes")
    allowed_hosts = [h.strip() for h in os.environ.get("SHEET_STUDIO_ALLOWED_HOSTS", "*").split(",") if h.strip()] if network_mode else ["127.0.0.1", "localhost", "testserver"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts if "*" not in allowed_hosts else ["*"])
    if network_mode:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def protect_local_api(request: Request, call_next):
        if request.url.path.startswith("/api"):
            origin = request.headers.get("origin")
            if origin and not network_mode:
                parsed = urlparse(origin)
                allowed = {"http://127.0.0.1:8765", "http://localhost:8765", "http://127.0.0.1:5173", "http://localhost:5173"}
                # Allow this same-origin local instance when started on another port.
                if request.url.hostname in {'127.0.0.1', 'localhost'}:
                    allowed.add(str(request.base_url).rstrip('/'))
                if origin not in allowed or parsed.username is not None:
                    return JSONResponse({"detail": "Nguồn truy cập không được phép"}, status_code=403)
            if request.method not in ("GET", "HEAD", "OPTIONS") and not network_mode:
                if not secrets.compare_digest(request.cookies.get("studio_session", ""), token):
                    return JSONResponse({"detail": "Phiên local đã hết hạn. Hãy tải lại trang."}, status_code=403)
                if request.headers.get("sec-fetch-site") == "cross-site":
                    return JSONResponse({"detail": "Yêu cầu khác nguồn bị từ chối"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(KeyError)
    async def missing_handler(request, exc):
        return JSONResponse({"detail": "Không tìm thấy dự án, bản nhạc hoặc tệp yêu cầu."}, status_code=404)

    @app.exception_handler(FileNotFoundError)
    async def file_missing_handler(request, exc):
        return JSONResponse({"detail": f"Không tìm thấy tệp yêu cầu trên hệ thống: {str(exc)}"}, status_code=404)

    @app.exception_handler(ConflictError)
    async def conflict_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ValueError)
    async def value_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(IpActiveSessionError)
    async def ip_active_handler(request, exc: IpActiveSessionError):
        return JSONResponse({"detail": str(exc), "code": "IP_SESSION_ACTIVE", "active_job_id": exc.active_job_id}, status_code=429)

    @app.exception_handler(QueueBusyError)
    async def queue_busy_handler(request, exc: QueueBusyError):
        return JSONResponse({"detail": str(exc), "code": "QUEUE_BUSY", "current_queued": exc.current_queued, "max_queue": exc.max_queue}, status_code=503, headers={"Retry-After": "30"})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        LOGGER.exception("Unhandled server exception: %s", exc)
        return JSONResponse({"detail": f"Lỗi máy chủ nội bộ: {str(exc)}", "type": type(exc).__name__}, status_code=500)

    @app.get("/api/health")
    def health(request: Request):
        from .transcription import engine_status
        client_session = get_client_session(request) or secrets.token_hex(16)
        response = JSONResponse({"status": "ok", "version": "0.1.0", "ffmpeg": bool(executable("ffmpeg")), "pdf_export": "browser", "gpu": app.state.gpu, "models": engine_status(), "client_session": client_session})
        response.set_cookie("studio_session", token, httponly=True, samesite="strict", path="/")
        response.set_cookie("studio_client_session", client_session, httponly=False, samesite="lax", path="/")
        return response

    @app.get("/api/projects")
    def list_projects(request: Request, deleted: bool = False):
        client_ip = get_client_ip(request)
        session_id = get_client_session(request)
        return store.projects(deleted=deleted, client_ip=client_ip, session_id=session_id)

    @app.post("/api/projects", status_code=201)
    async def import_audio(request: Request, file: UploadFile = File(...), title: str | None = Form(None)):
        client_ip = get_client_ip(request)
        session_id = get_client_session(request)
        filename = PureWindowsPath(file.filename or "audio.wav").name
        suffix = Path(filename).suffix.lower()
        if suffix not in {".wav", ".mp3", ".flac"}:
            raise HTTPException(415, "Hỗ trợ WAV, MP3 và FLAC.")
        if title is not None and (not title.strip() or len(title.strip()) > 200):
            raise HTTPException(422, "Tên dự án cần từ 1 đến 200 ký tự.")
        project_id = uuid.uuid4().hex
        path = store.root / "projects" / project_id / "original" / ("audio" + suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        size, digest = 0, hashlib.sha256()
        try:
            with path.open("wb") as target:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise HTTPException(413, "File vượt giới hạn 200 MB.")
                    digest.update(chunk)
                    target.write(chunk)
            duration = await run_in_threadpool(probe_audio, path)
            return store.create_project(project_id, title.strip() if title else Path(filename).stem[:200], filename[:255], path, digest.hexdigest(), duration, client_ip=client_ip, session_id=session_id)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str):
        return store.project(project_id)

    @app.patch("/api/projects/{project_id}")
    @app.put("/api/projects/{project_id}")
    def update_project(project_id: str, body: UpdateProjectRequest):
        title = body.title.strip()
        if not title or len(title) > 200:
            raise HTTPException(422, "Tên bài hát cần từ 1 đến 200 ký tự.")
        with store.lock:
            project = store.project(project_id)
            if project["score_revision"] is not None:
                score = store.score(project_id)
                score["title"] = title
                store.save_score(project_id, score, expected_revision=project["score_revision"])
            else:
                store.update_project_title(project_id, title)
        return store.project(project_id)

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str):
        store.delete_project(project_id)
        return {"id": project_id, "deleted": True}

    @app.post("/api/projects/{project_id}/restore")
    def restore_project(project_id: str):
        return store.restore_project(project_id)

    @app.post("/api/projects/empty-trash")
    def empty_trash(request: Request):
        client_ip = get_client_ip(request)
        session_id = get_client_session(request)
        count = store.empty_trash(client_ip=client_ip, session_id=session_id)
        return {"emptied": True, "count": count}

    @app.get("/api/projects/{project_id}/audio")
    def get_audio(project_id: str):
        path = store.audio(project_id)
        return FileResponse(path, media_type={".wav": "audio/wav", ".mp3": "audio/mpeg", ".flac": "audio/flac"}[path.suffix])

    @app.post("/api/projects/{project_id}/analyze-audio")
    def detect_audio_settings(project_id: str):
        from .audio_analysis import analyze_audio
        from .storage import atomic_json
        ensure_idle(project_id)
        result = analyze_audio(store.audio(project_id))
        with store.lock:
            store.project(project_id)
            atomic_json(store.root / 'projects' / project_id / 'audio-analysis.json', result)
        return result

    @app.get("/api/projects/{project_id}/audio-analysis")
    def audio_settings(project_id: str):
        store.project(project_id)
        path = store.root / 'projects' / project_id / 'audio-analysis.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def run_job(job, options, event):
        job_id, project_id = job["id"], job["project_id"]
        try:
            if event.is_set():
                return
            from .transcription import transcribe
            from .notation import validate_score
            store.update_job(job_id, "running", "decoding", "Đang đọc audio")
            work_dir = store.root / "projects" / project_id / "runs" / job_id
            work_dir.mkdir(parents=True, exist_ok=True)

            def progress(stage, message):
                store.update_job(job_id, "running", stage, message)

            score = transcribe(store.audio(project_id), options, work_dir, progress, event.is_set)
            if event.is_set():
                raise InterruptedError("Đã hủy phân tích")
            score["title"] = store.project(project_id)["title"]
            attachment = store.lyric_input(project_id)
            if attachment:
                from .lyrics import parse_and_align
                aligned = parse_and_align(attachment["content"], attachment["filename"], score, attachment["offset_seconds"])
                score["lyrics"] = aligned["lyrics"]
                score["lyric_source"] = aligned["lyric_source"]
                score["diagnostics"].extend(aligned["warnings"])
            score["revision"] = 0
            score = ScoreDocument.model_validate(score).model_dump()
            warnings = validate_score(score)
            score["diagnostics"] = list(dict.fromkeys(score["diagnostics"] + warnings))[:200]
            store.save_score(project_id, score, inference_job=job_id)
        except InterruptedError:
            store.update_job(job_id, "cancelled", "cancelled", "Đã hủy phân tích")
        except Exception as exc:
            LOGGER.exception("Transcription job failed: %s", job_id)
            store.update_job(job_id, "failed", "failed", "Phân tích chưa hoàn thành", str(exc)[:2000])

    @app.post("/api/projects/{project_id}/analyze", status_code=202)
    def analyze(project_id: str, body: AnalyzeRequest, request: Request):
        from .transcription import engine_status
        from .notation import validate_score
        # Validate musical options before allocating a long-running job.
        validate_score({**ScoreDocument(title="Validation").model_dump(), "tempo": body.tempo, "meter": body.meter, "key": body.key})
        engine = next((model for model in engine_status() if model["id"] == body.engine), None)
        if not engine or not engine["available"]:
            raise HTTPException(409, (engine or {}).get("reason") or "Model chưa sẵn sàng.")
        options = body.model_dump()
        client_ip = get_client_ip(request)
        return queue_mgr.enqueue(project_id, options, client_ip, run_job)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        return store.job(job_id)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        return queue_mgr.cancel(job_id)

    @app.get("/api/queue/status")
    def queue_status(request: Request):
        client_ip = get_client_ip(request)
        return queue_mgr.get_status(client_ip)

    @app.get("/api/projects/{project_id}/score")
    def get_score(project_id: str, revision: int | None = Query(default=None, ge=1)):
        # Supply new optional fields without rewriting immutable legacy revisions.
        return ScoreDocument.model_validate(store.score(project_id, revision)).model_dump()

    @app.post("/api/projects/{project_id}/lyrics")
    async def import_lyrics(project_id: str, file: UploadFile = File(...),
                            expected_revision: int = Form(..., ge=1),
                            offset_seconds: float = Form(default=0, ge=-600, le=600)):
        from .lyrics import parse_and_align
        from .notation import validate_score
        try:
            filename = PureWindowsPath(file.filename or "").name
            if Path(filename).suffix.lower() not in {".srt", ".lrc"}:
                raise HTTPException(415, "Chọn tệp lời hát SRT hoặc LRC.")
            project = store.project(project_id)
            if project["score_revision"] is None:
                raise HTTPException(409, "Phân tích audio để tạo nốt nhạc trước khi nhập lời hát.")
            if project["score_revision"] != expected_revision:
                raise ConflictError("Bản nhạc đã thay đổi. Hãy tải lại trước khi nhập lời hát.")
            if project["latest_job"] and project["latest_job"]["status"] in {"queued", "running"}:
                raise HTTPException(409, "Chờ phân tích audio hoàn tất trước khi nhập lời hát.")
            payload = await file.read(1024 * 1024 + 1)
            if len(payload) > 1024 * 1024:
                raise HTTPException(413, "Tệp lời hát vượt giới hạn 1 MB.")
            score = ScoreDocument.model_validate(store.score(project_id, expected_revision)).model_dump()
            result = await run_in_threadpool(parse_and_align, payload, filename[:255], score, offset_seconds)
            score["lyrics"] = result["lyrics"]
            score["lyric_source"] = result["lyric_source"]
            score["review_status"] = "needs_review"
            score = ScoreDocument.model_validate(score).model_dump()
            retained = [message for message in score["diagnostics"] if not message.startswith("Lời hát:")]
            score["diagnostics"] = list(dict.fromkeys(retained + result["warnings"] + validate_score(score)))[:200]
            return store.save_score(project_id, score, expected_revision=expected_revision)
        finally:
            await file.close()

    @app.post("/api/projects/{project_id}/lyrics-source")
    async def stage_lyrics(project_id: str, file: UploadFile = File(...),
                           offset_seconds: float = Form(default=0, ge=-600, le=600)):
        from .lyrics import parse_and_align
        try:
            store.project(project_id)
            filename = PureWindowsPath(file.filename or "").name
            if Path(filename).suffix.lower() not in {".srt", ".lrc"}:
                raise HTTPException(415, "Chọn tệp SRT hoặc LRC.")
            content = await file.read(1024 * 1024 + 1)
            if len(content) > 1024 * 1024:
                raise HTTPException(413, "Tệp lời hát vượt giới hạn 1 MB.")
            parsed = await run_in_threadpool(parse_and_align, content, filename, {"tempo": 100, "notes": []}, offset_seconds)
            return store.stage_lyrics(project_id, content, parsed["lyric_source"])
        finally:
            await file.close()

    @app.delete("/api/projects/{project_id}/lyrics")
    def clear_lyrics(project_id: str, body: ReviewRequest):
        with store.lock:
            ensure_idle(project_id)
            score = ScoreDocument.model_validate(store.score(project_id)).model_dump()
            score.update(lyrics=[], lyric_source=None, review_status='needs_review')
            score['diagnostics'] = [m for m in score['diagnostics'] if not m.startswith('Lời hát:')]
            saved = store.save_score(project_id, score, expected_revision=body.expected_revision)
            with store.connect() as db:
                db.execute('DELETE FROM lyric_inputs WHERE project_id=?', (project_id,))
            return saved

    @app.put("/api/projects/{project_id}/score")
    def save_score(project_id: str, body: SaveScoreRequest):
        from .notation import validate_score
        score = body.score.model_dump()
        score["review_status"] = "needs_review"
        warnings = validate_score(score)
        retained = [message for message in score["diagnostics"] if not message.startswith("Lời hát:")]
        score["diagnostics"] = list(dict.fromkeys(retained + warnings))[:200]
        return store.save_score(project_id, score, expected_revision=body.expected_revision)

    def ensure_idle(project_id):
        project = store.project(project_id)
        if project["latest_job"] and project["latest_job"]["status"] in {"queued", "running"}:
            raise HTTPException(409, "Đang phân tích. Chờ hoàn tất rồi kiểm tra và xuất file.")
        return project

    @app.post("/api/projects/{project_id}/review")
    def review(project_id: str, body: ReviewRequest):
        from .notation import validate_score
        with store.lock:
            ensure_idle(project_id)
            score = ScoreDocument.model_validate(store.score(project_id)).model_dump()
            validate_score(score)
            score["review_status"] = "reviewed"
            return store.save_score(project_id, score, expected_revision=body.expected_revision)

    def downloadable_score(project_id, revision):
        project = ensure_idle(project_id)
        score = store.score(project_id, revision)
        if project["score_revision"] != revision or score["review_status"] != "reviewed":
            raise HTTPException(409, "Xác nhận kiểm tra phiên bản hiện tại trước khi tải file.")
        return score

    @app.get("/api/projects/{project_id}/preview")
    def preview(project_id: str, revision: int = Query(..., ge=1)):
        from .notation import export_musicxml, fix_overlaps
        # Review needs notation before downloads are unlocked. No artifact is
        # created; this in-app preview is separate from downloadable exports.
        score = store.score(project_id, revision)
        with tempfile.TemporaryDirectory(prefix="sheet-preview-") as folder:
            path = Path(folder) / "preview.musicxml"
            try:
                export_musicxml(score, path)
            except ValueError as exc:
                if "chồng lấn" in str(exc):
                    export_musicxml(fix_overlaps(score), path)
                else:
                    raise
            return Response(path.read_bytes(), media_type="application/vnd.recordare.musicxml+xml",
                            headers={"Content-Disposition": "inline"})

    @app.post("/api/projects/{project_id}/preview-draft")
    def preview_draft(project_id: str, body: ScoreDocument):
        from .notation import export_musicxml, fix_overlaps
        store.project(project_id)
        with tempfile.TemporaryDirectory(prefix='sheet-draft-') as folder:
            path = Path(folder) / 'preview.musicxml'
            score = body.model_dump()
            try:
                export_musicxml(score, path)
            except ValueError as exc:
                if 'chồng lấn' not in str(exc): raise
                export_musicxml(fix_overlaps(score), path)
            return Response(path.read_bytes(), media_type='application/vnd.recordare.musicxml+xml')

    @app.post("/api/projects/{project_id}/fix-overlaps")
    def fix_project_overlaps(project_id: str, body: ReviewRequest):
        from .notation import fix_overlaps
        with store.lock:
            ensure_idle(project_id)
            score = store.score(project_id)
            fixed_score = ScoreDocument.model_validate(fix_overlaps(score)).model_dump()
            return store.save_score(project_id, fixed_score, expected_revision=body.expected_revision)

    @app.post("/api/projects/{project_id}/activate-score")
    def activate_score(project_id: str, body: ActivateScoreRequest):
        return store.activate_score(project_id, body.expected_revision, body.revision)

    @app.post("/api/projects/{project_id}/transpose")
    def transpose(project_id: str, body: TransposeRequest):
        from .notation import transpose_score
        score = store.score(project_id)
        score = ScoreDocument.model_validate(transpose_score(score, body.semitones)).model_dump()
        return store.save_score(project_id, score, expected_revision=body.expected_revision)

    @app.get("/api/projects/{project_id}/editor")
    def editor_document(project_id: str, revision: int = Query(..., ge=1)):
        from .notation import export_musicxml
        with store.lock:
            score = downloadable_score(project_id, revision)
            path = store.root / "projects" / project_id / "editor" / str(revision) / "current.json"
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
            with tempfile.TemporaryDirectory(prefix="sheet-editor-") as folder:
                xml_path = Path(folder) / "score.musicxml"
                export_musicxml(score, xml_path)
                return {"base_revision": revision, "version": 0, "musicxml": xml_path.read_text(encoding="utf-8")}

    @app.put("/api/projects/{project_id}/editor")
    def save_editor_document(project_id: str, body: SaveEditorRequest):
        import xml.etree.ElementTree as ET
        # No entity expansion, local-file references, or non-score payloads.
        if len(body.musicxml.encode("utf-8")) > 10_000_000 or "<!ENTITY" in body.musicxml.upper():
            raise HTTPException(422, "MusicXML không hợp lệ hoặc vượt quá 10 MB.")
        try:
            xml = ET.fromstring(body.musicxml)
        except ET.ParseError as exc:
            raise HTTPException(422, "MusicXML không hợp lệ.") from exc
        if xml.tag != "score-partwise" or xml.find("part/measure") is None:
            raise HTTPException(422, "Cần MusicXML score-partwise có ô nhịp.")
        with store.lock:
            downloadable_score(project_id, body.expected_revision)
            directory = store.root / "projects" / project_id / "editor" / str(body.expected_revision)
            path = directory / "current.json"
            current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"version": 0}
            if current["version"] != body.expected_version:
                raise HTTPException(409, "Editor đã được lưu ở cửa sổ khác. Tải xuống bản đang sửa trước khi tải lại.")
            result = {"base_revision": body.expected_revision, "version": current["version"] + 1, "musicxml": body.musicxml}
            # Preserve full notation without flattening it into the single-melody schema.
            atomic_json(directory / f"v{result['version']}.json", result)
            atomic_json(path, result)
            return result

    @app.post("/api/projects/{project_id}/exports", status_code=201)
    def export(project_id: str, body: ExportRequest):
        from .notation import export_abc, export_midi, export_musicxml
        score = downloadable_score(project_id, body.revision)
        directory = store.root / "projects" / project_id / "exports" / str(body.revision)
        directory.mkdir(parents=True, exist_ok=True)
        # PDF is engraved in the browser from an explicitly prepared MusicXML
        # artifact. The source keeps the same revision/review/download gates.
        extension = {"musicxml": "musicxml", "midi": "mid", "pdf": "musicxml", "abc": "abc"}[body.format]
        path = directory / f"{uuid.uuid4().hex}.{extension}"
        options = {
            "accompaniment": body.accompaniment,
            "include_chords": body.include_chords,
            "include_lyrics": body.include_lyrics,
            "scope": body.scope,
            "bar_start": body.bar_start,
            "bar_end": body.bar_end,
            "custom_title": body.custom_title,
        }
        try:
            if body.format in {"musicxml", "pdf"}:
                export_musicxml(score, path, options=options)
            elif body.format == "midi":
                export_midi(score, path, accompaniment=body.accompaniment, options=options)
            elif body.format == "abc":
                export_abc(score, path, options=options)
            if not path.is_file() or not path.stat().st_size:
                raise RuntimeError("Công cụ xuất file không tạo được kết quả.")
            filename = "score.abc" if body.format == "abc" else f"lead-sheet-r{body.revision}.{extension}"
            artifact = store.add_artifact(project_id, body.revision, path, filename)
            if body.format == "pdf":
                return {"filename": f"lead-sheet-r{body.revision}.pdf", "source": artifact}
            return artifact
        except HTTPException:
            path.unlink(missing_ok=True)
            raise
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            path.unlink(missing_ok=True)
            raise HTTPException(422, f"Chưa xuất được file: {str(exc)[:1000]}") from exc


    @app.get("/api/artifacts/{artifact_id}")
    def artifact(artifact_id: str):
        project_id, revision = store.artifact_revision(artifact_id)
        downloadable_score(project_id, revision)
        path, filename = store.artifact(artifact_id)
        return FileResponse(path, filename=filename)

    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    else:
        @app.get("/")
        def frontend_not_built():
            return {"message": "Frontend chưa build. Chạy scripts/setup.ps1 rồi scripts/start.ps1.", "docs": "/docs"}

    return app


app = create_app()
