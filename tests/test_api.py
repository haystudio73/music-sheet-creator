"""Local API integration including actual FFmpeg/DSP -> score -> XML/MIDI."""
import threading
import time
import xml.etree.ElementTree as ET

import mido
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from scripts.make_test_audio import create_fixture


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.gpu_name", lambda: None)
    application = create_app(tmp_path / "data")
    with TestClient(application) as session:
        assert session.get("/api/health").status_code == 200
        yield session


def upload(client, tmp_path):
    path = create_fixture(tmp_path / "scale.wav")
    response = client.post("/api/projects", files={"file": ("Giai điệu thử nghiệm.wav", path.read_bytes(), "audio/wav")}, data={"title": "Thử nghiệm tổng hợp"})
    assert response.status_code == 201, response.text
    return response.json()


def analyze(client, project_id, melody_role="instrumental"):
    response = client.post(f"/api/projects/{project_id}/analyze", json={"engine": "monophonic", "tempo": 100, "meter": [4, 4], "key": "C", "melody_role": melody_role})
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "cancelled"}:
            assert job["status"] == "completed", job
            return job
        time.sleep(.05)
    pytest.fail("DSP job did not finish")


def test_audio_to_score_edit_export_and_rerun(client, tmp_path):
    project = upload(client, tmp_path)
    pid = project["id"]
    assert client.get(f"/api/projects/{pid}/audio").content[:4] == b"RIFF"
    attached = client.post(f"/api/projects/{pid}/lyrics-source", files={"file": ("words.lrc", "[00:00.00]Mây bay qua trời\n[00:02.40]Nắng lên bên đồi\n[00:04.80]".encode())})
    assert attached.status_code == 200, attached.text
    assert attached.json()["lyric_attachment"]["filename"] == "words.lrc"
    analyze(client, pid)
    score = client.get(f"/api/projects/{pid}/score").json()
    assert len(score["lyrics"]) == 8
    assert score["source_engine"] == "monophonic"
    assert [n["pitch"] for n in score["notes"]] == [60, 62, 64, 65, 67, 69, 71, 72]
    assert not score["harmonies"]  # DSP never invents chord predictions.
    score["harmonies"] = [{"id": "manual-c", "root": "C", "quality": "major", "bass": None, "start": "0", "duration": "4", "kind": "chord"}]
    score["title"] = "Bản đã chỉnh"
    score["review_status"] = "reviewed"
    saved = client.put(f"/api/projects/{pid}/score", json={"expected_revision": score["revision"], "score": score})
    assert saved.status_code == 200, saved.text
    revision = saved.json()["revision"]
    assert saved.json()["review_status"] == "needs_review"
    assert client.post(f"/api/projects/{pid}/exports", json={"revision": revision, "format": "midi"}).status_code == 409
    reviewed = client.post(f"/api/projects/{pid}/review", json={"expected_revision": revision})
    assert reviewed.status_code == 200
    revision = reviewed.json()["revision"]
    conflict = client.put(f"/api/projects/{pid}/score", json={"expected_revision": 1, "score": score})
    assert conflict.status_code == 409
    assert client.get(f"/api/projects/{pid}/score?revision=1").json()["harmonies"] == []
    exported = client.post(f"/api/projects/{pid}/exports", json={"revision": revision, "format": "musicxml"})
    assert exported.status_code == 201, exported.text
    xml = client.get(exported.json()["url"]).content
    root = ET.fromstring(xml)
    assert root.tag == "score-partwise"
    assert root.find(".//harmony/root/root-step").text == "C"
    exported_midi = client.post(f"/api/projects/{pid}/exports", json={"revision": revision, "format": "midi", "accompaniment": True})
    assert exported_midi.status_code == 201, exported_midi.text
    midi_path = tmp_path / "roundtrip.mid"
    midi_path.write_bytes(client.get(exported_midi.json()["url"]).content)
    assert len(mido.MidiFile(midi_path).tracks) >= 2
    exported_abc = client.post(f"/api/projects/{pid}/exports", json={"revision": revision, "format": "abc"})
    assert exported_abc.status_code == 201, exported_abc.text
    assert exported_abc.json()["filename"] == "score.abc"
    abc_content = client.get(exported_abc.json()["url"]).text
    assert "X: 1" in abc_content
    assert "T: Bản đã chỉnh" in abc_content
    assert '"C"' in abc_content
    exported_abc_range = client.post(
        f"/api/projects/{pid}/exports",
        json={"revision": revision, "format": "abc", "scope": "range", "bar_start": 1, "bar_end": 1, "include_chords": False},
    )
    assert exported_abc_range.status_code == 201, exported_abc_range.text
    abc_range_content = client.get(exported_abc_range.json()["url"]).text
    assert '"C"' not in abc_range_content
    analyze(client, pid, melody_role="vocal")
    current = client.get(f"/api/projects/{pid}").json()
    assert current["score_revision"] == revision
    assert current["pending_score_revision"] > revision
    assert client.get(f"/api/projects/{pid}/score").json()["review_status"] == "reviewed"
    assert client.get(f"/api/projects/{pid}/score").json()["melody_role"] == "instrumental"
    assert client.get(f"/api/projects/{pid}/score?revision={current['pending_score_revision']}").json()["melody_role"] == "vocal"
    activate = client.post(f"/api/projects/{pid}/activate-score", json={"expected_revision": revision, "revision": current["pending_score_revision"]})
    assert activate.status_code == 200
    assert activate.json()["harmonies"] == []
    assert activate.json()["melody_role"] == "vocal"
    assert activate.json()["review_status"] == "needs_review"


