"""Generate an explicitly synthetic monophonic fixture, never product demo data."""
import argparse
import json
import math
import wave
from pathlib import Path

import numpy as np


def create_fixture(path: Path):
    sample_rate = 22050
    bpm = 100
    pitches = [60, 62, 64, 65, 67, 69, 71, 72]
    beat = 60 / bpm
    audio = np.zeros(int((len(pitches) * beat + .5) * sample_rate), dtype=np.float64)
    reference = []
    for index, pitch in enumerate(pitches):
        onset = index * beat
        duration = beat * .8
        count = round(duration * sample_rate)
        t = np.arange(count) / sample_rate
        frequency = 440 * 2 ** ((pitch - 69) / 12)
        wave_data = np.sin(2 * math.pi * frequency * t) + .25 * np.sin(4 * math.pi * frequency * t)
        envelope = np.minimum(1, t / .015) * np.minimum(1, (duration - t) / .035)
        offset = round(onset * sample_rate)
        audio[offset:offset + count] += .45 * wave_data * envelope
        reference.append({"pitch": pitch, "onset": onset, "offset": onset + duration})
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
    path.with_suffix(".reference.json").write_text(json.dumps({"synthetic": True, "tempo": bpm, "notes": reference}, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="tmp/test-audio/scale-c-major.wav")
    create_fixture(Path(parser.parse_args().output))
