from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.storage import ConflictError, Store


def sample_score():
    return {"revision": 0, "title": "Test", "review_status": "needs_review", "notes": []}


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path)
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fixture")
    result.create_project("one", "Test", "original.wav", audio, "abc", 2)
    return result


def test_immutable_revisions_and_optimistic_concurrency(store):
    first = store.save_score("one", sample_score())
    assert first["revision"] == 1
    edited = {**first, "title": "Edited"}

    def update():
        try:
            return store.save_score("one", edited, expected_revision=1)["revision"]
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(lambda _: update(), range(2)))
    assert set(values) == {2, "conflict"}
    assert store.score("one", 1)["title"] == "Test"
    assert store.score("one")["title"] == "Edited"


def test_rerun_preserves_user_edits_and_requires_activation(store):
    store.save_score("one", {**sample_score(), "title": "User revision"})
    job = store.create_job("one", {"engine": "test"})
    draft = store.save_score("one", {**sample_score(), "title": "AI new"}, inference_job=job["id"])
    assert store.score("one")["title"] == "User revision"
    assert store.project("one")["pending_score_revision"] == draft["revision"]
    activated = store.activate_score("one", 1, draft["revision"])
    assert activated["title"] == "AI new"
    assert store.project("one")["pending_score_revision"] is None


def test_cancel_prevents_late_worker_write(store):
    job = store.create_job("one", {})
    store.update_job(job["id"], "cancelled", "cancelled", "Cancelled")
    with pytest.raises(InterruptedError):
        store.save_score("one", sample_score(), inference_job=job["id"])
    assert store.project("one")["score_revision"] is None


def test_recovery_and_path_confinement(store):
    job = store.create_job("one", {})
    with pytest.raises(ConflictError):
        store.create_job("one", {})
    store.recover_jobs()
    assert store.job(job["id"])["status"] == "failed"
    with pytest.raises(ValueError):
        store.contained("../outside")


def test_delete_and_empty_trash(store):
    store.delete_project("one")
    assert [p["id"] for p in store.projects(deleted=True)] == ["one"]
    assert store.projects(deleted=False) == []
    count = store.empty_trash()
    assert count == 1
    assert store.projects(deleted=True) == []
    with pytest.raises(KeyError):
        store.project("one", include_deleted=True)


def test_cross_platform_path_handling(store):
    score_path = store.root / "projects" / "one" / "scores" / "1.json"
    rel = store.relative(score_path)
    assert "\\" not in rel
    assert "/" in rel

    resolved_posix = store.contained("projects/one/scores/1.json")
    resolved_win = store.contained(r"projects\one\scores\1.json")
    assert resolved_posix == score_path.resolve()
    assert resolved_win == score_path.resolve()


def test_project_history_session_and_ip_isolation(tmp_path):
    store = Store(tmp_path)
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"test")
    store.create_project("user1_proj", "Title 1", "audio1.wav", audio, "hash1", 10, client_ip="192.168.1.10", session_id="sess_user1")
    store.create_project("user2_proj", "Title 2", "audio2.wav", audio, "hash2", 15, client_ip="192.168.1.20", session_id="sess_user2")

    u1_projects = store.projects(client_ip="192.168.1.10", session_id="sess_user1")
    assert len(u1_projects) == 1
    assert u1_projects[0]["id"] == "user1_proj"

    u2_projects = store.projects(client_ip="192.168.1.20", session_id="sess_user2")
    assert len(u2_projects) == 1
    assert u2_projects[0]["id"] == "user2_proj"

    store.delete_project("user1_proj")
    store.delete_project("user2_proj")
    assert len(store.projects(deleted=True, session_id="sess_user1")) == 1
    emptied = store.empty_trash(session_id="sess_user1")
    assert emptied == 1
    assert len(store.projects(deleted=True, session_id="sess_user1")) == 0
    assert len(store.projects(deleted=True, session_id="sess_user2")) == 1

