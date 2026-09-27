# Bản Nhạc Local

Web UI Việt/Anh chạy tại **http://127.0.0.1:8765** trên Windows 11. Backend Python, frontend React/TypeScript, dữ liệu lưu tại máy.

Vòng làm việc: **upload → dò thông số audio → phân tích bản nhạc → lời hát (tùy chọn) → kiểm tra → tải xuống**.

## Chạy trên máy hiện tại

Mở **`Start.cmd`** trong thư mục dự án. Giữ cửa sổ chạy backend mở trong lúc sử dụng; `Ctrl+C` để dừng. Nếu trình duyệt không tự mở, truy cập http://127.0.0.1:8765.

Sau khi sửa source hoặc cài trên máy mới:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1
```

Cần `uv`, Node.js 22+ để build giao diện, FFmpeg (`ffmpeg` và `ffprobe` trong PATH). `setup.ps1` tạo runtime Python 3.12 và cài đúng các phiên bản trong `requirements.lock`. Python của model dùng môi trường 3.11 riêng. Không cần Node.js khi chỉ chạy frontend đã build. PDF được tạo trực tiếp trong trình duyệt bằng JavaScript, không cần cài MuseScore.

## ✨ Tính năng nổi bật & Cập nhật mới

- 🌐 **Triển khai Online linh hoạt (Vercel + Google Colab GPU T4)**:
  - **Frontend trên Vercel**: Triển khai giao diện tĩnh cực nhanh lên Vercel, hỗ trợ cấu hình tùy biến địa chỉ Backend API từ xa (`VITE_API_URL` hoặc nhập trực tiếp trên giao diện). Xem chi tiết [Hướng dẫn Vercel](docs/HUONG-DAN-CAI-DAT-VERCEL.md).
  - **Backend AI trên Google Colab**: Chạy toàn bộ backend FastAPI + model SheetSage2/MERT-v2 trên GPU NVIDIA T4 miễn phí, tự động kết nối qua Cloudflare Tunnel (`trycloudflare.com`). Xem chi tiết [Hướng dẫn Google Colab](docs/deploy-colab.md).
  - **Chế độ Network Mode an toàn**: Hỗ trợ biến môi trường `SHEET_STUDIO_NETWORK_MODE`, kiểm soát CORS, giới hạn số tác vụ đồng thời trên mỗi IP (`SHEET_STUDIO_MAX_ACTIVE_PER_IP`) và hàng đợi xử lý chống tràn VRAM.
- 📄 **Xuất PDF Vector A4 & In ấn trực tiếp (Print)**:
  - **PDF Vector chuẩn in ấn**: Tạo trực tiếp trong trình duyệt bằng OpenSheetMusicDisplay + jsPDF + svg2pdf.js, không cần MuseScore hay dịch vụ backend bên ngoài.
  - **Nhúng font Noto Sans tiếng Việt**: Đảm bảo toàn bộ dấu thanh tiếng Việt và ký tự quốc tế hiển thị sắc nét, chuẩn xác.
  - **Tùy biến xuất nâng cao**: Cho phép chọn trích xuất phạm vi ô nhịp (`Từ ô... Đến ô...`), bật/tắt hợp âm (chords) và lời bài hát (lyrics).
  - **Nút In bản nhạc (Print)**: Tích hợp chế độ `@media print` chuyên dụng, tự động ẩn các thanh công cụ, tối ưu căn lề giấy A4 và khắc phục hoàn toàn lỗi trang trắng xem trước khi in.
- ✏️ **Chỉnh sửa Tên Bài hát trực tiếp**:
  - Nhấp đúp hoặc bấm biểu tượng chỉnh sửa trên tiêu đề H1 và trong bảng Inspector để đổi tên bài hát.
  - Tự động đồng bộ tên mới vào cơ sở dữ liệu và file MusicXML thông qua API `PATCH /api/projects/{id}`.
- 🎨 **Cải tiến Giao diện & Trải nghiệm (UI/UX)**:
  - Đường viền nổi bật (focus outlines) trực quan cho từng bước của quy trình: *1. Upload → 2. Phân tích → 3. Thêm lời → 4. Kiểm tra & Xuất*.
  - Nút **Dò thông số audio (Analyze Audio)** được làm nổi bật với sắc xanh hiện đại, dễ nhận biết.
  - Tự động lưu trữ cài đặt API endpoint, cấu hình hiển thị và font chữ lời hát vào LocalStorage.
- 🎼 **Trình soạn thảo nốt nhạc chuyên sâu (Smoosic Editor)**:
  - Tích hợp sâu Smoosic 1.0.44 chạy hoàn toàn local; chỉnh sửa cao độ (phím A–G, `=`/`-`), trường độ, lời ca, ô nhịp; lưu lịch sử phiên bản (`v1.json`, `v2.json`...) an toàn và kiểm tra xung đột đa tab.

---

## Hai bộ phân tích khác nhau

| Bộ phân tích | Dùng cho | Giới hạn |
|---|---|---|
| **SheetSage2 · Hugging Face** | Thử phiên âm melody và hợp âm từ bản phối bằng model local | Cần cài riêng model/runtime; kiểm tra kết quả trước khi sử dụng |
| **Giai điệu đơn · DSP thử nghiệm** | Một giai điệu solo sạch, mỗi thời điểm một nốt | Không phải AI; không tách melody trong bản phối và không đoán hợp âm |

Giao diện đọc trạng thái cài đặt thực tế. Nếu model chưa sẵn sàng, ứng dụng báo lý do; không tạo kết quả giả hoặc âm thầm gửi audio lên cloud.

Để cài SheetSage2 và model cha MERT-v2:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-model.ps1
```

