"""Tests for FIFO Queue, 1-task-per-IP limit, and backend load management."""
import time
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from scripts.make_test_audio import create_fixture


@pytest.fixture
def test_setup(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.gpu_name", lambda: None)
    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        yield client, tmp_path, app


def upload_sample(client, tmp_path, title="Audio Test"):
    path = create_fixture(tmp_path / f"{title}.wav")
    resp = client.post(
        "/api/projects",
        files={"file": (f"{title}.wav", path.read_bytes(), "audio/wav")},
        data={"title": title}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_queue_status_endpoint(test_setup):
    client, tmp_path, app = test_setup
    res = client.get("/api/queue/status", headers={"X-Forwarded-For": "10.0.0.1"})
    assert res.status_code == 200
    data = res.json()
    assert data["max_workers"] >= 1
    assert data["max_queue"] >= 1
    assert data["client_ip"] == "10.0.0.1"
    assert data["client_can_submit"] is True
    assert data["client_active_job_id"] is None


def test_single_active_job_per_ip_restriction(test_setup):
    client, tmp_path, app = test_setup
    p1 = upload_sample(client, tmp_path, "Song 1")
    p2 = upload_sample(client, tmp_path, "Song 2")

    ip_a = "192.168.1.10"
    ip_b = "192.168.1.20"

    # 1. First request from IP A should succeed
    res1 = client.post(
        f"/api/projects/{p1['id']}/analyze",
        json={"engine": "monophonic", "tempo": 100, "meter": [4, 4], "key": "C", "melody_role": "instrumental"},
        headers={"X-Forwarded-For": ip_a}
    )
    assert res1.status_code == 202
    job1_id = res1.json()["id"]

    # 2. Second request from SAME IP A must be rejected with 429
    res2 = client.post(
        f"/api/projects/{p2['id']}/analyze",
        json={"engine": "monophonic", "tempo": 100, "meter": [4, 4], "key": "C", "melody_role": "instrumental"},
        headers={"X-Forwarded-For": ip_a}
    )
    assert res2.status_code == 429
    err = res2.json()
    assert err.get("code") == "IP_SESSION_ACTIVE"
    assert ip_a in err["detail"]

    # 3. Request from DIFFERENT IP B while IP A is busy should succeed
    res3 = client.post(
        f"/api/projects/{p2['id']}/analyze",
        json={"engine": "monophonic", "tempo": 100, "meter": [4, 4], "key": "C", "melody_role": "instrumental"},
        headers={"X-Forwarded-For": ip_b}
    )
    assert res3.status_code == 202
    job2_id = res3.json()["id"]

    # 4. Check queue status for IP A shows client_can_submit == False
    status_a = client.get("/api/queue/status", headers={"X-Forwarded-For": ip_a}).json()
    assert status_a["client_can_submit"] is False
    assert status_a["client_active_job_id"] == job1_id

    # 5. Cancel or wait for job 1 to complete -> IP A can submit again
    client.post(f"/api/jobs/{job1_id}/cancel")
    time.sleep(0.1)

    # Now IP A can submit again (for project 1)
    res_retry = client.post(
        f"/api/projects/{p1['id']}/analyze",
        json={"engine": "monophonic", "tempo": 100, "meter": [4, 4], "key": "C", "melody_role": "instrumental"},
        headers={"X-Forwarded-For": ip_a}
    )
    assert res_retry.status_code == 202

    # Clean up
    client.post(f"/api/jobs/{job2_id}/cancel")
    client.post(f"/api/jobs/{res_retry.json()['id']}/cancel")


def test_queue_capacity_limit_rejection(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.gpu_name", lambda: None)
    # Set max_queue=2 and max_workers=1
    monkeypatch.setenv("SHEET_STUDIO_MAX_QUEUE", "2")
    monkeypatch.setenv("SHEET_STUDIO_MAX_WORKERS", "1")

    app = create_app(tmp_path / "data")
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        # Create 4 projects
        p1 = upload_sample(client, tmp_path, "Queue 1")
        p2 = upload_sample(client, tmp_path, "Queue 2")
        p3 = upload_sample(client, tmp_path, "Queue 3")
        p4 = upload_sample(client, tmp_path, "Queue 4")

        # Mock transcribe in run_job to simulate a long-running job so jobs queue up
        import backend.transcription
        started_event = False

        def slow_transcribe(*args, **kwargs):
            time.sleep(2.0)
            return {
                "schema_version": 1, "revision": 0, "title": "Mock",
                "tempo": 100, "meter": [4, 4], "key": "C",
                "notes": [], "harmonies": [], "diagnostics": [],
                "source_engine": "monophonic", "review_status": "needs_review",
                "melody_role": "instrumental"
            }

        monkeypatch.setattr(backend.transcription, "transcribe", slow_transcribe)

        # Job 1 (running)
        r1 = client.post(f"/api/projects/{p1['id']}/analyze", json={"engine": "monophonic", "tempo": 100, "meter": [4, 4], "key": "C", "melody_role": "instrumental"}, headers={"X-Forwarded-For": "10.0.0.1"})
        assert r1.status_code == 202

        # Give worker a split-second to pick up job 1 and transition it to 'running'
        time.sleep(0.15)

        # Job 2 (queued, pos 1)
        r2 = client.post(f"/api/projects/{p2['id']}/analyze", json={"engine": "monophonic", "tempo": 100, "meter": [4, 4], "key": "C", "melody_role": "instrumental"}, headers={"X-Forwarded-For": "10.0.0.2"})
        assert r2.status_code == 202

        # Job 3 (queued, pos 2 - reaches max_queue = 2)
        r3 = client.post(f"/api/projects/{p3['id']}/analyze", json={"engine": "monophonic", "tempo": 100, "meter": [4, 4], "key": "C", "melody_role": "instrumental"}, headers={"X-Forwarded-For": "10.0.0.3"})
        assert r3.status_code == 202

        # Check job 3 has queue_position
        j3 = client.get(f"/api/jobs/{r3.json()['id']}").json()
        assert j3["status"] == "queued"
        assert j3.get("queue_position") == 2

        # Job 4 from a new IP should now be REJECTED with 503 (Queue Full)
        r4 = client.post(f"/api/projects/{p4['id']}/analyze", json={"engine": "monophonic", "tempo": 100, "meter": [4, 4], "key": "C", "melody_role": "instrumental"}, headers={"X-Forwarded-For": "10.0.0.4"})
        assert r4.status_code == 503
        data4 = r4.json()
        assert data4.get("code") == "QUEUE_BUSY"
        assert "quá tải" in data4["detail"]

        # Cancel all to cleanly shut down
        for r in (r1, r2, r3):
            client.post(f"/api/jobs/{r.json()['id']}/cancel")
