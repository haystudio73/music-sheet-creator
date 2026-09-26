# Tiến độ task 2026-09-25

Mục tiêu: hoàn thiện luồng chỉnh sửa khuông nhạc, undo, cảnh báo chuyển dự án và lịch sử kiểm tra/xuất file.

## Yêu cầu

- [x] Box sửa nhanh hiển thị ngay dưới nốt đang sửa, không còn nằm ở cuối bài hát.
- [x] Thanh “Nhạc cụ nghe thử” giữ phạm vi 0–100%, nhưng gain tại 100% được tăng lên 5× so với trước.
- [x] Sau khi lưu vẫn chọn và sửa tiếp được nốt; khuông chưa có lyric vẫn mở editor nốt khi click.
- [x] Gia cố click nốt bằng event delegation để box sửa nhanh không phụ thuộc lyric hoặc vòng render OSMD.
- [x] Kiểm tra ngay mỗi lần sửa: cao độ MIDI hợp lệ, trường độ dương, không chồng nốt liền kề và xác định đúng vị trí ô nhịp.
- [x] Hoàn tác tối đa 99 thay đổi bằng nút Undo và `Ctrl+Z`/`Cmd+Z`.
- [x] Khi chuyển dự án có thay đổi chưa lưu, hỏi và lưu trước khi chuyển.
- [x] Click một lần ra ngoài nốt, lyric và khung editor sẽ đóng editor; không giật sau khi chọn lyric.
- [x] Lịch sử kiểm tra/xuất file lưu trong Local Storage, tối đa 10 mục, chỉ chứa metadata kết quả và tệp audio/output.

## Chẩn đoán

- `ScorePreview` chỉ gắn handler click nốt/lyric khi `disabled === false` tại thời điểm OSMD render. Trong lúc lưu, `disabled === true`; phiên bản mới làm render lại đúng lúc đó, nên sau khi lưu các nốt không còn handler click.
- Đóng editor hiện chỉ lắng nghe click trên phần tử `mount` của OSMD. Click vào khoảng trống khác hoặc click làm input lyric blur có thể không tới handler ở lần đầu.
- Undo hiện chỉ giữ 50 snapshot, chỉ có nút bấm và chưa có phím tắt toàn cục.
- Xác nhận chuyển dự án hiện hỏi bỏ thay đổi, chưa có lựa chọn lưu trước khi chuyển.
- Chưa có lịch sử kiểm tra/xuất file trong Local Storage.

## Nhật ký thay đổi

- 2026-09-25: bắt đầu sửa vị trí box edit; đổi từ sticky cuối khuông sang tọa độ bám theo SVG của nốt được chọn và theo dõi scroll/resize/render lại.
- 2026-09-25: giới hạn chiều rộng box trong cột khuông nhạc; tự lật lên trên nếu dưới nốt không đủ chỗ. Production build PASS; Playwright đo khoảng cách nốt–box 10 px, xác nhận box không tràn cột và toàn bộ regression edit PASS.
- 2026-09-25: đổi `instrumentVolume` về miền lưu/UI 0–100; ánh xạ 100% thành gain 0.8 (5× gain cũ 0.16), giữ compressor và không thay đổi gain metronome/audio gốc.
- 2026-09-25: cập nhật Playwright playback regression để yêu cầu đầu phải dừng ở 100% thay vì 200%.
- 2026-09-25: regression đọc trực tiếp Web Audio GainNode và xác nhận slider 100% tạo gain 0.8; production build và toàn bộ playback regression đều PASS.
- 2026-09-25: tạo file tiến độ và ghi lại chẩn đoán ban đầu.
- 2026-09-25: handler nốt/lyric dùng ref trạng thái mới nhất nên không bị mất sau khi lưu; thêm listener `pointerdown` capture để đóng editor chỉ với một click ngoài.
- 2026-09-25: thêm module lịch sử Local Storage có schema giới hạn chỉ `review`/`export`, metadata dự án/audio/output và tự cắt còn tối đa 10 mục.
- 2026-09-25: nâng Undo lên 99 snapshot, thêm `Ctrl+Z`/`Cmd+Z`, giữ stack sau khi lưu; thay confirm bỏ thay đổi bằng confirm lưu-trước-khi-chuyển và chỉ chuyển khi lưu thành công.
- 2026-09-25: ghi lịch sử khi xác nhận kiểm tra hoặc tải file thành công, hiển thị tối đa 10 mục trong Inspector; không lưu nội dung score hay dữ liệu audio vào Local Storage.
- 2026-09-25: thêm fixture và Playwright regression script cô lập cho toàn bộ 5 yêu cầu; chưa chạy ở thời điểm ghi dòng này.
- 2026-09-25: lần chạy Playwright đầu bị hộp hướng dẫn mặc định chặn click; đã cập nhật script tự đóng hộp này trước khi kiểm tra.
- 2026-09-25: Playwright regression đã đi hết luồng; fixture xác nhận dự án không lyric được sửa/lưu/sửa tiếp, chuyển dự án đã lưu thành revision 3, click ngoài đóng editor, history hiển thị 10/10 và Undo dừng ở thay đổi thứ nhất sau 99 lần.
- 2026-09-25: bộ đọc Local Storage chuẩn hóa lại từng mục về đúng schema để loại bỏ mọi field lạ từ dữ liệu cũ.
- 2026-09-25: build production lần cuối thành công; 24 backend regression tests passed; đã đóng browser và server fixture cô lập.
- 2026-09-25: nhận yêu cầu mới về box sửa nhanh khi chưa có lời và kiểm tra tính hợp lệ nhạc lý; bắt đầu gia cố mapping/click và validation phía client.
- 2026-09-25: chuyển click nốt/lyric sang event delegation tại container ổn định; mapping ưu tiên đúng attack rồi mới tới đoạn nốt nối, không phụ thuộc có lyric.
- 2026-09-25: thêm validation hiển thị ngay trong box: MIDI 0–127, start/duration hợp lệ, chặn chồng nốt trước/sau, xác định ô nhịp/phách, cảnh báo quãng tám và nốt nối qua ô nhịp.
- 2026-09-25: mở rộng Playwright regression để xác nhận box xuất hiện trên score không lyric, báo nốt hợp lệ và từ chối trường độ nốt tròn khi sẽ chồng nốt kế tiếp.
- 2026-09-25: production build thành công; Playwright regression không-lyric/validation đi hết luồng; 56 test `notation`/`editor`/`api` passed; đã đóng browser và server fixture.

