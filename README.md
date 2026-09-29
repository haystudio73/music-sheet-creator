# Ứng dụng "Bản Nhạc - Local"

Web UI Việt/Anh chạy tại **http://127.0.0.1:8765** trên Windows 11

Quy trình: **Upload file âm thanh → Dò thông số audio: nhịp, tông → Phân tích bản nhạc → Nhập và sửa lời hát (tùy chọn) → Kiểm tra → Tải xuống / In**.

## Chạy trên PC Windows
### Yêu cầu hệ thống:
- Windows 11 Pro+
- GPU nVidia VGA 4Gb+ (tùy chọn) để tăng tốc giải mã
- Cài download thư viện FFmpeg (Windows): https://www.gyan.dev/ffmpeg/builds/
```
winget install "FFmpeg (Essentials Build)"
```

- Cài đặt ứng dụng từ github
```
git clone https://github.com/haystudio73/music-sheet-creator.git
cd music-sheet-creator
```

- Thực thi ứng dụng:
```
Start.cmd
```
** Nhớ chạy trong thư mục dự án.Luôn Giữ cửa sổ chạy backend mở trong lúc sử dụng; `Ctrl+C` để dừng. , 

- Nếu trình duyệt không tự mở thì bạn nhập địa chỉ: http://127.0.0.1:8765 trên trình duyệt Chrome, Edge, Safari ... để vào sử dụng app!