def test_delete_and_restore_preserve_project_files_and_block_access(client, tmp_path):
    from backend.schemas import ScoreDocument
    pid = upload(client, tmp_path)["id"]
    store = client.app.state.store
    original = store.audio(pid).read_bytes()
    score = store.save_score(pid, ScoreDocument(title="Keep revisions", review_status="reviewed").model_dump())
    artifact = client.post(f"/api/projects/{pid}/exports", json={"revision": score["revision"], "format": "musicxml"}).json()
    xml = client.get(artifact["url"]).content
    assert client.delete(f"/api/projects/{pid}").status_code == 200
    assert client.delete(f"/api/projects/{pid}").status_code == 200  # Idempotent.
    assert client.get("/api/projects").json() == []
    assert client.get("/api/projects?deleted=true").json()[0]["id"] == pid
    for suffix in ("", "/audio", "/score", f"/preview?revision={score['revision']}"):
        assert client.get(f"/api/projects/{pid}{suffix}").status_code == 404
    assert client.get(artifact["url"]).status_code == 404
    assert client.post(f"/api/projects/{pid}/analyze", json={"engine": "monophonic"}).status_code == 404
    assert client.put(f"/api/projects/{pid}/score", json={"expected_revision": score["revision"], "score": score}).status_code == 404
    assert client.post(f"/api/projects/{pid}/restore").status_code == 200
    assert client.get("/api/projects?deleted=true").json() == []
    assert client.get(f"/api/projects/{pid}/audio").content == original
    assert client.get(f"/api/projects/{pid}/score").json() == score
    assert client.get(artifact["url"]).content == xml
    assert client.delete("/api/projects/missing").status_code == 404
    assert client.post("/api/projects/missing/restore").status_code == 404
    assert client.delete(f"/api/projects/{pid}").status_code == 200
    assert len(client.get("/api/projects?deleted=true").json()) == 1
    empty_resp = client.post("/api/projects/empty-trash")
    assert empty_resp.status_code == 200
    assert empty_resp.json()["emptied"] is True
    assert empty_resp.json()["count"] == 1
    assert client.get("/api/projects?deleted=true").json() == []
    assert not (store.root / "projects" / pid).exists()
    client.cookies.clear()
    assert client.delete(f"/api/projects/{pid}").status_code == 403
    assert client.post(f"/api/projects/{pid}/restore").status_code == 403


def test_delete_blocked_for_active_jobs(client, tmp_path):
    pid = upload(client, tmp_path)["id"]
    store = client.app.state.store
    job = store.create_job(pid, {})
    assert client.delete(f"/api/projects/{pid}").status_code == 409
    store.update_job(job["id"], "running", "test", "Testing")
    assert client.delete(f"/api/projects/{pid}").status_code == 409
    assert client.get("/api/projects?deleted=true").json() == []
    store.update_job(job["id"], "cancelled", "test", "Cancelled")
    assert client.delete(f"/api/projects/{pid}").status_code == 200


