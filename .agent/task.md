# Bản Nhạc Local (Sheet Studio Local) — Task & Specification

Tài liệu quản lý tác vụ, kiến trúc hệ thống và lộ trình phát triển của ứng dụng **Bản Nhạc Local** (Sheet Studio Local) dành cho AI Agents và đội ngũ phát triển.

---

## 1. Tổng quan & Tầm nhìn dự án

- **Tên dự án:** Bản Nhạc Local (Sheet Studio Local).
- **Mục tiêu cốt lõi:** Ứng dụng local-first, chạy hoàn toàn offline trên Windows 11, tự động phiên âm file âm thanh (WAV, MP3, FLAC) thành bản ký âm lead sheet (giai điệu đơn âm + ký hiệu hợp âm + lời bài hát tùy chọn), cho phép nghe đối chiếu, chỉnh sửa trực quan và xuất ra **MusicXML 4.0**, **MIDI** và **PDF (thông qua MuseScore 4)**.
- **Nguyên tắc kỹ thuật tối thượng:**
  1. **Không giả mạo dữ liệu (No simulated results):** Nếu model AI hoặc phụ thuộc hệ thống chưa sẵn sàng, báo lỗi rõ ràng kèm hướng dẫn khắc phục. Tuyệt đối không sinh dữ liệu nốt giả hoặc giả vờ hoàn thành.
  2. **Quyền riêng tư tuyệt đối (100% Local & Offline):** Không gửi audio hay dữ liệu người dùng lên bất kỳ dịch vụ cloud nào. Toàn bộ model weights, code inference, backend API và frontend assets đều nằm trên ổ đĩa cục bộ. API chỉ bind vào `127.0.0.1`.
  3. **Bảo toàn dữ liệu (Non-destructive & Lossless):** Audio gốc không bao giờ bị can thiệp. Mọi lần lưu chỉnh sửa tạo ra một revision mới bất biến (immutable revision). Tác vụ phân tích mới không ghi đè bản đang chỉnh sửa mà lưu vào bản nháp độc lập (`pending_score_revision`) chờ người dùng kích hoạt.
  4. **Nhạc lý chính xác & Ký âm chuẩn:** Dữ liệu trường độ lưu dưới dạng phân số nốt đen chính xác (phân số hữu tỉ như `"1"`, `"3/2"`, `"1/4"`, không dùng số thực làm tròn). Không tự tiện drop nốt khi có chồng lấn mà cảnh báo để người dùng rà soát.
  5. **Cổng kiểm duyệt tường minh (Explicit Review Gate):** File chỉ được phép xuất (MusicXML, MIDI, PDF) sau khi người dùng bấm xác nhận đã kiểm tra (trạng thái `reviewed`). Bất kỳ thao tác chỉnh sửa nào sau đó đều đưa score về lại trạng thái `needs_review` và khóa đường link tải cũ.

---

## 2. Kiến trúc & Công nghệ

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TRÌNH DUYỆT (FRONTEND)                          │
│  React 19 + TypeScript + Vite (Phong cách Swiss Design, Tiếng Việt)    │
│  • OpenSheetMusicDisplay (OSMD) render SVG khuông nhạc                 │
│  • Web Audio API Synthesizer (6 bộ mẫu âm FluidR3 GM soundfonts)       │
│  • Bảng chỉnh sửa Nốt, Hợp âm, Lời hát, Bộ điều khiển Audio gốc        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST (/api)
                                    │ Cookies: studio_session (Same-origin)
