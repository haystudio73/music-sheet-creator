"""Create isolated multi-page PDF QA data. Never opens real user projects."""
import sys
from fractions import Fraction
from pathlib import Path

from backend.schemas import ScoreDocument
from backend.storage import Store
from scripts.make_test_audio import create_fixture

root = Path(sys.argv[1]).resolve()
store = Store(root)
if store.projects():
    raise SystemExit("Use a new empty QA data directory")
audio = create_fixture(root / "scale.wav")
store.create_project("pdf-fixture", "Khúc thử nghiệm – Nắng bên đồi", "scale.wav", audio, "test", 4.8)
score = ScoreDocument(title="Khúc thử nghiệm – Nắng bên đồi", key="F", tempo=96).model_dump()
events = [(65, "1/2", "5"), (70, "6", "1/3"), (72, "19/3", "2/3")]
events += [(60 + i % 12, str(i), "1") for i in range(8, 320)]
score["notes"] = [dict(id=f"n{i}", pitch=p, start=s, duration=d, velocity=85,
                       source_start=float(Fraction(s)), source_end=float(Fraction(s) + Fraction(d)))
                  for i, (p, s, d) in enumerate(events)]
score["harmonies"] = [dict(id=f"h{i}", root="F" if i % 2 == 0 else "Bb",
                           quality="major" if i % 2 == 0 else "major-seventh", bass="A" if i % 2 == 0 else None,
                           start=str(i * 4), duration="4", kind="chord") for i in range(80)]
words = ["Nắng", "lên", "bên", "đồi", "Gió", "đưa", "mây", "về"]
score["lyrics"] = [dict(id=f"l{verse}-{i}", text=words[(i + verse - 1) % len(words)], note_id=f"n{i}",
                        verse=verse, syllabic="single", source_start=None, source_end=None)
                   for verse in (1, 2) for i in range(len(events))]
store.save_score("pdf-fixture", score)
print(root)
