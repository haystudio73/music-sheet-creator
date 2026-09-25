# Editor and settings verification · 2026-09-24

- Production TypeScript/Vite build passed; npm dependency audit: 0 vulnerabilities.
- `tests/test_editor.py`: 10 passed. Covers review gating, full XML save/reopen, immutable save history, concurrent-save conflict, stale/deleted sources, malformed XML/entities, CPU-only selection and unavailable GPU errors.
- Browser regression (`scripts/check-editor.js`) passed on isolated `ui-fixture`: 16 measures, 60 written pitched segments (59 notes including a tie), Vietnamese lyric, pitch edit, save/reopen, MusicXML download, eight independent section toggles, CPU/font preference persistence, lyrics-only font and mobile overflow check.
- Downloaded XML independently parsed: edited E4, 16 measures and lyric preserved.
- Existing full backend suite: 139 passed, 1 unrelated SRT styling failure, plus 6 new fixture setup errors in the first run. Fixed the new fixture path and reran all 10 new tests successfully. Resolved existing failure `tests/test_lyrics.py::test_srt_optional_index_entities_styling_and_positions` by adding subtitle override tag cleanup (`{\s*(?:[\\/]|[yY]:)[^}]*}`) in `backend/lyrics.py::_words` so ASS styling like `{\an8}` is stripped before lyric tokenization; full backend test suite is now 140/140 passed.
- Full SheetSage2 inference was not rerun. Device selection is unit-tested; worker request passes the selected device and CPU-only subprocess sets `CUDA_VISIBLE_DEVICES` empty before Torch import.

To repeat browser QA, create a fresh workspace using `python -m scripts.ui_fixture <new-qa-folder>`, run the API with `SHEET_STUDIO_DATA` pointing there, choose English, CPU only and Birthstone in Settings, confirm review, and open Editor. Use Playwright CLI `run-code --filename scripts/check-editor.js`. Do not run against a real project. Screenshots and downloaded XML are in `output/playwright/`.

Smoosic is isolated in its own frame. Import initializes dynamic constructors and font metrics before conversion; conversion warnings become visible failures instead of saving an upstream fallback score. Browser-native XML parsing is used; the unused legacy `xmldom` dependency is overridden with maintained `@xmldom/xmldom` 0.9.12. The build substitutes local Source fonts for malformed upstream WOFF2 files. Smoosic still emits upstream language/XSLT deprecation warnings in Chromium.
