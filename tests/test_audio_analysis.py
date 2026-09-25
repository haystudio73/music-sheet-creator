import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy.io.wavfile import write
from backend.audio_analysis import estimate_pcm, SAMPLE_RATE
from backend.app import create_app
from backend.schemas import ScoreDocument


def rhythmic_chord(beats_per_bar=4, seconds=24):
    sr = SAMPLE_RATE
    y = np.zeros(sr * seconds, dtype=np.float32)
    t = np.arange(int(.15 * sr)) / sr
    chord = np.exp(-30*t) * (np.sin(2*np.pi*261.63*t) + .6*np.sin(2*np.pi*329.63*t) + .5*np.sin(2*np.pi*392*t))
    for beat in range(seconds*2):
        start = int(beat*.5*sr)
        y[start:start+len(t)] += chord * (.5 if beat % beats_per_bar == 0 else .18)
    return y


@pytest.mark.parametrize('meter', [3, 4])
def test_real_signal_tempo_key_and_accent_meter(meter):
    result = estimate_pcm(rhythmic_chord(meter))
    assert abs(result['tempo'] - 120) < 3
    assert result['key'] == 'C'
    assert result['meter'] == [meter, 4]
    assert result['analyzed_seconds'] == 24


def test_silence_short_and_nonfinite_audio_are_not_fabricated():
    for audio in [np.zeros(SAMPLE_RATE*4), np.ones(SAMPLE_RATE), np.full(SAMPLE_RATE*4, np.nan)]:
        with pytest.raises(ValueError): estimate_pcm(audio)


def test_sustained_tone_does_not_invent_meter():
    t = np.arange(SAMPLE_RATE*5)/SAMPLE_RATE
    result = estimate_pcm(.2*np.sin(2*np.pi*440*t))
    assert result['meter'] is None


def test_analysis_cache_draft_preview_clear_reload_and_review_gate(tmp_path, monkeypatch):
    monkeypatch.setattr('backend.app.gpu_name', lambda: None)
    app = create_app(tmp_path/'data')
    store = app.state.store
    audio = store.root/'fixture.wav'
    write(audio, SAMPLE_RATE, rhythmic_chord())
    store.create_project('fixture', 'Fixture', 'fixture.wav', audio, 'hash', 24)
    score = ScoreDocument(title='Fixture', tempo=120).model_dump()
    score['notes'] = [dict(id=f'n{i}', pitch=60+i, start=str(i), duration='1', velocity=80, source_start=i*.5, source_end=(i+1)*.5) for i in range(8)]
    words=b'[00:00.00]First words\n[00:02.00]New words\n[00:04.00]'
    store.stage_lyrics('fixture', words, {'filename':'lyrics.lrc','format':'lrc','offset_seconds':0,'cue_count':2})
    store.save_score('fixture', score)
    with TestClient(app) as client:
        client.get('/api/health')
        root='/api/projects/fixture'
        assert client.get(root+'/audio-analysis').json() is None
        detected=client.post(root+'/analyze-audio')
        assert detected.status_code == 200, detected.text
        assert detected.json()['key'] == 'C'
        assert client.get(root+'/audio-analysis').json() == detected.json()
        draft={**score, 'title':'Unsaved draft'}
        draft['notes']=[{**n,'pitch':n['pitch']+12} for n in score['notes']]
        preview=client.post(root+'/preview-draft',json=draft)
        assert preview.status_code == 200
        assert b'<octave>5</octave>' in preview.content
        saved=client.get(root+'/score').json()
        assert saved['revision'] == 1 and saved['notes'][0]['pitch'] == 60
        assert client.post(root+'/exports',json={'format':'musicxml','revision':1}).status_code == 409
        words=b'[00:00.00]First words\n[00:02.00]New words\n[00:04.00]'
        imported=client.post(root+'/lyrics',files={'file':('lyrics.lrc',words)},data={'expected_revision':1}).json()
        stale=client.request('DELETE',root+'/lyrics',json={'expected_revision':1})
        assert stale.status_code == 409 and store.lyric_input('fixture') is not None
        cleared=client.request('DELETE',root+'/lyrics',json={'expected_revision':imported['revision']})
        assert cleared.status_code == 200, cleared.text
        cleared=cleared.json()
        assert cleared['lyrics'] == [] and cleared['lyric_source'] is None
        assert store.lyric_input('fixture') is None
        assert store.score('fixture',imported['revision'])['lyrics']
        reloaded=client.post(root+'/lyrics',files={'file':('lyrics.lrc',words)},data={'expected_revision':cleared['revision']}).json()
        assert reloaded['lyrics'] and reloaded['review_status'] == 'needs_review'
        assert client.post(root+'/exports',json={'format':'musicxml','revision':reloaded['revision']}).status_code == 409
        reviewed=client.post(root+'/review',json={'expected_revision':reloaded['revision']}).json()
        export=client.post(root+'/exports',json={'format':'musicxml','revision':reviewed['revision']})
        assert export.status_code == 201
        saved=client.put(root+'/score',json={'expected_revision':reviewed['revision'],'score':reviewed}).json()
        assert saved['review_status'] == 'needs_review'
        assert client.get(export.json()['url']).status_code == 409