Xem [hướng dẫn model](docs/model-setup.md) về phiên bản, bộ nhớ, điều kiện weights và kết quả kiểm tra. Weights SheetSage2/MERT-v2 được công bố CC-BY-NC-4.0; không suy ra quyền thương mại/phân phối code từ giấy phép thư viện phụ. Repo ứng dụng không kèm weights trong Git.

## Cách sử dụng

1. **Upload:** chọn WAV, MP3 hoặc FLAC, tối đa 200 MB / 10 phút.
2. **Dò thông số audio:** bấm **Analyze Audio** để ước lượng tempo, giọng và nhịp. Mặc định tự chạy sau upload; có thể tắt trong Cài đặt. Kiểm tra các gợi ý trước khi tiếp tục.
3. **Phân tích bản nhạc:** chọn engine, nguồn melody (nhạc cụ/giọng hát), chỉnh thông số rồi chạy phiên âm. Có thể hủy tác vụ.
4. **Lời hát (tùy chọn):** nhập SRT/LRC, căn và sửa lời. Có thể xóa/reset rồi nhập lại.
5. **Kiểm tra:** nghe audio gốc và bản dựng lại, sửa nốt/hợp âm/lời; lưu rồi bấm **Xác nhận đã kiểm tra**.
6. **Tải xuống & In ấn:** MusicXML, MIDI, PDF hoặc ABC chỉ mở khi bản hiện tại đã được xác nhận. Sửa tiếp sẽ yêu cầu lưu và kiểm tra lại:
   - **Xuất PDF vector A4:** Dàn trang A4 tự động bằng OpenSheetMusicDisplay và xuất file vector bằng jsPDF/svg2pdf.js; hỗ trợ tùy chọn khoảng ô nhịp (`Từ ô... Đến ô...`), bật/tắt hợp âm và lời hát. Font Noto Sans được nhúng sẵn giữ trọn vẹn dấu tiếng Việt khi in. Thư viện và font được đóng gói local; không gọi dịch vụ tạo PDF bên ngoài.
   - **In bản nhạc trực tiếp (Print):** Bấm **In bản nhạc** để mở hộp thoại in của trình duyệt; CSS `@media print` được tối ưu chuyên dụng để ẩn toàn bộ thanh điều khiển thừa, tự động căn lề và xử lý hiển thị chống trang trắng xem trước.
   - **Đổi tên bài hát:** Bấm đúp hoặc icon bút chì cạnh tiêu đề H1 / Inspector để đổi tên bài; tên mới sẽ tự động lưu và xuất hiện trên bản in PDF & MusicXML.