┌───────────────────────────────────▼────────────────────────────────────┐
│                        API SERVER (BACKEND)                            │
│  Python 3.12 + FastAPI + Uvicorn (Bind: 127.0.0.1:8765)                │
│  • schemas.py: Pydantic v2 strict models (ScoreDocument v1)            │
│  • storage.py: SQLite (WAL mode) + JSON file revisions nguyên tử       │
│  • notation.py: music21, mido, MuseScore 4 CLI wrapper                 │
│  • lyrics.py: SRT/LRC parser & syllabic/cue alignment engine           │
│  • transcription.py: Điều phối job giải mã FFmpeg & routing model      │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   ▼                                 ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│       DSP MONOPHONIC ENGINE          │  │     SHEETSAGE2 AI WORKER     │
│  • In-process (NumPy, SciPy)         │  │  • Process riêng (Subprocess)│
│  • Thuật toán YIN pitch detection    │  │  • Python 3.11 (.venv-model) │
│  • Dò cao độ solo sạch 1 nốt         │  │  • PyTorch 2.8 + CUDA 12.6   │
│  • Lưới lượng tử hóa 1/16            │  │  • Hugging Face offline mode │
│  • Không đoán hợp âm (chỉ melody)    │  │  • MERT-v2-FullSong + Adapter│
└──────────────────────────────────────┘  └──────────────────────────────┘
```

---

## 3. Ma trận tính năng & Trạng thái triển khai

| ID | Tính năng / Phân hệ | Chi tiết kỹ thuật | Trạng thái | Ghi chú kiểm thử |
|---|---|---|:---:|---|
| **FEAT-01** | Nhập file âm thanh | Hỗ trợ WAV, MP3, FLAC; dung lượng tối đa 200 MB, thời lượng tối đa 10 phút. Kiểm tra hợp lệ qua FFmpeg/ffprobe. | **HOÀN THÀNH** | Đã pass kiểm thử với file thật và file tổng hợp. |
| **FEAT-02** | Quản lý dự án & Thùng rác | Tạo, liệt kê, đổi tên, xóa mềm (chuyển vào Thùng rác) và khôi phục (Restore). Dữ liệu audio và revisions được bảo toàn nguyên vẹn. | **HOÀN THÀNH** | Kiểm tra chặn xóa khi job đang chạy, bảo toàn dữ liệu khi khôi phục. |
| **FEAT-03** | Engine Monophonic DSP | Phân tích cao độ giai điệu đơn âm bằng thuật toán YIN, lọc nhiễu trung vị (median filter), lượng tử hóa lưới 1/16. Không đoán hợp âm giả mạo. | **HOÀN THÀNH** | Đã test dò đúng cao độ chuỗi thang âm mẫu C4–C5. |
| **FEAT-04** | Engine SheetSage2 AI | Chạy mô hình transformer phiên âm giai điệu và hợp âm trong subprocess cách ly Python 3.11, PyTorch + CUDA, nạp weights offline có kiểm tra SHA-256. | **HOÀN THÀNH** | Đã test smoke 4s và file thực tế 479s (303 nốt, 164 hợp âm) trên RTX 3060 12GB. |
| **FEAT-05** | Quản lý Revision bất biến | Bản nhạc lưu dưới dạng JSON có revision tăng dần (`1.json`, `2.json`...). Kiểm soát tương tranh lạc quan (`expected_revision`). Ghi file nguyên tử (`atomic_json`). | **HOÀN THÀNH** | Không thể ghi đè nếu revision không khớp (HTTP 409). |
| **FEAT-06** | Nhập lời hát (Lyrics) SRT / LRC | Hỗ trợ upload SRT hoặc LRC (kèm Enhanced LRC). Tự động phân đoạn câu, căn nốt theo mốc thời gian, giữ lại từ chưa gắn nốt. Cho phép đính kèm trước khi phân tích hoặc nhập sau. | **HOÀN THÀNH** | Đã test mã hóa UTF-8/BOM/UTF-16, offset âm/dương, sửa nốt liên kết. |
| **FEAT-07** | Hiển thị khuông nhạc SVG | Tích hợp thư viện OpenSheetMusicDisplay (OSMD), tự động co giãn theo chiều rộng cửa sổ, hiển thị đầy đủ nốt, vạch nhịp, hợp âm, lời hát, khóa Sol. | **HOÀN THÀNH** | Render mượt mà, hỗ trợ zoom, không rò rỉ bộ nhớ khi unmount/resize. |
| **FEAT-08** | Nghe thử đa nhạc cụ (Soundfonts) | Web Audio API phát giai điệu nạp từ 6 bộ soundfonts SFZ/OGG cục bộ (Piano, Guitar, Violin, Flute, Clarinet, Contrabass) từ FluidR3 GM. | **HOÀN THÀNH** | Chạy offline hoàn toàn, có compressor chống vỡ tiếng, hủy voice sạch sẽ khi dừng. |
| **FEAT-09** | Bảng chỉnh sửa Nốt & Hợp âm | Giao diện bảng tabular cho phép thêm, xóa, sửa cao độ MIDI, vị trí, trường độ, cường độ nốt, loại hợp âm (chord, no_chord, unknown), nốt gốc, nốt bass. Có ngăn xếp Undo. | **HOÀN THÀNH** | Ràng buộc phân số chặt chẽ, tự động chuyển trạng thái sang `needs_review`. |
| **FEAT-10** | Chuyển giọng (Transpose) | Chuyển toàn bộ bản nhạc theo số bán âm (−12 đến +12), tự động đổi cao độ nốt, giọng (key signature), nốt gốc và nốt bass hợp âm, lưu thành revision mới. | **HOÀN THÀNH** | Đã kiểm thử tính nhất quán của vòng bậc năm và chính tả nốt hóa (spelling). |
| **FEAT-11** | Xuất MusicXML 4.0 | Xuất file `.musicxml` đạt chuẩn định dạng, phân chia ô nhịp, dấu lặng, nối nốt (tie) qua vạch nhịp, phân số/triplet, hợp âm chuẩn và lời hát đúng âm tiết (syllabic). | **HOÀN THÀNH** | Đã kiểm thử MusicXML round-trip không mất mát thông tin. |
| **FEAT-12** | Xuất MIDI | Xuất file `.mid` chuẩn MIDI Type 1 qua thư viện `mido`. Tùy chọn xuất thêm track bè đệm hợp âm tổng hợp để tham khảo khi tập hoặc đưa vào DAW. | **HOÀN THÀNH** | Đảm bảo logic note_off trước note_on với nốt liên tiếp cùng cao độ. |
| **FEAT-13** | Xuất PDF qua MuseScore 4 | Gọi MuseScore 4 chế độ dòng lệnh không cửa sổ (`-o output.pdf input.musicxml`), hỗ trợ font Unicode tiếng Việt, dàn trang A4 chuẩn xác. | **HOÀN THÀNH** | Đã test trên Windows 11 với bản MuseScore 4 cài đặt tại Program Files. |
| **FEAT-14** | Bảo vệ API & An ninh mạng | Khóa bind loopback `127.0.0.1`, chặn truy cập cross-origin, xác thực phiên bằng cookie bí mật `studio_session`, kiểm tra TrustedHost, vô hiệu hóa caching HTTP API. | **HOÀN THÀNH** | Đã test chặn origin lạ, chặn bypass cookie, chặn method nguy hiểm. |
| **FEAT-15** | Xuất định dạng ABC Notation (`score.abc`) | Xuất file `score.abc` đạt chuẩn ABC 2.1 (header `X:`, `T:`, `M:`, `L: 1/16`, `Q:`, `K:`), chuyển đổi cao độ MIDI sang ký âm ABC chuẩn kèm dấu thăng/giáng, nốt nối `-`, dấu lặng `z`, hợp âm `"..."`, lời hát `w:`. | **HOÀN THÀNH** | Đã viết unit test và integration test qua API, trả về đúng filename `score.abc`. |
| **FEAT-16** | Cấu hình xuất bài hát & trích đoạn | Cho phép chọn phạm vi xuất: Toàn bộ bài hát (`scope="full"`) hoặc khoảng ô nhịp (`scope="range"`, `bar_start`, `bar_end`), tùy chọn bật/tắt hợp âm (`include_chords`), lời bài hát (`include_lyrics`), bè đệm MIDI (`accompaniment`). | **HOÀN THÀNH** | Đã test trên cả 4 định dạng xuất (MusicXML, MIDI, PDF, ABC) và giao diện người dùng. |
| **FEAT-17** | Dọn dẹp thùng rác vĩnh viễn (Purge Trash) | Xóa vĩnh viễn toàn bộ các dự án trong thùng rác: dọn sạch bản ghi SQLite (`deleted_projects`, `artifacts`, `lyric_inputs`, `scores`, `jobs`, `projects`) và xóa thư mục vật lý `data/projects/{id}` trên đĩa cứng; có hộp thoại cảnh báo người dùng. | **HOÀN THÀNH** | Đã kiểm thử `test_delete_and_empty_trash` và API endpoint `POST /api/projects/empty-trash`. |
| **FEAT-18** | Giao diện Sáng / Tối (Light & Dark Theme) | Hệ thống biến CSS ngữ nghĩa (`:root` và `[data-theme="dark"]`), nút toggle nhanh Sun/Moon trên topbar, lưu trữ trạng thái vào `localStorage`, tự động nhận diện `prefers-color-scheme`, đồng bộ bảng nốt, hợp âm, thanh điều khiển âm thanh và OpenSheetMusicDisplay (OSMD SVG filter inversion). | **HOÀN THÀNH** | Đã kiểm thử chuyển đổi mượt mà, typography Swiss Design sắc nét trên cả hai nền. |
| **FEAT-19** | Tự động phân tích sau khi upload (Auto-Analyze) | Ngay sau khi chọn hoặc kéo thả tệp âm thanh (WAV, MP3, FLAC), hệ thống tự động kích hoạt API `/analyze` với các thiết lập hiện tại mà không bắt người dùng bấm nút thủ công; có checkbox toggle `[AUTO]` trực quan tại mục Thiết lập âm nhạc và lưu trạng thái vào `localStorage`. | **HOÀN THÀNH** | Đã tích hợp vào luồng `upload()` và giao diện Inspector. |

---

## 4. Hợp đồng dữ liệu & Cấu trúc ScoreDocument

### 4.1 Schema ScoreDocument (v1)

```typescript
interface ScoreDocument {
  schema_version: 1;
  revision: number;                        // Tăng dần: 1, 2, 3...
  title: string;                           // 1 - 200 ký tự
  tempo: number;                           // 20 - 300 BPM
  meter: [number, number];                 // Ví dụ: [4, 4], [3, 4], [6, 8]
  key: string;                             // Ví dụ: "C", "G", "Am", "F#m"
  notes: Note[];                           // Tối đa 20.000 nốt
  harmonies: Harmony[];                    // Tối đa 5.000 hợp âm
  lyrics: LyricToken[];                    // Tối đa 20.000 từ/âm tiết
  lyric_source?: LyricSource | null;       // Metadata file SRT/LRC đã import
  diagnostics: string[];                   // Cảnh báo nhạc lý, chồng lấn, v.v.
  source_engine: string;                   // "sheetsage2", "monophonic", "manual"
  review_status: 'needs_review' | 'reviewed'; // Cổng kiểm duyệt trước xuất file
  melody_role: 'instrumental' | 'vocal';   // Bè giai điệu chính
}

