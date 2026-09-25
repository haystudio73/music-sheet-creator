"""Run actual offline inference on a generated four-second musical signal.

Use API Python: .venv/Scripts/python.exe -m workers.smoke_model
This checks integration/hardware, not transcription accuracy on real music.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import time

import numpy as np
from scipy.io import wavfile

from backend.transcription import transcribe

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / ".cache" / "model-smoke"
    folder.mkdir(parents=True, exist_ok=True)
    rate = 24000
    time_axis = np.arange(4 * rate) / rate
    audio = np.zeros_like(time_axis)
    for index, pitch in enumerate((60, 64, 67, 72, 71, 67, 64, 60)):
        start, end = index * rate // 2, (index + 1) * rate // 2
        t = np.arange(end - start) / rate
        hz = 440 * 2 ** ((pitch - 69) / 12)
        envelope = np.minimum(1, t / 0.02) * np.minimum(1, (0.5 - t) / 0.05)
        audio[start:end] = 0.25 * envelope * (np.sin(2 * np.pi * hz * t) + 0.2 * np.sin(4 * np.pi * hz * t))
    for pitch in (48, 52, 55):
        hz = 440 * 2 ** ((pitch - 69) / 12)
        audio += 0.045 * np.sin(2 * np.pi * hz * time_axis)
    source = folder / "synthetic-c-major.wav"
    wavfile.write(source, rate, audio.astype(np.float32))
    started = time.monotonic()
    record = {"fixture": source.name, "duration_seconds": 4, "purpose": "Integration and hardware smoke; not a musical accuracy benchmark"}
    try:
        score = transcribe(source, {"engine": "sheetsage2", "tempo": 120, "melody_role": "instrumental"},
                           folder / "job", lambda stage, message: print(f"{stage}: {message}", flush=True), lambda: False)
        worker = json.loads((folder / "job" / "sheetsage2" / "normalized-events.json").read_text(encoding="utf-8"))
        record.update({"success": True, "notes": len(score["notes"]), "harmonies": len(score["harmonies"]),
                       "inference_seconds": worker["elapsed_seconds"], "peak_gpu_mib": worker["peak_gpu_mib"],
                       "device": worker["device"], "warnings": worker["warnings"]})
    except Exception as exc:
        record.update({"success": False, "error": str(exc)})
    record["total_seconds"] = round(time.monotonic() - started, 2)
    record["checked_at"] = datetime.now(timezone.utc).isoformat()
    (folder / "smoke-result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    status_path = ROOT / "models" / "runtime-status.json"
    if status_path.is_file():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status.update({"inference_verified": record["success"], "last_smoke": record})
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)
    raise SystemExit(0 if record["success"] else 1)


if __name__ == "__main__":
    main()