## Kiểm thử đã hoàn tất

- [x] Production build TypeScript/Vite.
- [x] UI: chọn nốt khi không có lyric, sửa → lưu → chọn/sửa tiếp.
- [x] UI: `Ctrl+Z` hoàn tác và stack bị giới hạn 99.
- [x] UI: chuyển dự án khi dirty sẽ hỏi lưu và chỉ chuyển sau khi lưu thành công.
- [x] UI: chọn lyric rồi click một lần vào vùng ngoài sẽ đóng editor.
- [x] Local Storage: tối đa 10 mục, schema chỉ có metadata review/export/audio/output.
- [x] Backend regression: `test_editor.py`, `test_storage.py`, `test_api.py` — 24 passed.
- [x] Yêu cầu bổ sung: Playwright xác nhận box sửa nhanh trên score không lyric và chặn trường độ gây chồng nốt.
- [x] Yêu cầu bổ sung: `test_notation.py`, `test_editor.py`, `test_api.py` — 56 passed.
- [x] Âm lượng nghe thử: slider vẫn 0–100%, tại 100% gain nhạc cụ là 0.8 (5× mức cũ); metronome/audio gốc không đổi; playback regression PASS.
- [x] Vị trí box edit: bám nốt đang chọn khi scroll/resize/render lại, nằm dưới nốt với khoảng cách 10 px và trong cột khuông; production build + Playwright edit regression PASS.

## Tiến độ task 2026-09-26

Mục tiêu: hoàn tất kiểm tra tải xuống PDF, kiểm tra bố cục, cập nhật hướng dẫn sử dụng và cho phép chỉnh sửa tên bài hát.

### Yêu cầu

- [x] Kiểm tra tải xuống PDF: đủ 8 trang, đủ 630 từ lời bài hát và 80 hợp âm của bản thử nghiệm cô lập.
- [x] Xuất trích đoạn theo ô nhịp: chỉ bao gồm các ô nhịp đã chọn, hỗ trợ tùy chọn kèm/bỏ hợp âm và lời.
- [x] Đồng nhất bản in: bản xuất từ màn hình điện thoại (mobile viewport) và giao diện tối (dark theme) cho cùng nội dung, định dạng và kích thước bản in vector A4 như desktop light theme.
- [x] Hoàn tất kiểm tra bố cục và cập nhật hướng dẫn sử dụng trong tài liệu `docs/PDF-QA.md` và modal hướng dẫn workflow `frontend/src/Settings.tsx`.
- [x] Cho phép chỉnh sửa tên bài hát:
  - Sửa trực tiếp tại tiêu đề chính `<h1>` với nút bút chì, click để sửa, phím tắt Enter (lưu) / Escape (hủy), nút Lưu và Hủy.
  - Sửa trong khung Inspector bên phải (mục "Thiết lập bản nhạc" / "Thiết lập âm nhạc").
  - Hỗ trợ đổi tên bài hát ngay sau khi upload audio (trước khi phân tích) và sau khi đã tạo bản nhạc.
  - API `PATCH /api/projects/{id}` cập nhật tên bài hát / dự án, tự động đồng bộ score revision khi có bản nhạc.
  - Kiểm thử backend `test_update_project_title` passed (148/148 passed).
  - TypeScript / Vite production build PASS.
- [x] Tối ưu và hoàn thiện tính năng in / xuất PDF:
  - Bổ sung nút In nhanh (icon Máy in) trên toolbar khuông nhạc, hỗ trợ `window.print()` / `Ctrl+P`.
  - Bổ sung CSS `@media print` chuẩn A4 portrait: tự động ẩn toàn bộ UI chrome (sidebar, player, inspector), khuông nhạc đen trắng sắc nét, phân trang tự động.
  - Gia cố `exportPdf.ts`: hỗ trợ đường dẫn dự phòng cho font Noto Sans, trích xuất kích thước SVG linh hoạt.
  - Nâng thời gian giữ URL Blob lên 60 giây trong `App.tsx`, ngăn Chrome/Edge ngắt kết nối tải file.
  - Thêm tooltip hướng dẫn trên các nút xuất file khi bị khóa (chưa review hoặc chưa lưu).


