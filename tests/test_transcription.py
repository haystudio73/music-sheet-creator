"""Signal-level regression tests; synthetic fixtures do not benchmark mixed music."""
from fractions import Fraction
from pathlib import Path
import json

import numpy as np
import pytest
from scipy.io import wavfile

from backend.transcription import (
    TranscriptionCancelled, _events_to_score, _harmony, _yin_pitch,
    ffmpeg_executable, transcribe,
)


@pytest.mark.parametrize("midi", [48, 60, 69, 79, 84])
def test_yin_identifies_known_sinusoid_with_harmonics(midi):
    rate = 22050
    frequency = 440 * 2 ** ((midi - 69) / 12)
    time = np.arange(2048) / rate
    signal = np.sin(2 * np.pi * frequency * time) + 0.3 * np.sin(4 * np.pi * frequency * time)
    detected, confidence = _yin_pitch(signal, rate)
    assert abs(12 * np.log2(detected / frequency)) < 0.1
    assert confidence > 0.95


def make_fixture(path: Path, *, silence=False):
    rate = 22050
    audio = np.zeros(int(2 * rate), dtype=np.float32)
    if not silence:
        # Two separated pitches with attacks away from frame boundaries.
        for midi, start, end in ((60, 0.25, 0.75), (67, 1.0, 1.5)):
            t = np.arange(round((end - start) * rate)) / rate
            hz = 440 * 2 ** ((midi - 69) / 12)
            tone = 0.4 * np.sin(2 * np.pi * hz * t)
            audio[round(start * rate):round(start * rate) + len(tone)] = tone
    wavfile.write(path, rate, audio)
    return path


@pytest.mark.skipif(not ffmpeg_executable(), reason="FFmpeg required for real decoding")
def test_dsp_decodes_audio_and_preserves_pitch_rest_and_timing(tmp_path):
    audio = make_fixture(tmp_path / "known-pitches.wav")
    stages = []
    work = tmp_path / "job"
    result = transcribe(audio, {"engine": "monophonic", "tempo": 120, "title": "Test"},
                        work, lambda stage, message: stages.append(stage), lambda: False)
    assert [note["pitch"] for note in result["notes"]] == [60, 67]
    assert [Fraction(note["start"]) for note in result["notes"]] == [Fraction(1, 2), Fraction(2)]
    assert [Fraction(note["duration"]) for note in result["notes"]] == [Fraction(1), Fraction(1)]
    assert result["harmonies"] == []  # DSP must not fabricate chords.
    raw = json.loads((work / "raw-notes.json").read_text(encoding="utf-8"))
    assert abs(raw["notes"][0]["start"] - 0.25) < 0.05
    assert abs(raw["notes"][1]["end"] - 1.5) < 0.05
    assert "decoding" in stages and "transcribing" in stages
    assert result["review_status"] == "needs_review"


@pytest.mark.skipif(not ffmpeg_executable(), reason="FFmpeg required for real decoding")
def test_silence_never_generates_fake_notes(tmp_path):
    result = transcribe(make_fixture(tmp_path / "silence.wav", silence=True),
                        {"engine": "monophonic"}, tmp_path / "job",
                        lambda *_: None, lambda: False)
    assert result["notes"] == []
    assert result["harmonies"] == []


def test_cancellation_matches_job_runner_contract(tmp_path):
    audio = make_fixture(tmp_path / "cancel.wav")
    with pytest.raises(InterruptedError):
        transcribe(audio, {"engine": "monophonic"}, tmp_path / "job",
                   lambda *_: None, lambda: True)
    assert issubclass(TranscriptionCancelled, InterruptedError)
    assert not (tmp_path / "job" / "score-draft.json").exists()


@pytest.mark.skipif(not ffmpeg_executable(), reason="FFmpeg required for real decoding")
def test_cancellation_during_dsp_does_not_publish_score(tmp_path):
    audio = make_fixture(tmp_path / "cancel.wav")
    stopped = False

    def progress(stage, _):
        nonlocal stopped
        if stage == "transcribing":
            stopped = True

    with pytest.raises(TranscriptionCancelled):
        transcribe(audio, {"engine": "monophonic"}, tmp_path / "job", progress, lambda: stopped)
    assert not (tmp_path / "job" / "score-draft.json").exists()


def test_harmony_preserves_unknown_no_chord_and_inversion():
    assert _harmony("N")["kind"] == "no_chord"
    assert _harmony("X")["kind"] == "unknown"
    assert _harmony("C:maj13")["kind"] == "unknown"
    assert _harmony("C:maj/3") == {"root": "C", "quality": "major", "bass": "E", "kind": "chord"}
    assert _harmony("D:min/b3")["bass"] == "F"


def test_model_events_choose_instrumental_track_and_report_fixed_tempo():
    events = [
        {"time": 0.0, "values": {"melody": [
            {"track": 0, "pitch": 60, "end_time": 0.5},
            {"track": 1, "pitch": 72, "end_time": 1.0}], "chord": "C:maj/3"}},
        {"time": 1.0, "values": {"chord": "N"}},
        {"time": 1.5, "values": {"chord": "C:maj13"}},
    ]
    score = _events_to_score(Path("song.wav"), {"tempo": 120, "melody_role": "instrumental"}, events, 2.0)
    assert [note["pitch"] for note in score["notes"]] == [72]
    assert score["notes"][0]["duration"] == "2"
    assert [chord["kind"] for chord in score["harmonies"]] == ["chord", "no_chord", "unknown"]
    assert score["harmonies"][0]["bass"] == "E"
    assert any("tempo" in item and "cố định" in item for item in score["diagnostics"])
    assert any("C:maj13" in item for item in score["diagnostics"])
