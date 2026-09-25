"""Create isolated projects for score-edit browser regression checks."""
import sys
from pathlib import Path

from backend.schemas import ScoreDocument
from backend.storage import Store
from scripts.make_test_audio import create_fixture


root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
store = Store(root)
if store.projects():
    raise SystemExit("Use a new empty QA data directory")

audio = create_fixture(root / "scale.wav")


def create_project(project_id: str, title: str, with_lyric: bool) -> None:
    store.create_project(project_id, title, "scale.wav", audio, "test", 4.8)
    score = ScoreDocument(title=title, tempo=72).model_dump()
    score["notes"] = [
        dict(
            id=f"{project_id}-n{index}", pitch=pitch, start=str(index), duration="1",
            velocity=85, source_start=float(index), source_end=float(index + 1),
        )
        for index, pitch in enumerate((60, 62, 64, 65, 67, 69, 71, 72))
    ]
    if with_lyric:
        score["lyrics"] = [dict(
            id=f"{project_id}-l1", text="La", note_id=score["notes"][0]["id"],
            verse=1, syllabic="single", source_start=0.0, source_end=1.0,
        )]
    store.save_score(project_id, score)


create_project("ui-with-lyrics", "Lyric project", True)
create_project("ui-no-lyrics", "No lyric project", False)
print(root)
