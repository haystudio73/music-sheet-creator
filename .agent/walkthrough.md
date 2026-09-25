# Bản Nhạc Local (Sheet Studio Local) — Hướng Dẫn Vận Hành & Kiến Trúc Chi Tiết (Walkthrough)

Tài liệu hướng dẫn chi tiết toàn bộ kiến trúc, quy trình vận hành từ đầu đến cuối (End-to-End Walkthrough) và cẩm nang kỹ thuật của dự án **Bản Nhạc Local** (Sheet Studio Local).

---

## 1. Sơ đồ Kiến trúc & Luồng Dữ liệu Tổng thể

Dự án được xây dựng theo mô hình **Local-first**, cô lập hoàn toàn với Internet trong quá trình suy luận và xử lý dự án. Dưới đây là luồng xử lý từ file âm thanh thô đến bản nhạc hoàn chỉnh:

```mermaid
sequenceDiagram
    autonumber
    actor User as Người dùng
    participant UI as Giao diện Web (React/Vite)
    participant API as FastAPI Backend (Port 8765)
    participant DB as SQLite & File Storage
    participant Worker as Engine Phân tích (DSP / ML)
    participant Notation as Engine Ký âm (music21 / MuseScore)

    User->>UI: Kéo thả file audio (WAV/MP3/FLAC) & SRT/LRC tùy chọn
    UI->>API: POST /api/projects (Multipart Audio)
    API->>API: Probe audio bằng FFmpeg (kiểm tra codec, duration <= 10m)
    API->>DB: Lưu audio gốc vào data/projects/{id}/original/ & metadata SQLite
    API-->>UI: Trả về Project metadata

    User->>UI: Chọn engine, tempo, số chỉ nhịp, giọng -> Bắt đầu phân tích
    UI->>API: POST /api/projects/{id}/analyze
    API->>DB: Tạo Job (status: queued -> running)
    API->>Worker: Điều phối giải mã FFmpeg -> PCM Float32
    alt Monophonic DSP
        Worker->>Worker: Dò cao độ YIN + Lọc median + Lưới 1/16
    else SheetSage2 AI
        Worker->>Worker: Chạy Subprocess Python 3.11 (PyTorch + CUDA)
    end
    Worker-->>API: Trả về events thô (notes + chords)
    API->>DB: Lưu ScoreDocument Revision 1 (Trạng thái: needs_review)
    API->>DB: Cập nhật Job (status: completed)

    UI->>API: GET /api/projects/{id}/score & GET /preview
    API->>Notation: Tạo MusicXML động phục vụ preview
    API-->>UI: ScoreDocument JSON & MusicXML inline
    UI->>UI: OSMD render SVG khuông nhạc; Web Audio nạp mẫu âm phát thử

    User->>UI: Nghe A/B đối chiếu, chỉnh nốt, sửa hợp âm, gắn lời -> Bấm Lưu
    UI->>API: PUT /api/projects/{id}/score (expected_revision: 1)
    API->>DB: Lưu ScoreDocument Revision 2 nguyên tử (atomic JSON)

    User->>UI: Bấm "Xác nhận đã kiểm tra"
    UI->>API: POST /api/projects/{id}/review
    API->>DB: Chuyển review_status = 'reviewed' -> Mở khóa các nút xuất file

    User->>UI: Bấm tải MusicXML / MIDI / PDF / ABC (score.abc)
    UI->>API: POST /api/projects/{id}/exports (kèm options: scope, chords, lyrics, accompaniment)
    alt MusicXML
        API->>Notation: Ghi file .musicxml chuẩn 4.0
    else MIDI
        API->>Notation: Tạo track giai điệu + bè đệm hợp âm bằng mido
    else PDF
        API->>Notation: Gọi MuseScore 4 CLI chế độ ẩn cửa sổ render PDF
    else ABC
        API->>Notation: Xuất file score.abc chuẩn ABC 2.1 gọn nhẹ
    end
    API-->>UI: Đường dẫn Artifact (/api/artifacts/{id}, file score.abc)
    UI-->>User: Tải file về máy
```

---