interface Note {
  id: string;                              // Định danh duy nhất
  pitch: number;                           // Cao độ MIDI: 0 - 127 (C4 = 60)
  start: string;                           // Phân số nốt đen toàn bài, ví dụ "0", "3/2"
  duration: string;                        // Phân số nốt đen dương, ví dụ "1", "1/4"
  velocity: number;                        // 1 - 127 (mặc định 80-88)
  source_start: number | null;             // Giây bắt đầu trong audio gốc
  source_end: number | null;               // Giây kết thúc trong audio gốc
}

interface Harmony {
  id: string;
  root: string;                            // "C", "C#", "Db", "D"...
  quality: 'major' | 'minor' | 'dominant-seventh' | 'major-seventh' |
           'minor-seventh' | 'diminished' | 'augmented' |
           'suspended-second' | 'suspended-fourth';
  bass: string | null;                     // Hợp âm đảo / slash bass (ví dụ "G" trong C/G)
  start: string;                           // Phân số nốt đen toàn bài
  duration: string;                        // Phân số nốt đen
  kind: 'chord' | 'no_chord' | 'unknown';  // Rõ ràng giữa N.C và chưa nhận diện
}

interface LyricToken {
  id: string;
  text: string;                            // 1 - 200 ký tự, không chứa ký tự điều khiển
  note_id: string | null;                  // ID nốt gắn kèm (null nếu chưa khớp)
  verse: number;                           // Khổ lời: 1 - 20
  syllabic: 'single' | 'begin' | 'middle' | 'end'; // Quy chuẩn gạch nối MusicXML
  source_start: number | null;             // Mốc giây từ phụ đề SRT/LRC
  source_end: number | null;
}
```

---

## 5. Danh sách API Endpoints

- `GET /api/health`: Kiểm tra trạng thái runtime, FFmpeg, MuseScore 4, GPU, danh sách models. Đồng thời cấp cookie `studio_session`.
- `GET /api/projects?deleted=false|true`: Liệt kê các dự án hiện có hoặc các dự án trong thùng rác.
- `POST /api/projects`: Upload audio mới (`multipart/form-data`: file, title).
- `GET /api/projects/{id}`: Chi tiết dự án, tiến độ job mới nhất, metadata lời staged.
- `DELETE /api/projects/{id}`: Xóa mềm dự án vào thùng rác.
- `POST /api/projects/{id}/restore`: Khôi phục dự án từ thùng rác.
- `GET /api/projects/{id}/audio`: Stream file audio gốc phục vụ trình phát.
- `POST /api/projects/{id}/lyrics-source`: Đính kèm file SRT/LRC trước khi chạy phân tích.
- `POST /api/projects/{id}/analyze`: Khởi chạy job phân tích audio (`engine`, `tempo`, `meter`, `key`, `melody_role`).
- `GET /api/jobs/{id}`: Kiểm tra tiến độ job phân tích (status, stage, message, error).
- `POST /api/jobs/{id}/cancel`: Hủy bỏ job đang chạy.
- `GET /api/projects/{id}/score?revision=N`: Lấy dữ liệu ScoreDocument của revision chỉ định (hoặc mới nhất).
- `PUT /api/projects/{id}/score`: Lưu chỉnh sửa bản nhạc (yêu cầu `expected_revision`).
- `POST /api/projects/{id}/lyrics`: Upload file SRT/LRC đính kèm vào bản nhạc hiện tại.
- `POST /api/projects/{id}/transpose`: Chuyển giọng toàn bài (số bán âm).
- `POST /api/projects/{id}/review`: Đánh dấu xác nhận bản nhạc đã được kiểm tra (`reviewed`).
- `GET /api/projects/{id}/preview?revision=N`: Trả về MusicXML động để OSMD render xem trước (không tạo artifact).
- `POST /api/projects/{id}/activate-score`: Kích hoạt bản phân tích mới (`pending_score_revision`) thành bản chính.
- `POST /api/projects/empty-trash`: Xóa vĩnh viễn toàn bộ các dự án trong thùng rác và giải phóng dung lượng đĩa cứng.
- `POST /api/projects/{id}/exports`: Xuất bản nhạc ra file (`musicxml`, `midi`, `pdf`, `abc`). Hỗ trợ cấu hình `scope: full | range`, `bar_start`, `bar_end`, `include_chords`, `include_lyrics`, `accompaniment`, `custom_title`. Trả về `score.abc` khi xuất ABC. Chỉ cho phép khi score đã `reviewed`.
- `GET /api/artifacts/{id}`: Tải file artifact đã xuất.

---

## 6. Tiêu chí nghiệm thu & Kiểm thử (Quality Gates)

1. **Kiểm thử tự động (Unit & Integration Tests):**
   - Chạy lệnh: `.venv\Scripts\python.exe -m pytest -q --basetemp=tmp/pytest -p no:cacheprovider`
   - Đảm bảo **140/140 tests passed** (100% xanh), bao gồm toàn bộ test cho: `test_api.py`, `test_audio_analysis.py`, `test_editor.py`, `test_lyrics.py`, `test_lyrics_api.py`, `test_notation.py`, `test_queue.py`, `test_storage.py`, `test_transcription.py`. Đã khắc phục triệt để lỗi làm sạch thẻ phụ đề SRT ASS (`{\an8}`).
2. **Build giao diện (Frontend Production Build):**
   - Chạy lệnh: `cd frontend && npm run build`
   - Đảm bảo biên dịch TypeScript thành công (`tsc -b`), đóng gói Vite sạch sẽ không lỗi bundle.
3. **Smoke Test Model AI:**
   - Chạy script: `.venv-model\Scripts\python.exe workers/smoke_model.py`
   - Đảm bảo nạp snapshot SheetSage2 và MERT-v2 thành công, chạy inference đoạn mẫu và giải phóng bộ nhớ.

---

## 7. Lộ trình phát triển tương lai (Phase 2 Roadmap)

- [ ] **P2-01 (ML):** Nghiên cứu và đánh giá mô hình phân tích đa nhạc cụ (như MuScriptor) so sánh với baseline SheetSage2.
- [ ] **P2-02 (ML):** Thử nghiệm pipeline tách nguồn âm thanh (Source Separation: Demucs / Spleeter) trước khi chuyển vào mô hình phiên âm AMT nhằm nâng cao độ chuẩn xác cho giai điệu giọng hát.
- [ ] **P2-03 (Notation):** Hỗ trợ khuông nhạc Piano hai tay (Grand Staff - Treble/Bass split) và ký âm bộ gõ (Percussion).
- [ ] **P2-04 (Notation):** Hỗ trợ chuyển giọng nhạc cụ đặc thù (Transposing instruments như Trumpet/Clarinet Bb, Alto Sax Eb).
- [ ] **P2-05 (Notation):** Hỗ trợ tab Guitar (Guitar TAB), chỉnh thế bấm (fingering), Capo và các kiểu ký âm hợp âm nâng cao.
- [ ] **P2-06 (Frontend):** Bổ sung trình biên tập nốt tương tác kéo thả trực tiếp trên SVG khuông nhạc (Interactive OSMD canvas editing).