def test_security_and_invalid_input(client, tmp_path):
    assert client.post("/api/projects", files={"file": ("evil.html", b"<script></script>")}).status_code == 415
    assert client.post("/api/projects", files={"file": ("fake.wav", b"not audio")}).status_code == 422
    assert client.get("/api/projects", headers={"Origin": "https://attacker.example"}).status_code == 403
    assert client.get("/api/projects", headers={"Host": "attacker.example"}).status_code == 400
    client.cookies.clear()
    assert client.post("/api/projects", files={"file": ("test.wav", b"test")}).status_code == 403


def test_cancel_while_worker_running(client, tmp_path, monkeypatch):
    started = threading.Event()

    def slow_transcription(path, options, work_dir, progress, cancelled):
        started.set()
        for _ in range(100):
            if cancelled():
                raise InterruptedError("cancelled")
            time.sleep(.01)
        raise AssertionError("Cancellation was not delivered")

    monkeypatch.setattr("backend.transcription.transcribe", slow_transcription)
    pid = upload(client, tmp_path)["id"]
    job = client.post(f"/api/projects/{pid}/analyze", json={"engine": "monophonic"}).json()
    assert started.wait(2)
    cancelled = client.post(f"/api/jobs/{job['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.get(f"/api/projects/{pid}/score").status_code == 404


def test_invalid_score_update_does_not_create_revision(client, tmp_path):
    pid = upload(client, tmp_path)["id"]
    analyze(client, pid)
    score = client.get(f"/api/projects/{pid}/score").json()
    score["notes"][0]["duration"] = "0"
    response = client.put(f"/api/projects/{pid}/score", json={"expected_revision": 1, "score": score})
    assert response.status_code == 422
    assert client.get(f"/api/projects/{pid}").json()["score_revision"] == 1


def test_preview_handles_overlaps_and_fix_overlaps_endpoint(client, tmp_path):
    pid = upload(client, tmp_path)["id"]
    analyze(client, pid)
    score = client.get(f"/api/projects/{pid}/score").json()
    # Create an overlap
    score["notes"][1]["start"] = score["notes"][0]["start"]
    saved = client.put(f"/api/projects/{pid}/score", json={"expected_revision": 1, "score": score})
    assert saved.status_code == 200
    rev = saved.json()["revision"]
    # Preview should succeed despite overlap by resolving gracefully
    preview = client.get(f"/api/projects/{pid}/preview?revision={rev}")
    assert preview.status_code == 200
    assert b"<score-partwise" in preview.content

    # Fix overlaps endpoint should resolve notes and return new revision
    fixed = client.post(f"/api/projects/{pid}/fix-overlaps", json={"expected_revision": rev})
    assert fixed.status_code == 200
    fixed_score = fixed.json()
    assert fixed_score["revision"] == rev + 1
    assert not any("chồng lấn" in d for d in fixed_score["diagnostics"])


def test_update_project_title(client, tmp_path):
    project = upload(client, tmp_path)
    pid = project["id"]
    assert project["title"] == "Thử nghiệm tổng hợp"

    # Update title before score analysis
    res = client.patch(f"/api/projects/{pid}", json={"title": "  Bình minh trên đồi  "})
    assert res.status_code == 200
    assert res.json()["title"] == "Bình minh trên đồi"
    assert client.get(f"/api/projects/{pid}").json()["title"] == "Bình minh trên đồi"

    # Validation: empty and too long
    assert client.patch(f"/api/projects/{pid}", json={"title": "   "}).status_code == 422
    assert client.patch(f"/api/projects/{pid}", json={"title": "A" * 201}).status_code == 422

    # Analyze to create score
    analyze(client, pid)
    score = client.get(f"/api/projects/{pid}/score").json()
    assert score["title"] == "Bình minh trên đồi"

    # Update title after score exists
    res_after = client.patch(f"/api/projects/{pid}", json={"title": "Hoàng hôn buông xuống"})
    assert res_after.status_code == 200
    assert res_after.json()["title"] == "Hoàng hôn buông xuống"
    updated_score = client.get(f"/api/projects/{pid}/score").json()
    assert updated_score["title"] == "Hoàng hôn buông xuống"
    assert updated_score["revision"] > score["revision"]


