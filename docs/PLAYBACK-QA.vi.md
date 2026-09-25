# Kiểm thử nghe thử và workflow

Chạy lại khi thay ScorePlayer, ScorePreview, Settings, timeline, lyrics hoặc OSMD.
Không dùng bài của người dùng để kiểm thử thao tác sửa/xóa lời.

## Workspace QA riêng

Build frontend rồi tạo một thư mục mới chưa có dự án:

```powershell
.venv\Scripts\python.exe -m scripts.ui_fixture tmp/ui-qa-new
$env:SHEET_STUDIO_DATA = Join-Path (Get-Location) 'tmp/ui-qa-new'
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8770
```

Mở `http://127.0.0.1:8770`, bỏ qua hướng dẫn, chọn EN và dự án **Playback regression**.
Fixture 60 BPM dài 64 giây: nốt đầu 0–1, nghỉ 1–2, nốt nối 2–6 (tách ở beat 4), nghỉ 6–7.

## Kiểm thử tự động trong trình duyệt

`scripts/check-playback.js` là hàm nhận Playwright Page (hoặc `tab.playwright` trong browser tool). Chạy bằng Playwright `run-code` trên tab QA. Không chạy trên dữ liệu thật. Hàm kiểm tra:

- Thanh volume nhạc cụ đạt 100% và gain thực tế tại đó là 0,8 (gấp 5 lần mức cũ); metronome có mức 0% riêng.
- Hai lần dừng/phát lại đều sáng nốt đầu; dừng xóa màu và reset vị trí.
- Tua vào đoạn 4–6 của nốt nối tô đúng đoạn viết trên khuông.
- Sửa cao độ chưa lưu vẫn sáng nốt; export bị khóa; undo trả về bản đã lưu.

Đã chạy thành công các bước này qua trình duyệt tích hợp ngày 23/09/2026.
Đã kiểm tra thêm: mobile 390px không tràn ngang; màu đỏ/xanh, font Lora tiếng Việt; clear/import lyrics; settings giữ sau reload; Help mở lại; luồng upload tự dò → DSP phiên âm → bước lời tùy chọn → xác nhận → tải MusicXML. Không ghi nhận lỗi JavaScript trong lượt kiểm thử.

## Các tình huống bổ sung

- Kéo thanh vị trí bằng chuột/touch; tua vào khoảng nghỉ không sáng nốt.
- Đổi màu, font, tab và kích thước cửa sổ; nốt vẫn sáng sau khi khuông dàn lại.
- Auto-scroll bật đưa nốt ngoài màn hình vào giữa; tắt giữ vị trí xem. Không giật trang khi đang giữ thanh tua.
- Font Lora hiển thị lời tiếng Việt; có đủ 9 font offline. Reload giữ lựa chọn.
- Mobile 390px: không tràn trang; toolbar, tab và workflow có icon/tên truy cập; dialog dùng được.
- Lyrics: clear tạo revision mới; import file mới/cùng file; confirm mở export; sửa/import lại khóa export.
- Upload audio tự dò khi setting bật; tắt thì chỉ chạy khi bấm Analyze Audio. Dò thông số không tự chạy model phiên âm.
- Hướng dẫn xuất hiện lần đầu; đã bỏ qua thì không mở lại khi reload; Help luôn mở được.

Backend: `.venv\Scripts\python.exe -m pytest -q` (124 bài kiểm thử đã qua).
Frontend: `cd frontend; npm run build` (TypeScript và production bundle đã qua).
