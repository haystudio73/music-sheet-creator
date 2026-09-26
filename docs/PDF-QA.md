# Kiểm thử xuất PDF và bố cục in ấn · 2026-09-26

## Kết quả kiểm thử đã đạt

- **Quy mô và độ dài**: Đã kiểm thử trên fixture cô lập (`Khúc thử nghiệm – Nắng bên đồi` qua `scripts/ui_pdf_fixture.py`):
  - File PDF xuất đầy đủ đạt đúng **8 trang A4**.
  - Đầy đủ **630 từ lời bài hát** (315 sự kiện nốt × 2 khổ lời).
  - Đầy đủ **80 ký hiệu hợp âm** (chords/extensions/bass slash).
- **Trích đoạn theo ô nhịp**:
  - Đã kiểm tra xuất trích đoạn (ví dụ ô nhịp 3 đến 4).
  - Bản xuất chỉ bao gồm đúng các ô nhịp đã chọn; các ô nhịp ngoài phạm vi không bị đưa vào PDF.
  - Tùy chọn bỏ hợp âm và bỏ lời hoạt động chính xác: bản nhạc trích đoạn xuất nốt nhạc thuần túy khi bỏ chọn.
- **Đồng nhất hiển thị (Print Parity)**:
  - Bản xuất trên màn hình di động (viewport 390×844) và chế độ giao diện tối (Dark Theme) cho cùng nội dung, kích thước và định dạng bản in vector A4 như chế độ sáng trên desktop.
  - Văn bản tiếng Việt giữ đúng dấu nhờ nhúng font Unicode Noto Sans local, không bị lỗi font ASCII.
- **Cơ chế bảo vệ (Gating & Error handling)**:
  - Bản nhạc chưa xác nhận kiểm tra (`needs_review`) tự động khóa nút tải PDF.
  - Chỉnh sửa nốt hoặc lời chưa lưu tự động khóa nút tải PDF.
  - Trường hợp font gặp lỗi tải: hiển thị thông báo lỗi rõ ràng, dọn dẹp sạch DOM render tạm thời, không để lại phần tử treo; cho phép thử lại sau khi font khả dụng.
  - Không phụ thuộc vào MuseScore hay công cụ render ngoài nào; xử lý 100% vector phía trình duyệt bằng OpenSheetMusicDisplay + jsPDF + svg2pdf.js.

## Hướng dẫn tái hiện kiểm thử tự động

Tạo thư mục dữ liệu QA cô lập và chạy fixture:

```powershell
.venv\Scripts\python.exe -m scripts.ui_pdf_fixture tmp/pdf-qa
$env:SHEET_STUDIO_DATA = Join-Path (Get-Location) 'tmp/pdf-qa'
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8771
```

Chạy kiểm thử Playwright với script `scripts/check-pdf-export.js`. Kết quả file PDF và ảnh chụp được lưu tại:
- `output/playwright/pdf-export-full.pdf` (8 trang đầy đủ)
- `output/playwright/pdf-export-range.pdf` (trích đoạn ô nhịp 3–4)
- `output/playwright/pdf-export-mobile-dark.pdf` (bản xuất từ mobile viewport & dark theme)
- `output/playwright/pdf-export-mobile-dark.png` (ảnh chụp màn hình giao diện)