Mỗi lần lưu tạo revision mới. Phân tích lại một dự án đã có sheet tạo bản nháp riêng; phải chọn sử dụng thì mới thay bản đang chỉnh. API chỉ cho tải revision hiện tại đã xác nhận; đường tải file cũ cũng bị khóa sau khi lưu bản sửa. Xem khuông nhạc và nghe thử vẫn dùng được trước khi xác nhận.

Khi nghe giai điệu dựng lại, kéo thanh vị trí để tua tới/lùi (cũng dùng được trước khi bấm phát), chỉnh **Âm lượng** từ 0–100%. Ở mức 100%, gain nhạc cụ là 0,8 — gấp 5 lần gain cũ tại 100%; compressor vẫn hạn chế đỉnh âm. Bộ đếm ô nhịp/phách có tiếng click và âm lượng riêng. Nhịp kép 6/8, 9/8, 12/8 đếm theo phách đen chấm dôi. Bấm dừng để về đầu. Khuông nhạc và màu nốt đồng bộ cả bản sửa chưa lưu, nốt nối qua ô nhịp và khi tua/nghe lại.

**Cài đặt** lưu tại trình duyệt: tự dò thông số sau upload, tự cuộn khi nghe, màu active notes, ngôn ngữ VI/EN và 10 font lời hát. Font chỉ áp dụng cho lời trên khuông nhạc và ô nhập lời; tên bè, tempo, hợp âm và số ô nhịp giữ nguyên. PDF dùng font Noto Sans nhúng sẵn; lựa chọn font lời hát chỉ áp dụng cho phần xem/chỉnh lời. Chọn **Thiết bị xử lý → Auto / GPU · CUDA / CPU only** cho lần chạy SheetSage2 tiếp theo. Auto ưu tiên CUDA; GPU báo lỗi nếu CUDA không khả dụng; CPU only ẩn CUDA khỏi worker và dùng FP32. Dò audio và DSP luôn dùng CPU. Tác vụ đang chạy giữ lựa chọn lúc bắt đầu.

Các khung audio gốc, dò audio, nghe giai điệu, bản nhạc và bốn khung thiết lập/xuất file có mũi tên nhỏ lên/xuống để thu gọn hoặc mở lại, giữ nguyên nội dung và trạng thái điều khiển. **Giúp đỡ** mở hướng dẫn 6 bước; popup cũng xuất hiện lần đầu.

### Editor MusicXML

