"""Timed lyric imports must preserve edits/revisions and reach real exports."""
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.schemas import ScoreDocument


@pytest.fixture
def lyrics_client(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.gpu_name", lambda: None)
    app = create_app(tmp_path / "data")
    store = app.state.store
    audio = store.root / "fixture.wav"
    audio.write_bytes(b"test fixture; this suite does not decode audio")
    store.create_project("lyrics-test", "Lời thử nghiệm", "fixture.wav", audio, "test", 4.8)
    score = ScoreDocument(title="Lời thử nghiệm", tempo=100, review_status="reviewed").model_dump()
    score["notes"] = [{"id": f"n{i}", "pitch": pitch, "start": str(i), "duration": "1",
                       "velocity": 80, "source_start": i * .6, "source_end": (i + 1) * .6}
                      for i, pitch in enumerate([60, 62, 64, 65, 67, 69, 71, 72])]
    # Existing projects predate the optional lyric fields.
    score.pop("lyrics")
    score.pop("lyric_source")
    store.save_score("lyrics-test", score)
    with TestClient(app) as client:
        client.get("/api/health")
        yield client


def import_file(client, name, content, revision=1, offset=0):
    return client.post("/api/projects/lyrics-test/lyrics", files={"file": (name, content)},
                       data={"expected_revision": revision, "offset_seconds": offset})


@pytest.mark.parametrize("filename,payload", [
    ("lời.srt", "1\n00:00:00,000 --> 00:00:02,400\nMây bay qua trời\n\n2\n00:00:02,400 --> 00:00:04,800\nNắng lên bên đồi\n"),
    ("lời.lrc", "[00:00.00]Mây bay qua trời\n[00:02.40]Nắng lên bên đồi\n[00:04.80]\n"),
    ("meta.lrc", "[TI : Title]\n[AR:Artist]\n[Verse 1]\n[00:00.00][Chorus]Mây bay qua trời[by:Editor]\n[00:02.40][Bridge]Nắng lên bên đồi\n[00:04.80][Outro]"),
    ("meta.srt", "[ti:Title]\n\n1\n00:00:00,000 --> 00:00:02,400\n[Verse 1]\nMây bay qua trời\n\n2\n00:00:02,400 --> 00:00:04,800\n[Chorus]Nắng lên bên đồi[by:Editor]"),
])
def test_import_lyrics_revision_edit_transpose_and_xml(lyrics_client, filename, payload):
    client = lyrics_client
    before = client.get("/api/projects/lyrics-test/score").json()
    assert before["lyrics"] == [] and before["lyric_source"] is None
    response = import_file(client, filename, payload.encode("utf-8"))
    assert response.status_code == 200, response.text
    score = response.json()
    assert score["revision"] == 2 and score["review_status"] == "needs_review"
    assert score["notes"] == before["notes"]
    assert [token["text"] for token in score["lyrics"]] == "Mây bay qua trời Nắng lên bên đồi".split()
    assert [token["note_id"] for token in score["lyrics"]] == [f"n{i}" for i in range(8)]
    assert client.get("/api/projects/lyrics-test/score?revision=1").json()["lyrics"] == []
    assert import_file(client, filename, payload.encode("utf-8")).status_code == 409

    score["lyrics"][0]["text"] = "Gió & mây"
    saved = client.put("/api/projects/lyrics-test/score", json={"expected_revision": 2, "score": score})
    assert saved.status_code == 200, saved.text
    transpose = client.post("/api/projects/lyrics-test/transpose", json={"expected_revision": 3, "semitones": 2})
    assert transpose.status_code == 200
    assert transpose.json()["lyrics"] == saved.json()["lyrics"]
    approved = client.post("/api/projects/lyrics-test/review", json={"expected_revision": 4})
    assert approved.status_code == 200
    export = client.post("/api/projects/lyrics-test/exports", json={"revision": approved.json()["revision"], "format": "musicxml"})
    assert export.status_code == 201, export.text
    xml = client.get(export.json()["url"]).content
    assert [element.text for element in ET.fromstring(xml).findall(".//lyric/text")] == ["Gió & mây", *"bay qua trời Nắng lên bên đồi".split()]


@pytest.mark.parametrize("filename,payload,status", [
    ("bad.txt", b"[00:00.00]word", 415),
    ("empty.lrc", b"", 422),
    ("bad.srt", b"1\nnot a timestamp\nwords", 422),
    ("large.lrc", b"x" * (1024 * 1024 + 1), 413),
    ("bad.lrc", b"\xff\xff[00:00.00]words", 422),
], ids=["extension", "empty", "malformed", "too-large", "encoding"])
def test_invalid_import_preserves_current_score(lyrics_client, filename, payload, status):
    response = import_file(lyrics_client, filename, payload)
    assert response.status_code == status, response.text
    assert lyrics_client.get("/api/projects/lyrics-test/score").json()["revision"] == 1


def test_alignment_overflow_and_binding_validation(lyrics_client):
    client = lyrics_client
    response = import_file(client, "overflow.srt", "1\n00:00:00,000 --> 00:00:00,500\nMây bay qua trời\n".encode())
    assert response.status_code == 200, response.text
    score = response.json()
    assert len(score["lyrics"]) == 4
    assert sum(token["note_id"] is None for token in score["lyrics"]) == 3
    assert any(message.startswith("Lời hát:") for message in score["diagnostics"])
    score["lyrics"][1]["note_id"] = "missing-note"
    result = client.put("/api/projects/lyrics-test/score", json={"expected_revision": 2, "score": score})
    assert result.status_code == 422
    assert client.get("/api/projects/lyrics-test/score").json()["revision"] == 2
    score["lyrics"][1]["note_id"] = score["lyrics"][0]["note_id"]
    assert client.put("/api/projects/lyrics-test/score", json={"expected_revision": 2, "score": score}).status_code == 422


def test_import_offset_and_session_guard(lyrics_client):
    client = lyrics_client
    response = import_file(client, "offset.lrc", b"[00:00.00]Cloud\n[00:00.30]\n", offset=.6)
    assert response.status_code == 200, response.text
    assert response.json()["lyrics"][0]["note_id"] == "n1"
    assert response.json()["lyric_source"]["offset_seconds"] == .6
    client.cookies.clear()
    assert import_file(client, "offset.lrc", b"[00:00.00]Cloud").status_code == 403


def test_review_gate_cannot_be_bypassed_by_save_or_old_download(lyrics_client):
    client = lyrics_client
    score = client.get("/api/projects/lyrics-test/score").json()
    score["title"] = "Changed"
    score["review_status"] = "reviewed"
    result = client.put("/api/projects/lyrics-test/score", json={"expected_revision": 1, "score": score})
    assert result.json()["review_status"] == "needs_review"
    for format_name in ["musicxml", "midi", "pdf"]:
        assert client.post("/api/projects/lyrics-test/exports", json={"revision": 2, "format": format_name}).status_code == 409
    preview = client.get("/api/projects/lyrics-test/preview?revision=2")
    assert preview.status_code == 200
    assert ET.fromstring(preview.content).tag == "score-partwise"
    assert client.post("/api/projects/lyrics-test/review", json={"expected_revision": 1}).status_code == 409
    assert client.post("/api/projects/lyrics-test/review", json={"expected_revision": 2}).json()["revision"] == 3
    artifact = client.post("/api/projects/lyrics-test/exports", json={"revision": 3, "format": "midi"}).json()
    assert client.get(artifact["url"]).status_code == 200
    score = client.get("/api/projects/lyrics-test/score").json()
    score["notes"][0]["pitch"] += 1
    client.put("/api/projects/lyrics-test/score", json={"expected_revision": 3, "score": score}).raise_for_status()
    assert client.get(artifact["url"]).status_code == 409
    assert client.post("/api/projects/lyrics-test/exports", json={"revision": 3, "format": "midi"}).status_code == 409


def test_active_analysis_blocks_review_and_download(lyrics_client):
    client = lyrics_client
    job = client.app.state.store.create_job("lyrics-test", {"engine": "test"})
    assert client.post("/api/projects/lyrics-test/review", json={"expected_revision": 1}).status_code == 409
    assert client.post("/api/projects/lyrics-test/exports", json={"revision": 1, "format": "midi"}).status_code == 409
    client.app.state.store.update_job(job["id"], "cancelled", "cancelled", "Test complete")
