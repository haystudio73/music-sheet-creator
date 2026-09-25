"""Download and convert six published GM sample banks into local JSON assets.

Only parses data from the upstream JavaScript assignment; never executes it.
The application does not contact this host during playback.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "frontend/public/instruments"
NAMES = ["acoustic_grand_piano", "acoustic_guitar_nylon", "violin", "flute", "clarinet", "acoustic_bass"]
BASE = "https://gleitz.github.io/midi-js-soundfonts/FluidR3_GM/"


def prepare(name):
    url = BASE + name + "-mp3.js"
    raw = urllib.request.urlopen(url, timeout=60).read()
    source = raw.decode("utf-8")
    marker = f"MIDI.Soundfont.{name} = "
    if marker not in source:
        raise ValueError("Unrecognized soundfont data")
    payload = source.split(marker, 1)[1].strip().removesuffix(";")
    samples = json.loads(re.sub(r",\s*}", "}", payload))
    if not samples or any(not re.fullmatch(r"[A-G](?:#|b)?-?\d+", key)
                          or not value.startswith("data:audio/mp3;base64,") for key, value in samples.items()):
        raise ValueError("Invalid soundfont sample dictionary")
    target = DESTINATION / (name + ".json")
    target.write_text(json.dumps(samples, separators=(",", ":")), encoding="utf-8")
    return {"instrument": name, "source": url, "source_sha256": hashlib.sha256(raw).hexdigest(),
            "json_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "samples": len(samples)}


if __name__ == "__main__":
    DESTINATION.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        entries = list(pool.map(prepare, NAMES))
    (DESTINATION / "manifest.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print(json.dumps([{k: entry[k] for k in ("instrument", "samples")} for entry in entries]))