Sau **Xác nhận đã kiểm tra**, bấm **Mở Editor** trong khung **Kiểm tra → Xuất file**. Trang Editor dùng [Smoosic 1.0.44](https://github.com/Smoosic/Smoosic) được đóng gói local và tự mở MusicXML của đúng dự án/phiên bản hiện tại. Chọn nốt rồi dùng A–G để đặt cao độ, `=`/`-` để chuyển cao độ, dấu phẩy/chấm để giảm/tăng trường độ; các menu hỗ trợ lời, ô nhịp và bố cục. Nghe thử dùng mẫu piano local cho mọi nhạc cụ.

**Lưu vào dự án** giữ nguyên MusicXML đầy đủ trong `data/projects/{id}/editor/{source_revision}/`, có lịch sử `v1.json`, `v2.json`… và kiểm tra xung đột khi có nhiều cửa sổ. Mở lại sẽ nạp bản Editor đã lưu. **Tải MusicXML** xuất nội dung đang chỉnh. Bản Editor là bản MusicXML riêng: không ghi đè mô hình phiên âm một bè, preview và các file MIDI/PDF/ABC của màn hình chính. Nếu nguồn được sửa/phân tích lại, hãy kiểm tra nguồn mới rồi mở Editor mới; các bản Editor cũ vẫn được giữ trên đĩa. Thông báo rời trang giúp tránh mất thay đổi chưa lưu.

`npm run dev` và `npm run build` tự chuẩn bị JS/CSS/font Smoosic từ dependency đã ghim; không cần CDN để mở/chỉnh sửa/nghe thử. Menu Library của Smoosic là thư viện bên ngoài. Lưu ý khả năng chuyển đổi MusicXML phụ thuộc Smoosic; nên kiểm tra bản nhạc sau nhập/xuất.

Analyze Audio chạy DSP local trên tối đa 120 giây đầu. Tempo có thể lệch nửa/gấp đôi, giọng trưởng/thứ tương đối có thể nhầm; gợi ý nhịp 3/4 hoặc 4/4 chỉ là ước lượng. Khi không đủ tín hiệu sẽ báo chưa xác định. Các nhịp khác vẫn chọn thủ công. Đây chưa phải tempo map hay nhận dạng đổi giọng/đổi nhịp trong bài.

Sáu bộ mẫu nhạc cụ được đóng gói local; nghe thử không cần mạng. Nguồn và ghi công: [FluidR3 GM](frontend/public/instruments/NOTICE.md). Lựa chọn nhạc cụ chỉ áp dụng cho nghe thử, chưa thay nhạc cụ trong MIDI xuất ra.

### Phân tích lại bản nhạc

Bấm **Quay lại bước 2 · Phân tích** phía trên quy trình (hoặc bấm **Phân tích** trên thanh bước). Nếu có chỉnh sửa chưa lưu, hãy lưu trước. Chọn lại **Giai điệu chính → Nhạc cụ / Giọng hát**, engine và các thiết lập rồi bấm **Phân tích lại audio**. Không cần upload lại audio. Các lựa chọn ở bước 2 không sửa bản nhạc đang có; có thể bấm **Quay lại bản nhạc** để hủy việc thiết lập lại.

Sau khi chạy xong, bấm **Mở xem → Dùng bản này** để thay bản hiện tại bằng kết quả mới. Bản cũ vẫn được giữ trong lịch sử. Bản mới cần nghe và xác nhận kiểm tra trước khi xuất file.

### Xóa và khôi phục dự án

Mở dự án cần xóa, bấm **Xóa dự án** phía trên quy trình và xác nhận. Dự án được đưa vào **Thùng rác** ở thanh bên; bấm **Khôi phục** để đưa lại vào danh sách. Audio, lời, các phiên bản và file xuất vẫn được giữ local, nên thao tác này chưa giải phóng dung lượng ổ đĩa. Không thể xóa khi tác vụ phân tích đang chờ/chạy; hãy dừng hoặc chờ hoàn tất. Cần lưu chỉnh sửa trước khi xóa.

## Thêm lời hát từ SRT / LRC

1. Sau khi phân tích bản nhạc, mở bước **Thêm lời (tùy chọn)**. Với bài hát có giọng, chọn bè **Giọng hát** khi phân tích nếu muốn ghép lời theo giai điệu hát.
2. Nếu đã có bản nhạc, mở tab **Lời hát** để nhập/thay SRT/LRC (tối đa 1 MB; UTF-8 hoặc UTF-16 có BOM). Chọn độ dịch thời gian nếu cần; số dương làm lời xuất hiện muộn hơn trong audio.
3. Ứng dụng ghép từ/âm tiết vào nốt trong khoảng thời gian của từng câu. Đây là căn lời ước lượng từ timestamps; những từ không đủ nốt để ghép vẫn được giữ ở trạng thái **Chưa gắn nốt**.
4. Sửa chữ, chọn nốt, khổ lời hoặc kiểu âm tiết trong bảng. Bấm **Lưu**, rồi trở về **Khuông nhạc** để kiểm tra.
5. Xác nhận đã kiểm tra rồi xuất **MusicXML/PDF**: lời đã gắn nốt nằm dưới khuông; nốt nối qua vạch nhịp không bị lặp chữ. MIDI hiện chỉ chứa nốt và bè đệm, không có lyric track.

Nhập tệp lời tạo revision mới và thay lớp lời đang chỉnh; revision cũ được giữ. Cần lưu chỉnh sửa trước khi nhập. Nếu dùng bản phân tích AI mới có bộ nốt khác, hãy nhập/căn lời lại. Xem [chi tiết định dạng và căn lời](docs/LYRICS.vi.md).

## Giới hạn phiên bản 0.1

- Score dùng **tempo, meter và key cố định do người dùng chọn**; chưa tự dựng tempo map/rubato/đổi nhịp từ AI.
- Melody được lượng tử hóa lưới 1/16 khi chuyển kết quả nhận dạng; raw events/audio vẫn được giữ trong project.
- Sheet một bè melody. Nếu còn nốt chồng lấn, ứng dụng cho lưu bản nháp và yêu cầu sửa trước khi khắc in MusicXML/PDF.
- Không phục hồi melody bị thiếu trong backing track, không tự nhận dạng/tạo lyrics từ audio; nhận lời do người dùng nhập SRT/LRC. Chưa chép tổng phổ hoặc TAB.
- Hợp âm dựng để nghe/MIDI accompaniment là phần đệm tổng hợp, không phải bè chép từ bản thu.
- Đã kiểm thử kỹ thuật, audio tổng hợp và chạy thành công một bản thu thực gần 8 phút; chưa có bộ đánh giá độ chính xác rộng trên nhạc thực. Xem [kết quả kiểm chứng](docs/VALIDATION.vi.md).

## Dữ liệu và cấu trúc

```text
backend/                  API, SQLite metadata, score revisions và exporter
frontend/                 Web UI, OSMD, audio playback và editor
workers/                  Worker AI chạy trong process/runtime riêng
models/registry.json      ID và revision model được ghim
models/installed.json     Manifest snapshot đã tải, checksum và kích thước
data/                     Dự án, audio gốc, runs, revisions và exports
.cache/model-snapshots/   Weights/config/code model tải về máy
.venv/                    Runtime API
.venv-model/              Runtime model
tests/                    Kiểm thử notation, lưu dữ liệu và API
output/                   Tài liệu nghiên cứu/kế hoạch ban đầu
```

Audio được giữ nguyên; tệp inference và score chỉnh sửa lưu riêng. Mặc định API chỉ bind `127.0.0.1`; không mở cho LAN. Asset giao diện được bundle local. Tải model/phụ thuộc cần mạng lần đầu; inference và xử lý project dùng tài nguyên local đã cài.

### Biến môi trường cấu hình

| Biến môi trường | Mặc định | Chức năng |
|---|---|---|
| `SHEET_STUDIO_DATA` | `data/` | Thư mục lưu trữ dự án, audio và các bản xuất |
| `SHEET_STUDIO_NETWORK_MODE` | `0` | Đặt `"1"` khi chạy backend từ xa (Google Colab, máy chủ mạng) để mở CORS |
| `SHEET_STUDIO_ALLOWED_HOSTS` | `*` (khi bật network mode) | Danh sách domain/host được phép kết nối (phân tách bởi dấu phẩy) |
| `SHEET_STUDIO_MAX_WORKERS` | `1` | Số tiến trình worker AI chạy đồng thời (giữ `1` để tránh tràn VRAM GPU) |
| `SHEET_STUDIO_MAX_QUEUE` | `10` | Số lượng tác vụ tối đa chờ trong hàng đợi phân tích |
| `SHEET_STUDIO_MAX_ACTIVE_PER_IP` | `1` | Giới hạn số bài phân tích đang xử lý cho mỗi địa chỉ IP (chống spam/DDoS) |
| `SHEETSAGE2_PYTHON` | `None` | Đường dẫn Python runtime riêng cho worker SheetSage2 |
| `FFMPEG_PATH` | `None` | Đường dẫn `ffmpeg` ngoài PATH (vẫn cần `ffprobe` trên PATH để kiểm tra file) |
| `VITE_API_URL` | `""` (cùng origin) | (Frontend) Địa chỉ backend từ xa khi triển khai frontend lên Vercel |

---

## Phát triển và kiểm thử

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
# Terminal khác:
cd frontend
npm run dev
```

Vite proxy `/api` tới backend. Production build do FastAPI phục vụ từ `frontend/dist`.

Khi sửa phần nghe thử hoặc khuông nhạc, chạy [kiểm thử active notes và workflow](docs/PLAYBACK-QA.vi.md) trên workspace QA riêng. Script `scripts/check-playback.js` kiểm phát lại, tua qua nốt nối, thanh volume 0–100% với gain nhạc cụ được khuếch đại 5 lần, bản chưa lưu và khóa export.

Tạo audio kiểm thử có nhãn nốt tham chiếu:

```powershell
.venv\Scripts\python.exe scripts/make_test_audio.py
```

Audio này chỉ kiểm đường kỹ thuật; không dùng để tuyên bố độ chính xác model trên bài hát thực.
