"""Actual local transcription adapters, with no fabricated fallback results."""
from __future__ import annotations

from fractions import Fraction
import importlib.util
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
Progress = Callable[[str, str], None]
Cancelled = Callable[[], bool]
GRID = 4  # sixteenth notes: four divisions per quarter note


class TranscriptionCancelled(InterruptedError):
    """A requested cancellation, including terminated model inference."""


def ffmpeg_executable() -> str | None:
    candidate = os.environ.get("FFMPEG_PATH")
    if candidate and Path(candidate).is_file():
        return candidate
    return shutil.which("ffmpeg") or ("C:/ffmpeg/bin/ffmpeg.exe" if Path("C:/ffmpeg/bin/ffmpeg.exe").is_file() else None)


def _model_python() -> Path:
    default = ROOT / ".venv-model" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return Path(os.environ.get("SHEETSAGE2_PYTHON", str(default)))


def _installed() -> dict:
    path = ROOT / "models" / "installed.json"
    if not path.is_file():
        raise RuntimeError("Chưa tải SheetSage2 và MERT-v2. Chạy scripts/setup-model.ps1 trong thư mục dự án.")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        registry = json.loads((ROOT / "models" / "registry.json").read_text(encoding="utf-8"))["sheetsage2"]
        for name, revision in (("adapter", registry["revision"]), ("parent", registry["parent_revision"])):
            item = manifest[name]
            if item["revision"] != revision:
                raise ValueError("Model revision does not match registry")
            folder = ROOT / item["path"]
            for filename in ("config.json", "model.safetensors"):
                if not (folder / filename).is_file():
                    raise ValueError(f"Missing {name}/{filename}")
        return manifest
    except (KeyError, ValueError, OSError) as exc:
        raise RuntimeError(f"Model cục bộ chưa đầy đủ ({exc}). Chạy lại scripts/setup-model.ps1.") from exc


def engine_status() -> list[dict]:
    ffmpeg = ffmpeg_executable()
    available = False
    try:
        _installed()
        if not _model_python().is_file() or not (ROOT / "models" / "runtime-status.json").is_file():
            raise RuntimeError("Chưa cài runtime Python 3.11/PyTorch. Chạy scripts/setup-model.ps1.")
        if not ffmpeg:
            raise RuntimeError("Chưa tìm thấy FFmpeg. Cài FFmpeg hoặc đặt FFMPEG_PATH.")
        available = True
        reason = "Runtime và snapshot đã cài. Inference local; chất lượng bản phối cần người dùng kiểm tra."
    except RuntimeError as exc:
        reason = str(exc)
    dsp = bool(ffmpeg) and importlib.util.find_spec("numpy") is not None and importlib.util.find_spec("scipy") is not None
    return [
        {"id": "sheetsage2", "name": "SheetSage2 · Hugging Face", "available": available,
         "description": "AI tạo giai điệu và hợp âm từ bản phối. Weights CC-BY-NC-4.0; profile thử nghiệm GPU 12 GB.", "reason": reason},
        {"id": "monophonic", "name": "Giai điệu đơn · DSP thử nghiệm", "available": dsp,
         "description": "Phân tích tín hiệu một giai điệu sạch; không phải AI, không tách giai điệu trong bản phối, không tự đoán hợp âm.",
         "reason": "Sẵn sàng cho solo một nốt tại một thời điểm." if dsp else "Cần FFmpeg, NumPy và SciPy trong runtime API."},
    ]


def _check_cancel(cancelled: Cancelled):
    if cancelled():
        raise TranscriptionCancelled("Đã hủy phân tích.")


