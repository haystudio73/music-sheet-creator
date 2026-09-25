"""Download pinned public HF artifacts; never accepts a gated repository's terms.

Only run during explicit setup. Inference uses local files and offline mode.
The optional HF_TOKEN is read from the environment and never persisted/logged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def fetch(url: str):
    headers = {"User-Agent": "LocalMusicSheets/0.1"}
    token = os.environ.get("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError(
                "Hugging Face refused access. Open the official model page, review its terms "
                "and request access yourself if required; then set HF_TOKEN for this setup process. "
                "No terms were accepted automatically."
            ) from None
        raise RuntimeError(f"Model download failed with HTTP {exc.code}") from None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install(repo: str, revision: str, dirname: str) -> dict:
    with fetch(f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true") as response:
        metadata = json.load(response)
    if metadata.get("sha") != revision:
        raise RuntimeError("HF revision mismatch; refusing an unpinned snapshot")
    folder = ROOT / ".cache" / "model-snapshots" / dirname
    folder.mkdir(parents=True, exist_ok=True)
    files = {}
    for item in metadata["siblings"]:
        name = item["rfilename"]
        # Only root-level inference code/config/weights and notices; no scripts/assets/benchmarks.
        if "/" in name or not (name.endswith((".py", ".json", ".safetensors"))
                               or name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md", "requirements.txt")):
            continue
        path = folder / name
        expected = item.get("lfs", {}).get("sha256")
        expected_size = item.get("size")
        if path.is_file() and (expected_size is None or path.stat().st_size == expected_size):
            actual = sha256(path)
            if expected and actual == expected:
                files[name] = {"sha256": actual, "bytes": path.stat().st_size}
                print(f"Verified existing {repo}/{name}", flush=True)
                continue
        print(f"Downloading {repo}/{name}", flush=True)
        temporary = path.with_suffix(path.suffix + ".partial")
        digest = hashlib.sha256()
        with fetch(f"https://huggingface.co/{repo}/resolve/{revision}/{name}") as source, temporary.open("wb") as target:
            while chunk := source.read(8 << 20):
                target.write(chunk)
                digest.update(chunk)
        actual = digest.hexdigest()
        if expected and actual != expected:
            raise RuntimeError(f"SHA256 mismatch for {repo}/{name}; incomplete file was not installed")
        if expected_size is not None and temporary.stat().st_size != expected_size:
            raise RuntimeError(f"Size mismatch for {repo}/{name}")
        temporary.replace(path)
        files[name] = {"sha256": actual, "bytes": path.stat().st_size}
    if not (folder / "model.safetensors").is_file():
        raise RuntimeError(f"No model.safetensors in {repo}; registry needs review")
    return {"repo_id": repo, "revision": revision, "path": str(folder.relative_to(ROOT)), "files": files}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="Verify runtime imports and write runtime status")
    args = parser.parse_args()
    registry = json.loads((ROOT / "models" / "registry.json").read_text(encoding="utf-8"))["sheetsage2"]
    if args.probe:
        import torch
        import transformers
        import torchaudio
        import mir_eval
        torch_major = int(torch.__version__.split("+")[0].split(".")[0])
        if torch_major < 2 or transformers.__version__ != "4.45.2":
            raise RuntimeError(f"Runtime version differs from reviewed model requirements (torch={torch.__version__}, transformers={transformers.__version__})")
        status = {"python": str(Path(os.sys.executable).resolve()), "torch": torch.__version__,
                  "transformers": transformers.__version__, "cuda": torch.cuda.is_available(),
                  "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                  "inference_verified": False}
        (ROOT / "models" / "runtime-status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        print(json.dumps(status), flush=True)
        return
    adapter = install(registry["id"], registry["revision"], "sheetsage2")
    parent = install(registry["parent_id"], registry["parent_revision"], "mert2")
    if parent["files"]["model.safetensors"]["sha256"] != registry["parent_weights_sha256"]:
        raise RuntimeError("Parent checksum does not match reviewed SheetSage2 config")
    manifest = {"schema_version": 1, "adapter": adapter, "parent": parent}
    manifest_path = ROOT / "models" / "installed.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Pinned snapshots verified. Run setup-model.ps1 to finish runtime setup.", flush=True)


if __name__ == "__main__":
    main()
