# Kiểm chứng bản 0.1 — cập nhật 21/09/2026

## Cập nhật lyrics và workflow ngày 21/09

- Toàn bộ suite: **113 passed**, 2 cảnh báo deprecation từ Starlette/TestClient. TypeScript và Vite production build thành công.
- Xóa/khôi phục: kiểm tra giữ nguyên audio, score và export, khóa truy cập dự án trong thùng rác, chặn xóa khi queued/running, xác thực cookie và thao tác lặp lại. Phân tích lại với `melody_role=vocal` giữ bản instrumental cũ cho đến khi kích hoạt bản mới.
- SRT/LRC: UTF-8/BOM/UTF-16, timestamp, offset, enhanced LRC, giới hạn tệp, căn lời và giữ từ chưa gắn nốt; kiểm tra revision bất biến, chuyển giọng và sửa liên kết lời–nốt.
- Lời trong MusicXML/PDF: tiếng Việt, nhiều khổ, kiểu âm tiết, nốt nối trong/qua ô nhịp không lặp chữ. Đã xuất PDF bằng MuseScore và render kiểm tra trực quan.
- API đính kèm lời trước phân tích chạy qua FFmpeg/DSP thật trong test; kết quả có 8 từ. API chặn export cả ba định dạng trước xác nhận, chặn khi có job đang chạy, không cho PUT tự đánh dấu reviewed, chặn đường tải artifact cũ sau khi lưu sửa.
- Web UI: upload SRT vào bản nhạc, sửa liên kết 8 từ, lưu và kiểm tra lời trên khuông. Chọn Piano/Violin, nạp mẫu âm local và điều khiển phát không ghi nhận console error. Xác nhận bản kiểm thử mở cả ba nút tải file.
- Web UI cũng đã upload WAV và đính kèm LRC trước phân tích; DSP tạo 8 nốt và 8 từ, giữ từ chưa khớp để sửa trong bước kiểm tra, các nút tải vẫn bị khóa. Hai dự án có tên bắt đầu bằng **Kiểm thử** là dữ liệu tổng hợp dùng xác minh tính năng.
- Đây là kiểm chứng chức năng và dữ liệu tổng hợp, không phải đánh giá chất lượng phiên âm hay độ tự nhiên âm sắc trên một bộ bài hát chuẩn.

## Môi trường thực

Windows 11, RTX 3060 12 GB, RAM 32 GB. API dùng Python 3.12; worker model dùng Python 3.11.15, PyTorch 2.8.0+cu126 và Transformers 4.45.2. FFmpeg và MuseScore 4 đã có trên máy. Frontend React/TypeScript được build và phục vụ tại `http://127.0.0.1:8765`.

## Kết quả nền ngày 20/09 (trước mở rộng lyrics/workflow)

| Kiểm tra | Kết quả |
| --- | --- |
| `python -m pytest -q` | **37 passed**; 2 cảnh báo deprecation từ Starlette/TestClient, không có test lỗi |
| `npm run build` | TypeScript và Vite production build thành công |
| Ký âm | MusicXML round-trip, dấu lặng, nối nốt qua vạch nhịp, phân số/triplet, slash chord, unknown/N.C., chuyển giọng và MIDI |
| Lưu dự án | Revision bất biến, chống ghi đè khi revision cũ, giữ bản chỉnh khi phân tích lại, kích hoạt bản AI mới tường minh |
| API | Upload audio thật qua FFmpeg, DSP với đáp án C4–C5, sửa/lưu/export, hủy job, từ chối file hoặc score lỗi, bảo vệ origin/cookie/host |
| Trình duyệt | Nhập scale tổng hợp, tempo 100, DSP trả 8 nốt đúng cao độ; dựng SVG khuông nhạc, sửa nốt, thêm hợp âm, lưu đến revision 3; xuất PDF và tải MIDI; kiểm tra tiến độ phát, phát/dừng giai điệu dựng lại và hiển thị sheet dài; không ghi nhận console error trong phiên kiểm tra |
| PDF thực | MuseScore xuất thành công trên Windows; đã render kiểm tra dấu nối, slash chord, triplet, dấu lặng và chữ tiếng Việt |
| Cài runtime | Script ghim rõ hậu tố `+cpu`/`+cu126`; PowerShell parse và CUDA dry-run thành công, giữ runtime GPU hiện tại |

## Inference SheetSage2 thật

Model và encoder được ghim commit, dùng snapshot local và chế độ Hugging Face offline. Xem [model-setup.md](model-setup.md) cho phiên bản và giấy phép.

1. **Tín hiệu tổng hợp 4 giây:** 8 nốt, 2 khoảng hợp âm; inference 6,609 giây; toàn luồng 42,38 giây; peak PyTorch allocated 3.370,37 MiB. Bằng chứng: `.cache/model-smoke/smoke-result.json`.
2. **Bản thu người dùng nhập vào ứng dụng, dài 479,4 giây:** model hoàn thành 3 cửa sổ và tạo 303 nốt nhạc cụ, 164 khoảng hợp âm trong score của ứng dụng. Model báo inference 29,610 giây và peak PyTorch allocated 3.380,33 MiB. Events, ABC, MIDI, beat/key/chord/structure từ upstream được giữ trong thư mục `runs` của dự án.

Các số bộ nhớ trên là bộ nhớ do PyTorch cấp phát trong worker, không phải tổng VRAM toàn máy. Thời gian inference không bao gồm toàn bộ thời gian upload, giải mã và nạp model. Số nốt/hợp âm đầu ra chỉ chứng minh luồng chạy thành công, **không đo độ đúng âm nhạc**.

## Giới hạn còn lại

- Người dùng cần chọn tempo, giọng và nhịp cố định; adapter chưa sử dụng tempo map/beat map upstream để khắc nhạc rubato hoặc đổi nhịp.
- Cần nghe kiểm tra cao độ, quãng tám, hợp âm và lượng tử hóa trước khi dùng sheet. Chưa có benchmark chất lượng trên bộ dữ liệu bài hát có đáp án.
- Nghe trực tiếp trong Web UI dựng lại một bè giai điệu bằng sáu bộ mẫu nhạc cụ local. Mẫu âm hữu hạn có thể tắt trước cuối nốt rất dài; chưa mô phỏng articulation. MIDI có tùy chọn bè đệm hợp âm tổng hợp; lựa chọn nhạc cụ nghe thử chưa thay nhạc cụ MIDI.
- CPU có đường cài đặt nhưng chưa benchmark inference. Chưa kiểm tra thời gian/độ chính xác trên mọi định dạng và mọi kiểu phối khí.
- Chưa chép tổng phổ đa nhạc cụ, tự nhận dạng lyrics từ audio hay guitar TAB. Đã hỗ trợ lời SRT/LRC do người dùng cung cấp. Lộ trình mở rộng nằm trong `output/IMPLEMENTATION_PLAN.vi.md` và `output/AGENT_BACKLOG.vi.md`.
