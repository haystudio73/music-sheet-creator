"""SQLite metadata + immutable JSON revisions and contained artifact paths."""
import json
import os
import shutil
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


class ConflictError(Exception):
    pass


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.database = self.root / "studio.sqlite3"
        with self.connect() as db:
            try:
                db.execute("PRAGMA journal_mode=WAL;")
            except sqlite3.OperationalError:
                pass
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                  id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL, audio_name TEXT NOT NULL, audio_path TEXT NOT NULL,
                  audio_hash TEXT NOT NULL, duration REAL NOT NULL, status TEXT NOT NULL,
                  score_revision INTEGER, pending_score_revision INTEGER,
                  client_ip TEXT, session_id TEXT);
                CREATE TABLE IF NOT EXISTS scores (
                  project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL,
                  path TEXT NOT NULL, PRIMARY KEY(project_id,revision));
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                  status TEXT NOT NULL, stage TEXT NOT NULL, message TEXT NOT NULL,
                  error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  options TEXT NOT NULL, base_revision INTEGER, client_ip TEXT);
                CREATE TABLE IF NOT EXISTS artifacts (
                  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                  revision INTEGER NOT NULL, path TEXT NOT NULL, filename TEXT NOT NULL,
                  created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS lyric_inputs (
                  project_id TEXT PRIMARY KEY REFERENCES projects(id),
                  filename TEXT NOT NULL, content BLOB NOT NULL,
                  offset_seconds REAL NOT NULL, cue_count INTEGER NOT NULL,
                  format TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS deleted_projects (
                  project_id TEXT PRIMARY KEY REFERENCES projects(id), deleted_at TEXT NOT NULL);
                PRAGMA user_version=1;
            """)
            cursor = db.execute("PRAGMA table_info(jobs)")
            columns = [row[1] for row in cursor.fetchall()]
            if "client_ip" not in columns:
                db.execute("ALTER TABLE jobs ADD COLUMN client_ip TEXT")
            proj_cursor = db.execute("PRAGMA table_info(projects)")
            proj_columns = [row[1] for row in proj_cursor.fetchall()]
            if "client_ip" not in proj_columns:
                db.execute("ALTER TABLE projects ADD COLUMN client_ip TEXT")
            if "session_id" not in proj_columns:
                db.execute("ALTER TABLE projects ADD COLUMN session_id TEXT")
            db.execute("UPDATE projects SET audio_path = replace(audio_path, '\\', '/') WHERE instr(audio_path, '\\') > 0")
            db.execute("UPDATE scores SET path = replace(path, '\\', '/') WHERE instr(path, '\\') > 0")
            db.execute("UPDATE artifacts SET path = replace(path, '\\', '/') WHERE instr(path, '\\') > 0")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def contained(self, relative: str) -> Path:
        normalized = str(relative).replace("\\", "/")
        path = (self.root / normalized).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Đường dẫn nằm ngoài thư mục dự án")
        return path

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def create_project(self, project_id, title, audio_name, path, audio_hash, duration, client_ip=None, session_id=None):
        with self.lock, self.connect() as db:
            stamp = now()
            db.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                project_id, title, stamp, stamp, audio_name, self.relative(path),
                audio_hash, duration, "ready", None, None, client_ip, session_id))
        return self.project(project_id)

    @staticmethod
    def require_active(db, project_id):
        if db.execute("SELECT 1 FROM deleted_projects WHERE project_id=?", (project_id,)).fetchone():
            raise KeyError(project_id)

    def project(self, project_id, include_deleted=False):
        with self.connect() as db:
            if not include_deleted:
                self.require_active(db, project_id)
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if row is None:
                raise KeyError(project_id)
            data = dict(row)
            job = db.execute("SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone()
        for key in ("audio_path", "audio_hash", "client_ip", "session_id"):
            data.pop(key, None)
        data["latest_job"] = self.public_job(job) if job else None
        with self.connect() as db:
            attachment = db.execute("SELECT filename,offset_seconds,cue_count,format FROM lyric_inputs WHERE project_id=?", (project_id,)).fetchone()
        data["lyric_attachment"] = dict(attachment) if attachment else None
        return data

    def stage_lyrics(self, project_id, content, metadata):
        with self.lock, self.connect() as db:
            self.require_active(db, project_id)
            project = db.execute("SELECT score_revision FROM projects WHERE id=?", (project_id,)).fetchone()
            if project is None:
                raise KeyError(project_id)
            active = db.execute("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','running')", (project_id,)).fetchone()
            if project[0] is not None or active:
                raise ConflictError("Chỉ đính kèm lời trước khi phân tích. Nếu đã có bản nhạc, dùng tab Lời hát.")
            db.execute("INSERT OR REPLACE INTO lyric_inputs VALUES (?,?,?,?,?,?)", (
                project_id, metadata["filename"], content, metadata["offset_seconds"], metadata["cue_count"], metadata["format"]))
            db.execute("UPDATE projects SET updated_at=? WHERE id=?", (now(), project_id))
        return self.project(project_id)

    def lyric_input(self, project_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM lyric_inputs WHERE project_id=?", (project_id,)).fetchone()
        return dict(row) if row else None

    def projects(self, deleted=False, client_ip=None, session_id=None):
        with self.lock, self.connect() as db:
            query = """SELECT p.id FROM projects p
                LEFT JOIN deleted_projects d ON d.project_id=p.id
                WHERE (d.project_id IS NOT NULL)=?"""
            params = [deleted]
            if session_id or client_ip:
                query += " AND (p.session_id = ? OR (p.session_id IS NULL AND p.client_ip = ?) OR (p.session_id IS NULL AND p.client_ip IS NULL))"
                params.extend([session_id, client_ip])
            query += " ORDER BY p.updated_at DESC"
            ids = [row[0] for row in db.execute(query, params)]
            return [self.project(project_id, include_deleted=deleted) for project_id in ids]

    def delete_project(self, project_id):
        """Recoverable deletion: keep audio, revisions, jobs and exports intact."""
        with self.lock, self.connect() as db:
            if not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                raise KeyError(project_id)
            if db.execute("SELECT 1 FROM jobs WHERE project_id=? AND status IN ('queued','running')", (project_id,)).fetchone():
                raise ConflictError("Dừng hoặc chờ phân tích hoàn tất trước khi xóa dự án.")
            db.execute("INSERT OR IGNORE INTO deleted_projects VALUES (?,?)", (project_id, now()))

    def restore_project(self, project_id):
        with self.lock, self.connect() as db:
            if not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
                raise KeyError(project_id)
            db.execute("DELETE FROM deleted_projects WHERE project_id=?", (project_id,))
        return self.project(project_id)

    def empty_trash(self, client_ip=None, session_id=None) -> int:
        """Permanently delete all soft-deleted projects from database and disk for current client."""
        with self.lock, self.connect() as db:
            query = """SELECT d.project_id FROM deleted_projects d
                JOIN projects p ON p.id = d.project_id WHERE 1=1"""
            params = []
            if session_id or client_ip:
                query += " AND (p.session_id = ? OR (p.session_id IS NULL AND p.client_ip = ?) OR (p.session_id IS NULL AND p.client_ip IS NULL))"
                params.extend([session_id, client_ip])
            project_ids = [row[0] for row in db.execute(query, params)]
            for project_id in project_ids:
                db.execute("DELETE FROM deleted_projects WHERE project_id=?", (project_id,))
                db.execute("DELETE FROM artifacts WHERE project_id=?", (project_id,))
                db.execute("DELETE FROM lyric_inputs WHERE project_id=?", (project_id,))
                db.execute("DELETE FROM scores WHERE project_id=?", (project_id,))
                db.execute("DELETE FROM jobs WHERE project_id=?", (project_id,))
                db.execute("DELETE FROM projects WHERE id=?", (project_id,))
                project_dir = self.root / "projects" / project_id
                if project_dir.exists():
                    shutil.rmtree(project_dir, ignore_errors=True)
            return len(project_ids)

    def audio(self, project_id):
        with self.connect() as db:
            self.require_active(db, project_id)
            row = db.execute("SELECT audio_path FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise KeyError(project_id)
        return self.contained(row[0])

    @staticmethod
    def public_job(row):
        data = dict(row)
        data.pop("options", None)
        data.pop("base_revision", None)
        return data

    def job(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        job_data = self.public_job(row)
        if job_data["status"] == "queued":
            pos, total = self.get_queue_position(job_id)
            job_data["queue_position"] = pos
            job_data["queue_length"] = total
            job_data["estimated_wait_seconds"] = (pos or 1) * 90
            job_data["message"] = f"Đang chờ trong hàng đợi (vị trí #{pos}/{total}). Vui lòng chờ worker trống..."
        return job_data

    def get_queue_position(self, job_id: str) -> tuple[int | None, int]:
        with self.connect() as db:
            row = db.execute("SELECT status, created_at FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            status, created_at = row["status"], row["created_at"]
            total_queued = db.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0]
            if status != "queued":
                return None, total_queued
            pos = db.execute("SELECT COUNT(*) FROM jobs WHERE status='queued' AND created_at <= ?", (created_at,)).fetchone()[0]
            return max(1, pos), total_queued

    def get_active_job_for_ip(self, client_ip: str | None):
        if not client_ip:
            return None
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE client_ip=? AND status IN ('queued','running') ORDER BY created_at ASC LIMIT 1", (client_ip,)).fetchone()
        return self.public_job(row) if row else None

    def count_active_and_queued_jobs(self) -> tuple[int, int]:
        with self.connect() as db:
            running = db.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0]
            queued = db.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0]
        return running, queued

    def create_job(self, project_id, options, client_ip=None):
        with self.lock, self.connect() as db:
            self.require_active(db, project_id)
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project:
                raise KeyError(project_id)
            active = db.execute("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','running')", (project_id,)).fetchone()
            if active:
                raise ConflictError("Dự án đang có tác vụ phân tích")
            job_id, stamp = uuid.uuid4().hex, now()
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                job_id, project_id, "queued", "queued", "Đang chờ xử lý", None,
                stamp, stamp, json.dumps(options), project["score_revision"], client_ip))
            db.execute("UPDATE projects SET status='analyzing',updated_at=? WHERE id=?", (stamp, project_id))
        return self.job(job_id)

    def update_job(self, job_id, status, stage, message, error=None):
        with self.lock, self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            if row["status"] in ("cancelled", "completed", "failed"):
                return
            db.execute("UPDATE jobs SET status=?,stage=?,message=?,error=?,updated_at=? WHERE id=?", (status, stage, message, error, now(), job_id))
            if status in ("failed", "cancelled"):
                project = db.execute("SELECT * FROM projects WHERE id=?", (row["project_id"],)).fetchone()
                next_status = "draft" if project["score_revision"] else ("failed" if status == "failed" else "ready")
                if project["score_revision"]:
                    score = self.score(row["project_id"], project["score_revision"])
                    next_status = "reviewed" if score["review_status"] == "reviewed" else "draft"
                db.execute("UPDATE projects SET status=?,updated_at=? WHERE id=?", (next_status, now(), row["project_id"]))

    def recover_jobs(self):
        with self.connect() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM jobs WHERE status IN ('queued','running')")]
        for job_id in ids:
            self.update_job(job_id, "failed", "interrupted", "Tác vụ bị gián đoạn khi ứng dụng dừng", "Hãy phân tích lại; bản nhạc đã lưu vẫn được giữ.")

    def score(self, project_id, revision=None):
        with self.connect() as db:
            self.require_active(db, project_id)
            project = db.execute("SELECT score_revision FROM projects WHERE id=?", (project_id,)).fetchone()
            if project is None:
                raise KeyError(project_id)
            revision = revision or project[0]
            row = db.execute("SELECT path FROM scores WHERE project_id=? AND revision=?", (project_id, revision)).fetchone()
        if not row:
            raise KeyError("Dự án chưa có bản nhạc")
        file_path = self.contained(row[0])
        if not file_path.is_file():
            raise FileNotFoundError(f"Tệp bản nhạc không tồn tại: {file_path}")
        return json.loads(file_path.read_text(encoding="utf-8"))

    def save_score(self, project_id, score, expected_revision=None, inference_job=None):
        with self.lock, self.connect() as db:
            self.require_active(db, project_id)
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if project is None:
                raise KeyError(project_id)
            if expected_revision is not None and project["score_revision"] != expected_revision:
                raise ConflictError("Bản nhạc đã thay đổi. Hãy tải lại trước khi lưu.")
            if inference_job:
                job = db.execute("SELECT status FROM jobs WHERE id=?", (inference_job,)).fetchone()
                if not job or job[0] == "cancelled":
                    raise InterruptedError("Đã hủy phân tích")
            revision = db.execute("SELECT COALESCE(MAX(revision),0)+1 FROM scores WHERE project_id=?", (project_id,)).fetchone()[0]
            score = {**score, "revision": revision}
            path = self.root / "projects" / project_id / "scores" / f"{revision}.json"
            atomic_json(path, score)
            db.execute("INSERT INTO scores VALUES (?,?,?)", (project_id, revision, self.relative(path)))
            status = "reviewed" if score["review_status"] == "reviewed" else "draft"
            if inference_job and project["score_revision"] is not None:
                old_score = self.score(project_id, project["score_revision"])
                status = "reviewed" if old_score["review_status"] == "reviewed" else "draft"
                db.execute("UPDATE projects SET pending_score_revision=?,updated_at=?,status=? WHERE id=?", (revision, now(), status, project_id))
            else:
                db.execute("UPDATE projects SET score_revision=?,title=?,updated_at=?,status=? WHERE id=?", (revision, score["title"], now(), status, project_id))
            if inference_job:
                db.execute("UPDATE jobs SET status='completed',stage='completed',message=?,updated_at=? WHERE id=?", ("Đã tạo bản nháp mới. Hãy nghe và kiểm tra kết quả.", now(), inference_job))
        return score

    def activate_score(self, project_id, expected_revision, revision):
        with self.lock, self.connect() as db:
            self.require_active(db, project_id)
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project:
                raise KeyError(project_id)
            if project["score_revision"] != expected_revision:
                raise ConflictError("Bản nhạc đã thay đổi. Hãy tải lại.")
            score = self.score(project_id, revision)
            status = "reviewed" if score["review_status"] == "reviewed" else "draft"
            db.execute("UPDATE projects SET score_revision=?,pending_score_revision=NULL,title=?,status=?,updated_at=? WHERE id=?", (revision, score["title"], status, now(), project_id))
        return score

    def add_artifact(self, project_id, revision, path, filename):
        artifact_id = uuid.uuid4().hex
        with self.lock, self.connect() as db:
            self.require_active(db, project_id)
            db.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?)", (artifact_id, project_id, revision, self.relative(path), filename, now()))
        return {"id": artifact_id, "filename": filename, "url": f"/api/artifacts/{artifact_id}"}

    def artifact(self, artifact_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        if not row:
            raise KeyError(artifact_id)
        return self.contained(row["path"]), row["filename"]

    def artifact_revision(self, artifact_id):
        with self.connect() as db:
            row = db.execute("SELECT project_id,revision FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        return row["project_id"], row["revision"]
