# Lời hát trên bản nhạc

Lời hát được lưu riêng trong từng revision của score; mỗi từ/âm tiết tham chiếu ID của một nốt. Mỗi nốt có một từ ở mỗi khổ (1–20). Kiểu âm tiết đơn/đầu/giữa/cuối giúp khắc dấu nối giữa các âm tiết. Chuyển giọng giữ liên kết lời–nốt; xóa nốt trên Web UI bỏ liên kết nhưng giữ lời.

## Import

Khi upload SRT/LRC, ứng dụng tự loại metadata dạng `[ti:...]`, `[ar:...]`, `[al:...]`, `[by:...]` và nhãn đoạn phổ biến như `[Verse 1]`, `[Chorus]`, `[Pre-Chorus]`, `[Bridge]`, `[Instrumental]`, `[Outro]`. Thẻ ở đầu tệp, riêng dòng hoặc chen giữa lời đều được xử lý trước khi ghép nốt; không đưa tên bài/ca sĩ/nhãn đoạn vào khuông nhạc. Các chữ trong ngoặc không được nhận diện như `[Oh]` vẫn được giữ. Mốc dòng, mốc từng từ và mốc lặp không bị xóa; `[offset:...]` trong LRC vẫn được kiểm tra và áp dụng. Tệp chỉ có metadata, không có lời kèm thời gian, sẽ bị từ chối và không thay bản hiện tại.

Trên Web UI, phân tích audio thành bản nhạc rồi mở **Thêm lời (tùy chọn)** để nhập SRT/LRC. Nút **Xóa / reset lời** tạo revision không có lời và cho phép nhập tệp mới (hoặc nhập lại cùng tệp). Cần lưu các chỉnh sửa trước; lịch sử revision vẫn được giữ. API xóa lời: `DELETE /api/projects/{id}/lyrics`, JSON `expected_revision`. API legacy `/lyrics-source` vẫn hỗ trợ dự án cũ có lời đính kèm trước phân tích.

API `POST /api/projects/{id}/lyrics` nhận multipart `file`, `expected_revision` và `offset_seconds` (−600 đến +600 giây). Phải có bản nhạc đã lưu. Tệp tối đa 1 MiB, 20.000 từ/âm tiết; mỗi ô lời tối đa 200 ký tự. Hỗ trợ UTF-8 (có hoặc không BOM) và UTF-16 có BOM. Tệp lỗi hoặc revision cũ không thay đổi bản hiện tại.

SRT dùng thời điểm đầu/cuối từng đoạn; nhiều dòng được ghép thành từ cách nhau bởi khoảng trắng. LRC dùng mốc đầu câu và mốc tiếp theo; dòng cuối cần khoảng kết thúc ước lượng nếu không có timestamp trống kết thúc. Nên thêm mốc kết thúc để tránh căn lời vào đoạn nhạc dạo sau câu hát.

Mốc lời cần tính từ cùng điểm bắt đầu audio. `offset_seconds` dương dịch lời muộn hơn. Thẻ LRC `[offset:N]` theo quy ước parser dịch lời sớm hơn N mili giây; nếu tệp dùng quy ước khác, điều chỉnh độ dịch khi nhập.

Ví dụ dùng với giai điệu tám nốt ở tempo 100 (lời tổng hợp để kiểm thử):

```text
[00:00.00]Mây bay qua trời
[00:02.40]Nắng lên bên đồi
[00:04.80]
```

## Độ chính xác

SRT/LRC đánh dấu cả câu không có vị trí chính xác từng từ. Ứng dụng phân bổ từ theo thứ tự vào các nốt trong khoảng thời gian đó; ưu tiên timestamp nguồn của nốt, nếu thiếu thì dùng vị trí phách và tempo. Không tự phân tích ngữ âm hoặc tách âm tiết tiếng Anh/ngôn ngữ không dùng khoảng trắng. Có thể tách/ghép chữ và sửa nốt thủ công; tiếng Việt thường dùng được các tiếng cách nhau bởi khoảng trắng.

Lời chưa gắn nốt được giữ để sửa, chưa in trên sheet. Cần nghe đối chiếu kể cả khi mọi từ đã có nốt. Gắn lời vào giai điệu nhạc cụ có thể không khớp giai điệu hát; chọn đúng bè khi phân tích audio.

## Hiển thị và xuất

Web UI hiển thị revision đã lưu bằng OpenSheetMusicDisplay. MusicXML ghi `lyric` trên lần phát đầu mỗi nốt; PDF do OpenSheetMusicDisplay dàn trang A4 từ cùng MusicXML rồi jsPDF/svg2pdf.js tạo file trực tiếp trong trình duyệt, với font Noto Sans nhúng sẵn. Các đoạn nối trường độ không lặp chữ. Chưa có tô sáng karaoke hoặc tổng hợp giọng hát; nút nghe phát giai điệu bằng một trong sáu bộ mẫu nhạc cụ local.

Lưu chỉnh sửa và bấm **Xác nhận đã kiểm tra** mới được tải MusicXML/MIDI/PDF. Nhập lại lời hoặc lưu thay đổi sẽ đặt bản nhạc về trạng thái cần kiểm tra, đồng thời khóa tải cho đến khi xác nhận lại.