## 2. Chuẩn bị Môi trường & Khởi động Ứng dụng

### 2.1 Yêu cầu hệ thống
- **Hệ điều hành:** Windows 11 64-bit.
- **Phần cứng:** Khuyến nghị GPU NVIDIA (tối ưu RTX 3060 12 GB VRAM hoặc tương đương để chạy SheetSage2), RAM tối thiểu 16 GB (khuyến nghị 32 GB), ổ đĩa trống từ 15 GB trở lên.
- **Công cụ bên ngoài:**
  - **FFmpeg & ffprobe:** Phải nằm trong biến môi trường `PATH` (hoặc cấu hình qua biến `FFMPEG_PATH`).
  - **MuseScore 4:** Cài đặt mặc định tại `C:\Program Files\MuseScore 4\bin\MuseScore4.exe` (hoặc cấu hình qua `MUSESCORE_PATH`) để xuất PDF.
  - **Node.js:** Phiên bản 22 trở lên (dùng để build giao diện Vite/React).
  - **Python:** Khuyến nghị Python 3.12 (cho backend API) và Python 3.11 (cho worker model).

### 2.2 Các bước cài đặt tự động
Mở PowerShell tại thư mục gốc dự án:

1. **Cài đặt môi trường Backend & Frontend:**
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
   ```
   *Lệnh này sẽ tạo môi trường ảo `.venv` (Python 3.12), cài đặt các thư viện trong `requirements.lock`, cài đặt npm packages trong thư mục `frontend` và biên dịch giao diện vào `frontend/dist`.*

2. **Cài đặt Model SheetSage2 & MERT-v2 (Tùy chọn nếu dùng AI):**
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-model.ps1
   ```
   *Lệnh này sẽ tạo môi trường ảo `.venv-model` (Python 3.11), cài đặt PyTorch với CUDA 12.6, tải snapshot mô hình được ghim phiên bản (pinned commit) và xác thực mã băm SHA-256.*

### 2.3 Khởi động ứng dụng
Chạy file batch:
```cmd
Start.cmd
```
Hoặc chạy bằng PowerShell:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1
```
Ứng dụng sẽ tự động mở trình duyệt tại: **`http://127.0.0.1:8765`**.

---

## 3. Quy trình 4 Bước Trải nghiệm Người dùng (Step-by-Step User Journey)

Giao diện ứng dụng được thiết kế theo phong cách **Swiss Design** tối giản, trực quan với 4 bước tuần tự rõ ràng:

### Bước 1: Nhập dữ liệu (Upload & Staged Lyrics)
- **Hành động:** Người dùng kéo thả hoặc nhấn chọn tệp âm thanh (WAV, MP3, FLAC) tối đa 200 MB / 10 phút.
- **Đính kèm lời hát tùy chọn:** Trước khi phân tích, người dùng có thể tải file `.srt` hoặc `.lrc` và chỉnh độ lệch thời gian (Offset) nếu muốn lời hát tự động gắn vào các nốt giai điệu sau khi phân tích.
- **Cơ chế:** Backend sử dụng `ffprobe` để đo thời lượng, kiểm tra luồng audio hợp lệ và tính mã hash SHA-256 để định danh file trong thư mục `data/projects/{id}/original/`.

### Bước 2: Phân tích âm nhạc (Analysis Configuration)
- **Lựa chọn Engine:**
  - **SheetSage2 · Hugging Face:** Sử dụng AI để tách giai điệu và dự đoán hợp âm từ bản phối hoàn chỉnh.
  - **Giai điệu đơn · DSP thử nghiệm:** Phù hợp cho file solo một nhạc cụ sạch từng nốt (sử dụng thuật toán YIN, không dự đoán hợp âm).
- **Thiết lập tham số:** Người dùng chọn Tempo (BPM), Số chỉ nhịp (4/4, 3/4, 6/8...), Giọng (Key) và Bè giai điệu chính (**Nhạc cụ** hoặc **Giọng hát**).
- **Hủy tác vụ:** Người dùng có thể nhấn nút **Dừng** bất kỳ lúc nào để hủy tiến trình mà không làm hỏng dự án.

