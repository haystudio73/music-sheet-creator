"""Isolated pinned SheetSage2 runtime. JSON progress on stdout; logs on stderr."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]


def report(stage: str, message: str):
    print(json.dumps({"stage": stage, "message": message}, ensure_ascii=False), flush=True)


def verify_snapshot(folder: Path, files: dict):
    # Verify downloaded code/config/adapter weights before trusting custom code.
    # The parent loader additionally verifies its upstream-pinned SHA256.
    for name, metadata in files.items():
        if not name.endswith((".py", ".json", ".safetensors")):
            continue
        path = folder / name
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(8 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest() != metadata["sha256"]:
            raise RuntimeError(f"Snapshot checksum mismatch: {folder.name}/{name}. Rerun model setup.")


def run(request: dict):
    import numpy as np
    import torch
    from transformers import AutoModel
    manifest = json.loads((ROOT / "models" / "installed.json").read_text(encoding="utf-8"))
    report("loading_model", "Đang xác minh checksum model và custom code cục bộ.")
    verify_snapshot(Path(request["adapter"]), manifest["adapter"]["files"])
    verify_snapshot(Path(request["parent"]), manifest["parent"]["files"])
    device = select_device(request.get("device", "auto"), torch)
    report("loading_model", f"Đang nạp SheetSage2 trên {torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'}.")
    model = AutoModel.from_pretrained(
        request["adapter"], base_model_path=request["parent"], trust_remote_code=True,
        local_files_only=True, attn_implementation="sdpa",
    ).eval().to(device)
    waveform = np.load(request["audio"], allow_pickle=False)
    output_dir = Path(request["output_dir"])

    def on_progress(event: dict):
        stage = event.get("stage", "transcribing")
        index, count = event.get("window"), event.get("windows")
        detail = f" · cửa sổ {index}/{count}" if index is not None else ""
        tokens = f" · {event['tokens']} token" if "tokens" in event else ""
        report(stage, f"SheetSage2: {stage}{detail}{tokens}")

    with torch.inference_mode():
        result = model.transcribe(waveform, sampling_rate=request["sample_rate"], output_dir=str(output_dir),
                                  dtype="bf16" if device == "cuda" else "fp32", progress=on_progress)
    payload = {"events": result["events"], "duration": result["duration_seconds"], "warnings": result.get("warnings", []),
               "elapsed_seconds": result.get("elapsed_seconds"), "peak_gpu_mib": result.get("peak_gpu_mib"),
               "device": device}
    if result.get("abc_error"):
        payload["warnings"].append(f"Renderer ABC upstream: {result['abc_error']}. Events gốc vẫn được giữ.")
    (output_dir / "normalized-events.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report("complete", "SheetSage2 hoàn tất; đang dựng bản nháp lead sheet.")
    try:
        del model
        if device == "cuda":
            torch.cuda.empty_cache()
        import gc
        gc.collect()
    except Exception:
        pass


def select_device(requested, torch):
    if requested == "cpu":
        return "cpu"
    if requested not in {"auto", "gpu"}:
        raise ValueError("Unknown processing device")
    available = torch.cuda.is_available()
    if requested == "gpu" and not available:
        raise RuntimeError("GPU được chọn nhưng CUDA không khả dụng. Chọn CPU only hoặc cài runtime CUDA.")
    return "cuda" if available else "cpu"


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    output_dir = Path(request["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        run(request)
    except Exception as exc:
        error = str(exc)
        if "out of memory" in error.lower():
            error = "GPU hết VRAM. SheetSage2 pad cửa sổ tới 300 giây; audio ngắn hơn chưa chắc giảm peak VRAM. Đóng ứng dụng dùng GPU hoặc thử runtime CPU. " + error[:500]
        (output_dir / "worker-error.json").write_text(json.dumps({"error": error}, ensure_ascii=False), encoding="utf-8")
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
