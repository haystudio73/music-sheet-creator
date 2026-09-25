"""Create an isolated browser-regression workspace; never uses user projects."""
import sys
from pathlib import Path
from backend.storage import Store
from backend.schemas import ScoreDocument
from scripts.make_test_audio import create_fixture
root=Path(sys.argv[1]).resolve()
root.mkdir(parents=True,exist_ok=True)
store=Store(root)
if store.projects(): raise SystemExit('Use a new empty QA data directory')
audio=create_fixture(root/'scale.wav')
store.create_project('ui-fixture','Playback regression','scale.wav',audio,'test',4.8)
score=ScoreDocument(title='Playback regression',tempo=60).model_dump()
score['notes']=[dict(id=f'n{i}',pitch=p,start=str(s),duration=str(d),velocity=85,source_start=float(s),source_end=float(s+d)) for i,(p,s,d) in enumerate([(60,0,1),(62,2,4),(64,7,1)]+[(60+i%12,i,1) for i in range(8,64)])]
score['lyrics']=[dict(id='l1',text='Nắng',note_id='n0',verse=1,syllabic='single',source_start=0,source_end=1)]
store.save_score('ui-fixture',score)
print(root)