def _creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _decode(audio_path: Path, work_dir: Path, rate: int, cancelled: Cancelled):
    import numpy as np
    executable = ffmpeg_executable()
    if not executable:
        raise RuntimeError("Không tìm thấy FFmpeg; đặt biến FFMPEG_PATH tới ffmpeg.exe.")
    pcm_path = work_dir / "decoded.f32"
    log_path = work_dir / "decode.log"
    _check_cancel(cancelled)
    with log_path.open("wb") as error:
        command = [executable, "-v", "error", "-nostdin", "-y", "-i", str(audio_path.resolve()),
                   "-vn", "-t", "601", "-ac", "1", "-ar", str(rate), "-f", "f32le", str(pcm_path)]
        with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=error, creationflags=_creation_flags()) as process:
            started = time.monotonic()
            while process.poll() is None:
                if cancelled() or time.monotonic() - started > 180:
                    process.kill()
                    process.wait(timeout=10)
                    _check_cancel(cancelled)
                    raise RuntimeError("FFmpeg vượt thời gian giải mã 180 giây.")
                time.sleep(0.05)
            if process.returncode:
                raise ValueError("Không thể giải mã audio: " + log_path.read_text(errors="replace")[-1000:])
    _check_cancel(cancelled)
    samples = np.fromfile(pcm_path, dtype="<f4")
    if len(samples) < int(rate * 0.08) or not np.isfinite(samples).all():
        raise ValueError("Audio quá ngắn hoặc chứa dữ liệu mẫu không hợp lệ.")
    if len(samples) / rate > 600.05:
        raise ValueError("Bản thử nghiệm hỗ trợ audio tối đa 10 phút.")
    return samples


def _quarter(seconds: float, tempo: float) -> Fraction:
    return Fraction(round(seconds * tempo / 60 * GRID), GRID)


def _base_score(audio_path: Path, options: dict, engine: str) -> dict:
    tempo = float(options.get("tempo", 120))
    if not math.isfinite(tempo) or not 20 <= tempo <= 300:
        raise ValueError("Tempo phải từ 20 đến 300 BPM.")
    meter = options.get("meter", [4, 4])
    if len(meter) != 2 or meter[0] not in range(1, 13) or meter[1] not in (2, 4, 8, 16):
        raise ValueError("Nhịp không hợp lệ.")
    role = options.get("melody_role", "instrumental")
    if role not in ("instrumental", "vocal"):
        raise ValueError("melody_role phải là instrumental hoặc vocal.")
    return {"schema_version": 1, "revision": 0, "title": options.get("title") or audio_path.stem,
            "tempo": tempo, "meter": list(meter), "key": options.get("key", "C"),
            "notes": [], "harmonies": [], "diagnostics": [], "source_engine": engine,
            "review_status": "needs_review", "melody_role": role}


def _notes_to_score(raw_notes: list[dict], score: dict) -> None:
    raw_notes.sort(key=lambda n: (n["start"], n["pitch"]))
    previous_end = Fraction(0)
    overlaps = 0
    for index, raw in enumerate(raw_notes):
        start = max(Fraction(0), _quarter(raw["start"], score["tempo"]))
        end = max(start + Fraction(1, GRID), _quarter(raw["end"], score["tempo"]))
        if start < previous_end:
            overlaps += 1
        previous_end = max(previous_end, end)
        score["notes"].append({"id": f"n{index + 1}", "pitch": int(raw["pitch"]),
                               "start": str(start), "duration": str(end - start),
                               "velocity": int(raw.get("velocity", 88)),
                               "source_start": round(raw["start"], 6), "source_end": round(raw["end"], 6)})
    if overlaps:
        score["diagnostics"].append(f"Có {overlaps} nốt chồng nhau sau quy đổi nhịp; dữ liệu gốc được giữ. Cần chỉnh trước khi xuất lead sheet đơn âm.")
    if not raw_notes:
        score["diagnostics"].append("Không tìm thấy nốt giai điệu phù hợp. Thử chọn đúng bè giọng hát/nhạc cụ hoặc dùng track solo rõ hơn.")
    score["diagnostics"].append("Bản nháp dùng tempo, giọng và nhịp cố định do bạn chọn; lượng tử hóa lưới nốt móc kép (1/16), chưa hỗ trợ rubato/đổi nhịp tự động.")