### Bước 3: Kiểm tra, Nghe đối chiếu & Chỉnh sửa (Review & Edit)
Khi quá trình phân tích hoàn tất, giao diện hiển thị 4 tab làm việc:
1. **Khuông nhạc (Sheet Tab):** Hiển thị bản ký âm SVG thời gian thực qua OpenSheetMusicDisplay (OSMD).
2. **Trình phát âm thanh kép:**
   - **Audio gốc:** Trình phát thanh điều khiển audio gốc với thanh trượt mốc thời gian, nút phát lại từ đầu và tùy chỉnh tốc độ phát (0.5x, 0.75x, 1x, 1.25x).
   - **Bản nghe thử nốt:** Bộ tổng hợp âm Web Audio sử dụng 6 bộ mẫu âm thực (Acoustic Grand Piano, Nylon Guitar, Violin, Flute, Clarinet, Contrabass) đóng gói cục bộ từ thư viện FluidR3 GM.
3. **Bảng chỉnh sửa Giai điệu (Notes Tab):** Sửa cao độ MIDI (0–127), vị trí nốt (phân số nốt đen), trường độ, cường độ (velocity). Hỗ trợ nút Hoàn tác (Undo).
4. **Bảng chỉnh sửa Hợp âm (Harmonies Tab):** Sửa loại hợp âm (Hợp âm, Không hợp âm, Chưa xác định), nốt gốc (Root), tính chất (Trưởng, Thứ, 7, maj7, m7, dim, aug, sus2, sus4) và nốt bass đảo.
5. **Bảng chỉnh sửa Lời hát (Lyrics Tab):** Gắn từng từ/âm tiết vào nốt nhạc, phân chia khổ (verse), đánh dấu loại âm tiết (Đầu, Giữa, Cuối, Đơn). Lọc nhanh các từ chưa gắn nốt.
6. **Công cụ Chuyển giọng (Transpose):** Chuyển toàn bộ bài hát lên/xuống từ −12 đến +12 bán âm. Toàn bộ nốt, hợp âm và giọng sẽ được đồng bộ.

### Bước 4: Xác nhận Kiểm tra & Xuất file (Export Gate & Full Song Settings)
- **Khóa an toàn:** Các nút tải file ban đầu đều bị vô hiệu hóa. Người dùng phải bấm **"Xác nhận đã kiểm tra"** để chuyển `review_status` sang `reviewed`.
- **Nếu tiếp tục chỉnh sửa:** Bất kỳ thao tác lưu mới nào đều tự động đưa trạng thái trở lại `needs_review` và vô hiệu hóa các liên kết tải cũ.
- **Cấu hình xuất bản nhạc (Export Settings):**
  - **Phạm vi xuất:** Chọn xuất **Toàn bộ bài hát** (`scope="full"`, mặc định) hoặc **Trích đoạn theo ô nhịp** (`scope="range"`, nhập ô bắt đầu `bar_start` và ô kết thúc `bar_end`).
  - **Kèm ký hiệu hợp âm:** Checkbox bật/tắt hiển thị hợp âm trên bản xuất.
  - **Kèm lời bài hát:** Checkbox bật/tắt gắn lời hát vào nốt trên bản xuất.
  - **Thêm hợp âm đệm vào MIDI:** Bật track bè đệm hòa âm tổng hợp khi xuất MIDI.
- **Định dạng hỗ trợ:**
  - **MusicXML (.musicxml):** Xuất bản ký âm chuẩn công nghiệp để tiếp tục chỉnh sửa trên MuseScore, Sibelius, Finale.
  - **MIDI (.mid):** Xuất file MIDI nốt giai điệu chuẩn, có tùy chọn thêm bè đệm hợp âm tổng hợp.
  - **PDF (.pdf):** Gọi MuseScore 4 biên dịch trực tiếp ra bản in A4 chất lượng cao với tiêu đề tiếng Việt chuẩn nét.
  - **ABC Notation (`score.abc`):** File ký âm chuẩn văn bản ABC 2.1 siêu gọn nhẹ, dễ dàng xem nhanh, nhúng web hoặc mở trong các công cụ hỗ trợ ABC notation.