** Nếu sửa source hoặc cài trên máy mới:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1
```

<img width="1538" height="873" alt="image" src="https://github.com/user-attachments/assets/155028f4-fabd-450e-bf1c-bda36b8d48d4" />

## ✨ Tính năng nổi bật

- 🌐 **Triển khai Online linh hoạt (Vercel + Google Colab GPU T4)**:
  - **Frontend trên Vercel**: Triển khai giao diện tĩnh cực nhanh lên Vercel, hỗ trợ cấu hình tùy biến địa chỉ Backend API từ xa (`VITE_API_URL` hoặc nhập trực tiếp trên giao diện). Xem chi tiết [Hướng dẫn Vercel](docs/HUONG-DAN-CAI-DAT-VERCEL.md).
  - **Backend AI trên Google Colab**: Chạy toàn bộ backend FastAPI + model SheetSage2/MERT-v2 trên GPU NVIDIA T4 miễn phí, tự động kết nối qua Cloudflare Tunnel (`trycloudflare.com`). Xem chi tiết [Hướng dẫn Google Colab](docs/deploy-colab.md).
  - **Chế độ Network Mode an toàn**: Hỗ trợ biến môi trường `SHEET_STUDIO_NETWORK_MODE`, kiểm soát CORS, giới hạn số tác vụ đồng thời trên mỗi IP (`SHEET_STUDIO_MAX_ACTIVE_PER_IP`) và hàng đợi xử lý chống tràn VRAM.
- 📄 **Xuất PDF Vector A4 & In ấn trực tiếp (Print)**:
  - **PDF Vector chuẩn in ấn**: Tạo trực tiếp trong trình duyệt.
  - **Tùy biến xuất nâng cao**: Cho phép chọn trích xuất phạm vi ô nhịp (`Từ ô... Đến ô...`), bật/tắt hợp âm (chords) và lời bài hát (lyrics).
  - **Nút In bản nhạc (Print)**: Tích hợp chế độ chuyên dụng, tự động ẩn các thanh công cụ, tối ưu căn lề giấy A4 và khắc phục hoàn toàn lỗi trang trắng xem trước khi in.
- ✏️ **Chỉnh sửa Tên Bài hát trực tiếp**:
  - Nhấp đúp hoặc bấm biểu tượng chỉnh sửa trên tiêu đề H1 và trong bảng Inspector để đổi tên bài hát.
  - Tự động đồng bộ tên mới vào cơ sở dữ liệu và file MusicXML thông qua API `PATCH /api/projects/{id}`.
- 🎨 **Cải tiến Giao diện & Trải nghiệm (UI/UX)**:
  - Đường viền nổi bật (focus outlines) trực quan cho từng bước của quy trình: *1. Upload → 2. Phân tích → 3. Thêm lời → 4. Kiểm tra & Xuất*.
  - Nút **Dò thông số audio (Analyze Audio)** được làm nổi bật với sắc xanh hiện đại, dễ nhận biết.
  - Tự động lưu thông số trong Cài đặt .
---

## Hai bộ phân tích khác nhau

| Bộ phân tích | Dùng cho | Giới hạn |
|---|---|---|
| **SheetSage2 · Hugging Face** | Thử phiên âm melody và hợp âm từ bản phối bằng model local | Cần cài riêng model/runtime; kiểm tra kết quả trước khi sử dụng |
| **Giai điệu đơn · DSP thử nghiệm** | Một giai điệu solo sạch, mỗi thời điểm một nốt | Không phải AI; không tách melody trong bản phối và không đoán hợp âm |

Giao diện đọc trạng thái cài đặt thực tế. Nếu model chưa sẵn sàng, ứng dụng báo lý do; ## *không tạo kết quả giả hoặc âm thầm gửi audio lên cloud.*

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

Khi nghe giai điệu dựng lại, kéo thanh vị trí để tua tới/lùi (cũng dùng được trước khi bấm phát), chỉnh **Âm lượng** từ 0–100%. 
Ở mức 100%, gain nhạc cụ là 0,8 — gấp 5 lần gain cũ tại 100%; compressor vẫn hạn chế đỉnh âm. Bộ đếm ô nhịp/phách có tiếng click và âm lượng riêng. Nhịp kép 6/8, 9/8, 12/8 đếm theo phách đen chấm dôi. Bấm dừng để về đầu. Khuông nhạc và màu nốt đồng bộ cả bản sửa chưa lưu, nốt nối qua ô nhịp và khi tua/nghe lại.

**Cài đặt** lưu tại trình duyệt: tự dò thông số sau upload, tự cuộn khi nghe, màu active notes, ngôn ngữ VI/EN và 10 font lời hát. Font chỉ áp dụng cho lời trên khuông nhạc và ô nhập lời; tên bè, tempo, hợp âm và số ô nhịp giữ nguyên. PDF dùng font Noto Sans nhúng sẵn; lựa chọn font lời hát chỉ áp dụng cho phần xem/chỉnh lời. Chọn **Thiết bị xử lý → Auto / GPU · CUDA / CPU only** cho lần chạy SheetSage2 tiếp theo. Auto ưu tiên CUDA; GPU báo lỗi nếu CUDA không khả dụng; CPU only ẩn CUDA khỏi worker và dùng FP32. Dò audio và DSP luôn dùng CPU. Tác vụ đang chạy giữ lựa chọn lúc bắt đầu.

Các khung audio gốc, dò audio, nghe giai điệu, bản nhạc và bốn khung thiết lập/xuất file có mũi tên nhỏ lên/xuống để thu gọn hoặc mở lại, giữ nguyên nội dung và trạng thái điều khiển. **Giúp đỡ** mở hướng dẫn 6 bước; popup cũng xuất hiện lần đầu.

### Phân tích lại bản nhạc khi muốn chọn Giọng hát(Vocal) hay Nhạc cụ (Instrument)

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

## Giới hạn phiên bản V0.1

- Score dùng **tempo, meter và key cố định do người dùng chọn**; chưa tự dựng tempo map/rubato/đổi nhịp từ AI (không sử dụng AI, API ...)
- Melody được lượng tử hóa lưới 1/16 khi chuyển kết quả nhận dạng; raw events/audio vẫn được giữ trong project.
- Sheet một bè melody. Nếu còn nốt chồng lấn, ứng dụng cho lưu bản nháp và yêu cầu sửa trước khi in MusicXML/PDF.
- Không phục hồi melody bị thiếu trong backing track, không tự nhận dạng/tạo lyrics từ audio; nhận lời do người dùng nhập SRT/LRC. Chưa chép tổng phổ hoặc TAB.
- **Hợp âm dựng để nghe/MIDI accompaniment là phần đệm tổng hợp, không phải bè chép từ bản thu.**
- **Phiên bản cover bằng AI sẽ có trong tương lai**

---

## Buy me a coffee!!

❤️❤️❤️ Nếu bạn yêu thích mã nguồn này ❤️❤️❤️ HÃY MỜI TÔI 1 LY CAFE (Momo QR)!

<img width="390" height="422" alt="image" src="https://github.com/user-attachments/assets/ba0993b0-264f-4c49-9f05-d8fd3050902a" />

## Thanks, and good luck!