def _yin_pitch(frame, sample_rate: int, fmin: float = 65.4, fmax: float = 1200.0) -> tuple[float, float]:
    """YIN cumulative difference with FFT autocorrelation and local refinement."""
    import numpy as np
    from scipy.signal import correlate
    centered = frame.astype(np.float64) - float(np.mean(frame))
    size = len(centered)
    min_lag, max_lag = max(2, int(sample_rate / fmax)), min(size // 2, int(sample_rate / fmin))
    corr = correlate(centered, centered, mode="full", method="fft")[size - 1:size + max_lag]
    energy = np.concatenate(([0.0], np.cumsum(centered * centered)))
    lags = np.arange(max_lag + 1)
    difference = np.maximum(0.0, energy[size - lags] + energy[size] - energy[lags] - 2 * corr)
    cmnd = np.ones(max_lag + 1)
    cmnd[1:] = difference[1:] * lags[1:] / np.maximum(np.cumsum(difference[1:]), 1e-12)
    lag = min_lag
    while lag <= max_lag:
        if cmnd[lag] < 0.16:
            while lag < max_lag and cmnd[lag + 1] < cmnd[lag]:
                lag += 1
            break
        lag += 1
    if lag > max_lag:
        lag = min_lag + int(np.argmin(cmnd[min_lag:]))
        if cmnd[lag] > 0.24:
            return 0.0, 0.0
    refined = float(lag)
    if 1 <= lag < max_lag:
        a, b, c = cmnd[lag - 1:lag + 2]
        denominator = a - 2 * b + c
        if abs(denominator) > 1e-10:
            refined += float(np.clip(0.5 * (a - c) / denominator, -0.5, 0.5))
    return sample_rate / refined, float(1 - cmnd[lag])


def _monophonic(audio_path: Path, options: dict, work_dir: Path, progress: Progress, cancelled: Cancelled) -> dict:
    import numpy as np
    from scipy.ndimage import median_filter
    rate, window, hop = 22050, 2048, 220
    score = _base_score(audio_path, options, "monophonic")
    progress("decoding", "Đang giải mã audio thành mono để phân tích giai điệu đơn.")
    audio = _decode(audio_path, work_dir, rate, cancelled)
    progress("transcribing", "Đang dò cao độ bằng DSP; cần audio solo một nốt tại một thời điểm.")
    padded = np.pad(audio, (window // 2, window // 2))
    frame_count = math.ceil(len(audio) / hop)
    rms = np.array([np.sqrt(np.mean(padded[i * hop:i * hop + window] ** 2)) for i in range(frame_count)])
    threshold = max(0.002, float(np.quantile(rms, 0.90)) * 0.065)
    pitches = np.full(frame_count, -1, dtype=int)
    confidence = np.zeros(frame_count)
    for index in range(frame_count):
        if index % 200 == 0:
            _check_cancel(cancelled)
        if rms[index] < threshold:
            continue
        hz, confidence[index] = _yin_pitch(padded[index * hop:index * hop + window], rate)
        if hz:
            midi = round(69 + 12 * math.log2(hz / 440))
            if 36 <= midi <= 90:
                pitches[index] = midi
    # Suppress isolated one-frame pitch glitches; preserve actual silence intervals.
    filtered = median_filter(pitches, size=3, mode="nearest")
    filtered[rms < threshold] = -1
    notes = []
    beginning = 0
    for index in range(1, frame_count + 1):
        if index < frame_count and filtered[index] == filtered[beginning]:
            continue
        start = beginning * hop / rate
        end = min(len(audio) / rate, index * hop / rate)
        if filtered[beginning] >= 0 and end - start >= 0.07:
            notes.append({"pitch": int(filtered[beginning]), "start": start, "end": end,
                          "confidence": round(float(np.median(confidence[beginning:index])), 4), "velocity": 88})
        beginning = index
    _check_cancel(cancelled)
    (work_dir / "raw-notes.json").write_text(json.dumps({"engine": "dsp-yin", "sample_rate": rate,
        "hop": hop, "window": window, "duration": len(audio) / rate, "notes": notes}, ensure_ascii=False, indent=2), encoding="utf-8")
    _notes_to_score(notes, score)
    score["diagnostics"].insert(0, "DSP thử nghiệm, không phải AI. Chỉ dùng giai điệu đơn rõ; bản phối nhiều nhạc cụ có thể cho cao độ sai.")
    score["diagnostics"].append("Không nhận dạng hợp âm ở chế độ DSP. Thêm hợp âm thủ công hoặc dùng SheetSage2; ô hợp âm trống không có nghĩa là N.C.")
    progress("building_score", f"Đã phát hiện {len(notes)} nốt; đang tạo bản nháp để kiểm tra.")
    return score


CHORD_QUALITIES = {"maj": "major", "min": "minor", "7": "dominant-seventh", "maj7": "major-seventh",
                   "min7": "minor-seventh", "dim": "diminished", "aug": "augmented",
                   "sus2": "suspended-second", "sus4": "suspended-fourth"}
PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _harmony(label: str) -> dict:
    empty = {"root": "C", "quality": "major", "bass": None}
    if label == "N":
        return {**empty, "kind": "no_chord"}
    if label in ("X", ""):
        return {**empty, "kind": "unknown"}
    match = re.fullmatch(r"([A-G](?:#|b)?):([^/]+)(?:/([b#]?[1-7]))?", label)
    if not match or match[2] not in CHORD_QUALITIES:
        return {**empty, "kind": "unknown"}
    root, quality, degree = match.groups()
    bass = None
    if degree:
        semitones = (0, 2, 4, 5, 7, 9, 11)[int(degree[-1]) - 1]
        semitones += 1 if degree.startswith("#") else -1 if degree.startswith("b") else 0
        root_pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[root[0]]
        root_pc += 1 if root.endswith("#") else -1 if root.endswith("b") else 0
        bass = PITCH_CLASSES[(root_pc + semitones) % 12]
    return {"root": root, "quality": CHORD_QUALITIES[quality], "bass": bass, "kind": "chord"}


def _events_to_score(audio_path: Path, options: dict, events: list[dict], duration: float, warnings: list[str] | None = None) -> dict:
    score = _base_score(audio_path, options, "sheetsage2")
    selected_track = 0 if score["melody_role"] == "vocal" else 1
    notes = []
    chord_events = []
    for event in events:
        start = max(0.0, float(event["time"]))
        if not math.isfinite(start) or start >= duration:
            continue
        values = event["values"]
        for note in values.get("melody", []):
            end = min(duration, float(note["end_time"]))
            pitch = int(note["pitch"])
            if int(note["track"]) == selected_track and math.isfinite(end) and end > start and 0 <= pitch <= 127:
                notes.append({"pitch": pitch, "start": start, "end": end, "velocity": 88})
        if "chord" in values:
            chord_events.append((start, str(values["chord"])))
    _notes_to_score(notes, score)
    chord_events.sort()
    unknown_labels = set()
    for index, (start_seconds, label) in enumerate(chord_events):
        end_seconds = chord_events[index + 1][0] if index + 1 < len(chord_events) else duration
        start, end = _quarter(start_seconds, score["tempo"]), _quarter(end_seconds, score["tempo"])
        if end <= start:
            continue
        chord = _harmony(label)
        if chord["kind"] == "unknown" and label not in ("X", ""):
            unknown_labels.add(label)
        score["harmonies"].append({"id": f"h{index + 1}", **chord, "start": str(start), "duration": str(end - start)})
    score["diagnostics"].extend(warnings or [])
    score["diagnostics"].insert(0, "SheetSage2: bản nháp AI cần nghe và kiểm tra lại cao độ, quãng tám, hợp âm và nhịp.")
    if unknown_labels:
        score["diagnostics"].append("Loại hợp âm chưa hỗ trợ được giữ là chưa xác định; nhãn gốc trong events.json: " + ", ".join(sorted(unknown_labels)))
    return score


def _sheetsage2(audio_path: Path, options: dict, work_dir: Path, progress: Progress, cancelled: Cancelled) -> dict:
    import numpy as np
    manifest = _installed()
    if not _model_python().is_file():
        raise RuntimeError("Thiếu runtime model. Chạy scripts/setup-model.ps1.")
    progress("decoding", "Đang giải mã audio local cho SheetSage2.")
    waveform = _decode(audio_path, work_dir, 24000, cancelled)
    waveform_path = work_dir / "waveform.npy"
    np.save(waveform_path, waveform)
    request = {"audio": str(waveform_path.resolve()), "sample_rate": 24000, "device": options.get("device", "auto"),
               "output_dir": str((work_dir / "sheetsage2").resolve()),
               "adapter": str((ROOT / manifest["adapter"]["path"]).resolve()),
               "parent": str((ROOT / manifest["parent"]["path"]).resolve())}
    request_path = work_dir / "model-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
               HF_HOME=str(ROOT / ".cache" / "huggingface"), HF_MODULES_CACHE=str(ROOT / ".cache" / "hf-modules"),
               PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    # A read-only token is unnecessary during inference and is not handed to model code.
    env.pop("HF_TOKEN", None)
    env.pop("HUGGING_FACE_HUB_TOKEN", None)
    if request["device"] == "cpu":
        env["CUDA_VISIBLE_DEVICES"] = ""
    log_path = work_dir / "model-worker.log"
    lines: queue.Queue[str] = queue.Queue()
    progress("loading_model", "Đang nạp snapshot SheetSage2 và MERT-v2 từ máy; lần đầu có thể lâu.")
    with log_path.open("w", encoding="utf-8") as log:
        with subprocess.Popen([str(_model_python()), str(ROOT / "workers" / "sheetsage2_worker.py"), str(request_path.resolve())],
                              cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=log, text=True, encoding="utf-8",
                              creationflags=_creation_flags()) as process:
            def consume():
                for line in process.stdout:
                    lines.put(line)
            reader = threading.Thread(target=consume, daemon=True)
            reader.start()
            started = time.monotonic()
            while process.poll() is None or not lines.empty():
                if cancelled() or time.monotonic() - started > 3600:
                    process.kill()
                    process.wait(timeout=10)
                    _check_cancel(cancelled)
                    raise RuntimeError("SheetSage2 vượt thời gian tối đa 60 phút; tiến trình đã dừng, dữ liệu gốc còn được giữ.")
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    message = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if message.get("stage"):
                    progress(str(message["stage"]), str(message.get("message", message["stage"])))
            reader.join(timeout=2)
            if process.returncode:
                error_file = work_dir / "sheetsage2" / "worker-error.json"
                error = json.loads(error_file.read_text(encoding="utf-8"))["error"] if error_file.is_file() else log_path.read_text(encoding="utf-8", errors="replace")[-1200:]
                raise RuntimeError(f"SheetSage2 thất bại: {error}")
    _check_cancel(cancelled)
    result_path = work_dir / "sheetsage2" / "normalized-events.json"
    if not result_path.is_file():
        raise RuntimeError("Worker không tạo events; xem model-worker.log. Không sinh kết quả thay thế.")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    progress("building_score", "Đang chuyển nốt và hợp âm AI sang bản nháp có thể chỉnh sửa.")
    return _events_to_score(audio_path, options, result["events"], result["duration"], result.get("warnings", []))


def transcribe(audio_path: Path, options: dict, work_dir: Path, progress: Progress, cancelled: Cancelled) -> dict:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise ValueError("Không tìm thấy audio đầu vào.")
    _check_cancel(cancelled)
    engine = options.get("engine", "sheetsage2")
    if engine == "monophonic":
        result = _monophonic(audio_path, options, work_dir, progress, cancelled)
    elif engine == "sheetsage2":
        result = _sheetsage2(audio_path, options, work_dir, progress, cancelled)
    else:
        raise ValueError(f"Engine không được hỗ trợ: {engine}")
    _check_cancel(cancelled)
    (work_dir / "score-draft.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