---

### Tiện ích Hệ thống: Giao diện Sáng/Tối & Dọn dẹp Thùng rác
1. **Chế độ Sáng / Tối (Light & Dark Mode):**
   - Nút chuyển đổi nhanh biểu tượng Mặt trời / Mặt trăng trên thanh công cụ trên cùng (topbar).
   - Tự động nhận diện thiết lập theme của hệ điều hành (`prefers-color-scheme`) và lưu cấu hình vào `localStorage`.
   - Toàn bộ bảng màu Swiss Design (Cobalt Blue, Surface, Neutral Ink) được ánh xạ động qua hệ biến CSS Semantic.
   - Bản nhạc SVG (OpenSheetMusicDisplay) được tự động nghịch đảo màu (`filter: invert(0.92) hue-rotate(180deg)`) trên nền tối mà vẫn đảm bảo độ sắc nét của nốt, vạch nhịp và chữ.
2. **Dọn dẹp Thùng rác vĩnh viễn (Empty Trash):**
   - Trong mục **Thùng rác** ở thanh bên (Sidebar), khi có dự án bị xóa mềm, nút **Dọn dẹp** (kèm icon thùng rác và màu cảnh báo đỏ) sẽ xuất hiện.
   - Khi bấm, ứng dụng hiển thị hộp thoại xác nhận số lượng dự án sẽ bị xóa vĩnh viễn.
   - Sau khi xác nhận, backend gọi `POST /api/projects/empty-trash` để xóa sạch toàn bộ metadata SQLite và xóa triệt để thư mục dữ liệu trên đĩa (`data/projects/{id}`), giải phóng dung lượng ổ cứng.
3. **Tự động phân tích sau khi upload (Auto-Analyze):**
   - Ngay sau khi người dùng kéo thả hoặc tải lên tệp âm thanh (WAV, MP3, FLAC), ứng dụng tự động gọi `POST /api/projects/{id}/analyze` với các thiết lập hiện tại.
   - Người dùng không phải mất thêm thao tác bấm nút "Bắt đầu phân tích" thủ công.
   - Tùy chọn này được đánh dấu bằng huy hiệu `AUTO` nổi bật ngay trên khung "Thiết lập âm nhạc" ở thanh bên phải (Inspector), có checkbox cho phép bật/tắt linh hoạt và tự động ghi nhớ trạng thái vào `localStorage`.

---

## 4. Chi tiết Kỹ thuật các Phân hệ Cốt lõi

### 4.1 Quản lý Dữ liệu & SQLite Schema (`backend/storage.py`)
Cơ sở dữ liệu SQLite cục bộ được kích hoạt chế độ **WAL (Write-Ahead Logging)** để tối ưu tốc độ đọc ghi đồng thời:
- `projects`: Chứa thông tin id, title, timestamps, thời lượng, trạng thái (`ready`, `analyzing`, `draft`, `reviewed`, `failed`), `score_revision` hiện tại và `pending_score_revision`.
- `scores`: Ánh xạ `(project_id, revision)` tới đường dẫn file JSON tương ứng trên đĩa (`data/projects/{id}/scores/{revision}.json`). Việc lưu file sử dụng hàm `atomic_json` ghi ra file `.tmp` trước khi đổi tên (`os.replace`) để chống hỏng file khi mất điện đột ngột.
- `jobs`: Quản lý tiến trình xử lý nền (stage, message, error, timestamps).
- `artifacts`: Quản lý các file xuất (MusicXML, MIDI, PDF, ABC) gắn với từng revision cụ thể.
- `deleted_projects`: Quản lý các dự án bị xóa mềm (Thùng rác), cho phép khôi phục bất cứ lúc nào hoặc dọn dẹp triệt để bằng `Store.empty_trash()`.

