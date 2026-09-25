"""MusicXML editor saves preserve notation and reject stale/deleted sources."""
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.app import create_app
from backend.schemas import AnalyzeRequest, ScoreDocument
from workers.sheetsage2_worker import select_device


@pytest.fixture
def editor(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.app.gpu_name', lambda: None)
    app = create_app(tmp_path / 'data')
    store = app.state.store
    audio = store.root / 'audio.wav'
    audio.write_bytes(b'RIFF')
    store.create_project('editor-test', 'Editor test', 'audio.wav', audio, 'test', 1)
    score = ScoreDocument(title='Editor test', notes=[dict(id='n1', pitch=60, start='0', duration='1')]).model_dump()
    store.save_score('editor-test', score)
    with TestClient(app) as client:
        client.get('/api/health')
        yield client, store


def test_editor_review_save_conflict_and_source_isolation(editor):
    client, store = editor
    url = '/api/projects/editor-test/editor'
    assert client.get(url + '?revision=1').status_code == 409
    revision = client.post('/api/projects/editor-test/review', json={'expected_revision': 1}).json()['revision']
    document = client.get(url, params={'revision': revision}).json()
    assert document['version'] == 0 and '<score-partwise' in document['musicxml']
    xml = document['musicxml'].replace('<step>C</step>', '<step>D</step>')
    body = dict(expected_revision=revision, expected_version=0, musicxml=xml)
    saved = client.put(url, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()['version'] == 1
    assert client.get(url, params={'revision': revision}).json()['musicxml'] == xml
    assert store.score('editor-test')['notes'][0]['pitch'] == 60
    assert client.put(url, json=body).status_code == 409
    body.update(expected_version=1, musicxml=xml.replace('<step>D</step>', '<step>E</step>'))
    assert client.put(url, json=body).json()['version'] == 2
    history = store.root / 'projects/editor-test/editor' / str(revision) / 'v1.json'
    assert history.is_file() and '<step>D</step>' in history.read_text()
    store.save_score('editor-test', store.score('editor-test'), expected_revision=revision)
    assert client.get(url, params={'revision': revision}).status_code == 409
    assert client.put(url, json={**body, 'expected_version': 2}).status_code == 409


@pytest.mark.parametrize('xml', ['<broken', '<html/>', '<score-partwise/>', '<!DOCTYPE x [<!ENTITY x "bad">]><score-partwise><part><measure>&x;</measure></part></score-partwise>'])
def test_editor_rejects_invalid_xml(editor, xml):
    client, _ = editor
    revision = client.post('/api/projects/editor-test/review', json={'expected_revision': 1}).json()['revision']
    assert client.put('/api/projects/editor-test/editor', json=dict(expected_revision=revision, expected_version=0, musicxml=xml)).status_code == 422


def test_editor_deleted_project(editor):
    client, _ = editor
    revision = client.post('/api/projects/editor-test/review', json={'expected_revision': 1}).json()['revision']
    client.delete('/api/projects/editor-test')
    assert client.get(f'/api/projects/editor-test/editor?revision={revision}').status_code == 404


def test_cpu_never_queries_cuda():
    def forbidden():
        raise AssertionError('CPU-only must not query CUDA')
    assert select_device('cpu', SimpleNamespace(cuda=SimpleNamespace(is_available=forbidden))) == 'cpu'


@pytest.mark.parametrize('available', [True, False])
def test_auto_and_explicit_gpu(available):
    torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: available))
    assert select_device('auto', torch) == ('cuda' if available else 'cpu')
    if available:
        assert select_device('gpu', torch) == 'cuda'
    else:
        with pytest.raises(RuntimeError, match='CUDA'):
            select_device('gpu', torch)


def test_device_request_validation():
    assert AnalyzeRequest().device == 'auto'
    assert AnalyzeRequest(device='cpu').model_dump()['device'] == 'cpu'
    with pytest.raises(ValidationError):
        AnalyzeRequest(device='invalid')