### 4.2 Mô hình MERT-v2-FullSong & Kiến trúc SheetSage2 (`workers/sheetsage2_worker.py`)
- **Nghiên cứu về `m-a-p/MERT-v2-FullSong`:**
  - `MERT-v2-FullSong` là mô hình biểu diễn âm thanh tự giám sát (self-supervised acoustic representation model) quy mô lớn với **632 triệu tham số (632M params)** được phát triển bởi Music Audio Pre-training (M-A-P).
  - Kiến trúc bao gồm: Tầng trích xuất đặc trưng ConvNeXt với tỷ lệ nhảy 960x subsampling từ tín hiệu âm thanh 24.000 Hz, đưa vào **24 lớp Conformer** với Rotary Position Embedding (RoPE), xử lý chuỗi ngữ cảnh siêu dài (lên tới 300 giây/5 phút âm thanh nguyên bài) và sinh ra chuỗi vector đặc trưng 1024 chiều ở tần số 25 Hz.
  - **Quan hệ với SheetSage2 trong ứng dụng:** `MERT-v2-FullSong` **không phải là mô hình giải mã symbolic độc lập** (nó không trực tiếp tạo ra nốt hay hợp âm). Thay vào đó, nó đóng vai trò là **frozen acoustic backbone encoder**. `SheetSage2` đóng băng (freeze) MERT-v2 để trích xuất đặc trưng âm học, sau đó đưa qua các adapter decoder chuyên biệt (Melody Decoder & Chord Decoder) để dự đoán nốt nhạc và ký hiệu hợp âm.
  - Snapshot mô hình được ghim cục bộ tại `.cache/model-snapshots/mert2` và `.cache/model-snapshots/sheetsage2`. Khi người dùng chọn engine **SheetSage2** trong ứng dụng, worker nền tảng đang kích hoạt chính `MERT-v2-FullSong` làm động cơ trích xuất âm học.

### 4.3 Engine Ký âm MusicXML, MuseScore 4 & ABC 2.1 (`backend/notation.py`)
- **Phân chia ô nhịp & Tùy chọn phạm vi:** Hàm tính toán ô nhịp hỗ trợ cắt lát chính xác theo `bar_start` và `bar_end`, tính lại offset mốc thời gian về 0 tương ứng với ô nhịp bắt đầu.
- **Engine xuất ABC Notation 2.1 (`export_abc`):**
  - Sinh tiêu đề chuẩn ABC 2.1: `X: 1`, `T: {title}`, `M: {beats}/{type}`, `L: 1/16` (chia lưới nốt móc kép integer), `Q: 1/4={tempo}`, `K: {key}`.
  - Ánh xạ cao độ MIDI sang hệ thống ký hiệu ABC: MIDI 60 $\to$ `C`, MIDI 72 $\to$ `c`, các quãng tám cao hơn dùng dấu `'` (`c'`), các quãng tám thấp hơn dùng dấu `,` (`C,`).
  - Hỗ trợ dấu thăng (`^`), dấu giáng (`_`), dấu lặng (`z`), nốt nối (`-`) và vạch nhịp kép kết thúc bài (`|]`).
  - Đặt nhãn hợp âm trong ngoặc kép `"..."` trước nốt đánh phách, và lời bài hát ngay dưới dòng nhạc qua tiền tố `w:`.
- **MuseScore Headless Export:** Chạy lệnh `MuseScore4.exe -o target.pdf source.musicxml`. Trên Windows, thiết lập cờ `CREATE_NO_WINDOW` và `STARTF_USESHOWWINDOW` để ẩn hoàn toàn cửa sổ pop-up của MuseScore, thiết lập timeout 120 giây an toàn.

---

## 5. Hướng Dẫn Kiểm Thử & Xác Nhận (Verification Guide)

### 5.1 Chạy Test Suite Backend
Bộ kiểm thử tự động gồm **140 test case** bao phủ toàn bộ các module:
```powershell
.venv\Scripts\python.exe -m pytest -q --basetemp=tmp/pytest -p no:cacheprovider
```
*Kết quả kiểm thử: `140 passed, 2 warnings` (100% pass).*

Các khía cạnh đã được kiểm chứng tự động:
- **API & Security:** Xác thực session cookie, chống CSRF, ngăn chặn path traversal, chặn truy cập dự án trong thùng rác.
- **Transcription & Queue:** Giải mã qua FFmpeg thật, kiểm tra thuật toán YIN, kiểm tra hàng đợi FIFO và giới hạn 1 tác vụ/IP.
- **Notation & Editor:** Kiểm tra tính toàn vẹn khi round-trip MusicXML, xử lý dấu hóa, hợp âm slash chord, nốt nối qua ô nhịp, kiểm tra export MIDI với track bè đệm; lưu và mở lại bản sửa đổi trong Editor MusicXML, kiểm soát phiên bản độc lập.
- **Lyrics:** Kiểm tra phân tích cú pháp SRT/LRC đa dạng (UTF-8, UTF-16, BOM), tính toán độ lệch thời gian (offset), căn chỉnh lời hát và nốt; loại bỏ sạch sẽ các thẻ định dạng phụ đề ASS (`{\an8}`) và HTML entities.

### 5.2 Kiểm tra Build Frontend
Đảm bảo mã nguồn TypeScript không có lỗi kiểu dữ liệu và đóng gói giao diện thành công:
```powershell
cd frontend
npm run build
```
*Kết quả kỳ vọng: `✓ built in ~4.5s` sinh ra thư mục `frontend/dist` hoàn chỉnh.*

### 5.3 Tạo file âm thanh mẫu để kiểm tra thực tế
Để tạo một file WAV mẫu chuẩn âm thanh thang âm C4–C5 kèm nhãn nốt tham chiếu:
```powershell
.venv\Scripts\python.exe scripts/make_test_audio.py
```
File kết quả sẽ được tạo tại `data/test_scale.wav`.

---

## 6. Xử lý Sự Cố & Câu Hỏi Thường Gặp (Troubleshooting & FAQ)

| Vấn đề gặp phải | Nguyên nhân có thể | Cách khắc phục |
|---|---|---|
| **Lỗi: "Chưa có ffprobe/ffmpeg"** | FFmpeg chưa được cài hoặc chưa có trong biến môi trường `PATH`. | Tải FFmpeg, giải nén và thêm thư mục `bin` vào `PATH` của Windows, hoặc gán biến môi trường `set FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe`. |
| **Không xuất được PDF (Nút PDF mờ)** | Chưa cài đặt MuseScore 4 trên máy. | Cài đặt MuseScore 4 từ trang chủ. Nếu cài đặt ở đường dẫn khác mặc định, gán biến `MUSESCORE_PATH`. Các nút MusicXML và MIDI vẫn hoạt động bình thường. |
| **GPU Out of Memory (OOM) khi chạy SheetSage2** | VRAM của card đồ họa không đủ (thường cần >= 8–10 GB VRAM trống). | Đóng các ứng dụng đồ họa nặng hoặc game đang chạy. Lưu ý: SheetSage2 tự động đệm (pad) cửa sổ xử lý lên 300 giây nên file ngắn cũng tiêu tốn VRAM tương đương. |
| **Bản nhạc có nốt chồng lấn (Overlaps)** | Âm thanh đầu vào có nhiều nốt vang đè lên nhau hoặc phân tích AI chưa hoàn hảo. | Mở tab **Giai điệu**, kiểm tra các nốt có vị trí và trường độ đè nhau. Chỉnh sửa lại trường độ hoặc vị trí trước khi xuất file lead sheet đơn âm. |
| **Lời hát không khớp với nốt** | Mốc thời gian của file phụ đề SRT/LRC bị lệch so với bản audio. | Trong tab **Lời hát**, sử dụng ô **Dịch mốc thời gian (giây)** (nhập số âm nếu lời xuất hiện quá trễ, số dương nếu lời xuất hiện quá sớm) rồi bấm nhập lại file. |
| **Xóa nhầm dự án** | Người dùng vô tình bấm nút xóa dự án. | Mở mục **Thùng rác** ở góc dưới thanh bên (Sidebar), tìm dự án đã xóa và nhấn nút **Khôi phục**. Toàn bộ audio, lịch sử phiên bản và file xuất sẽ được đưa trở lại danh sách. |
