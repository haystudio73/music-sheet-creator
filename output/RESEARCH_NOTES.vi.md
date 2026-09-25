# Đối chiếu nghiên cứu: audio → sheet nhạc chạy local

Ngày kiểm chứng: **19/09/2026**. Tài liệu đầu vào: **Tạo Sheet Nhạc Từ Audio & Ứng Dụng AI Local.pdf**, 12 trang. Nội dung PDF được xem là tài liệu tham khảo; các đề xuất bên trong không tự động trở thành yêu cầu triển khai.

Yêu cầu đã chốt với người dùng: **ưu tiên lead sheet gồm giai điệu và hợp âm; RTX 3060 12 GB, RAM 32 GB**. Windows là giả định dựa trên môi trường hiện tại. Đây là nghiên cứu từ tài liệu, model card và mã nguồn; chưa chạy benchmark mô hình trên máy người dùng.

## 1. Những điểm giữ lại và cần sửa trong PDF

| Vị trí | Nhận định sau đối chiếu | Điều chỉnh khi lập kế hoạch |
|---|---|---|
| Trang 1–2 | Tách cao độ, nhịp, nhạc cụ và ký âm là các bài toán khác nhau. | Giữ kiến trúc nhiều tầng; đo lỗi từng tầng. |
| Trang 5–6 | Bảng hiệu năng trộn tên mô hình, cột dữ liệu và phần cứng đo. | Bỏ bảng này khỏi căn cứ lựa chọn cấu hình. |
| Trang 5, 8 | Có đường chạy CPU cho YourMT3; không có cơ sở kết luận mọi model lớn đều bắt buộc 4090/A100. | Đo checkpoint thực tế trên 3060; phân biệt chạy được với tốc độ chấp nhận được. |
| Trang 8 | ONNX phù hợp một số model, không phải hợp đồng chung cho toàn pipeline. | Adapter riêng cho PyTorch/ONNX và kiểm tra tương đương trước tối ưu. |
| Trang 6–8 | Các nguồn về sinh nhạc và LLM không chứng minh khả năng phục hồi chính xác bản phổ gốc. | Luật ký âm và validator là đường chính; LLM là tính năng đề xuất sau này. |
| Trang 8–9 | Kết xuất đẹp không sửa được nhận dạng sai. | Tách kiểm thử âm nhạc, cấu trúc MusicXML và bố cục PDF. |

Chi tiết lỗi benchmark: Nano 26,3K tham số và tốc độ 1.622,5× là **Harmonica Nano**. Dòng 3,2M tham số/346,5× thuộc **Harmonica Large**, không phải MuScriptor Large. Tốc độ bảng gốc đo trên RTX 4090. Cột PDF ghi Slakh-stem chép số từ URMP-stem. Thí nghiệm stem không đại diện trực tiếp cho bản phối đầy đủ. Không suy ra độ chính xác sheet từ Frame F1. [Paper Harmonica, mục 4 và bảng 1](https://arxiv.org/html/2609.04640v1).

YourMT3 có mã inference chọn CPU khi không có CUDA. Điều này chứng minh đường thực thi, chưa chứng minh hiệu năng trên laptop. [Mã inference CPU của tác giả](https://huggingface.co/spaces/mimbres/YourMT3-cpu/blob/b1432b1a52fba003033905ce8ddabc1e1a13d65c/model_helper.py).

Text2Score giải quyết sinh bản nhạc từ lời nhắc; MusPyExpress giải quyết biểu diễn expression text. Hai nguồn này không đủ để giao LLM tự thêm dấu diễn cảm như dữ kiện nghe được. [Text2Score](https://arxiv.org/html/2605.13431v1), [MusPyExpress](https://arxiv.org/html/2608.21678v1). LilyBench cũng chỉ ra giới hạn trong hiểu cấu trúc ký âm của những LLM được kiểm tra. [LilyBench](https://arxiv.org/pdf/2606.08722).

## 2. Các ứng viên mới, đúng với bài toán

### SheetSage2: thử nghiệm đầu tiên cho lead sheet

**ID:** `m-a-p/SheetSage2`. Model card có cập nhật benchmark ngày 14–16/09/2026, xuất ABC, MIDI và sự kiện giai điệu/hợp âm/nhịp/giọng/cấu trúc. Có hai nguồn giai điệu Vocal và Ins; chưa đồng nghĩa nhận dạng từng nhạc cụ. Weights là CC-BY-NC-4.0. Melody F1 công bố dùng pitch class, nên không đo lỗi quãng tám. Báo cáo kỹ thuật riêng còn được ghi là sắp công bố. [Model card chính chủ](https://huggingface.co/m-a-p/SheetSage2).

**Kích thước cần tính đủ:** phần adapter được HF hiển thị khoảng 57,2M tham số; encoder cha `m-a-p/MERT-v2-FullSong` khoảng 632M. Không dự trù VRAM dựa riêng vào adapter. [Encoder cha](https://huggingface.co/m-a-p/MERT-v2-FullSong), [cấu hình](https://huggingface.co/m-a-p/SheetSage2/blob/main/config.json).

**Lưu ý đặc biệt cho GPU 12 GB:** inference lấy cửa sổ 300 giây; `slice_audio` pad đoạn thiếu đến độ dài cửa sổ. Giới hạn đầu vào 30 giây không đảm bảo giảm peak VRAM encoder. Chưa tìm thấy số đo chính chủ trên RTX 3060 12 GB. [Pipeline](https://huggingface.co/m-a-p/SheetSage2/blob/main/pipeline_sheetsage2.py), [xử lý audio](https://huggingface.co/m-a-p/SheetSage2/blob/main/audio_sheetsage2.py).

**Môi trường:** requirements hiện pin PyTorch/torchaudio 2.8.0, Transformers 4.45.2, huggingface-hub 0.36.0. Hướng cài đặt nêu Python 3.10/3.11. Native Windows cần smoke test; chưa coi là chứng nhận tương thích. [Requirements](https://huggingface.co/m-a-p/SheetSage2/blob/main/requirements.txt).

**Đầu ra và chuyển đổi:** có renderer ABC dùng abcjs và Chromium/Playwright để xuất PDF/SVG/PNG offline. MusicXML là hạng mục phải phát triển thêm. [Renderer](https://huggingface.co/m-a-p/SheetSage2/blob/main/rendering_sheetsage2.py), [exporter](https://huggingface.co/m-a-p/SheetSage2/blob/main/exports_sheetsage2.py).

Mã notation dùng hai voice Vocal/Ins và lưới chia beat; cần kiểm thử triplet, swing và các đoạn đổi nhịp. Không coi chuyển ABC sang MusicXML bằng một lệnh là bảo toàn tuyệt đối: bộ đọc ABC của music21 có giới hạn về voice. [Notation của model](https://huggingface.co/m-a-p/SheetSage2/blob/main/notation_sheetsage2.py), [ABC parser của music21](https://music21.org/music21docs/_modules/music21/abcFormat.html).

**Giấy phép code:** chưa xác minh được giấy phép độc lập rõ ràng cho toàn bộ Python code trong repo. Không ghi nhãn MIT/Apache cho code này. Cần làm rõ trước khi sao chép hoặc phân phối tích hợp. [LICENSE hiện có](https://huggingface.co/m-a-p/SheetSage2/blob/main/LICENSE).

Revision quan sát để tái lập nghiên cứu: `80af707174fc7ee521c25925d5f014729f0e61ae`; commit này sửa README, không phải chứng cứ model weights vừa đổi. Khi triển khai phải kiểm lại manifest toàn bộ dependency thay vì tự chuyển sang HEAD mới. [Commit đã kiểm chứng](https://huggingface.co/m-a-p/SheetSage2/commit/80af707174fc7ee521c25925d5f014729f0e61ae).

### MuScriptor: ứng viên cho sheet từng nhạc cụ ở giai đoạn tiếp theo

**HF:** `MuScriptor/muscriptor-small`, `MuScriptor/muscriptor-medium`, `MuScriptor/muscriptor-large`. Công trình công bố tháng 07/2026. Có CLI, giao diện local, đường Windows CUDA, và xuất MusicXML/PDF từng bè qua MuseScore 4. Code MIT; weights CC-BY-NC-4.0 và cần quyền tải. Tài liệu cảnh báo rubato làm giảm chất lượng ký âm. Khởi đầu bằng small/medium trong thử nghiệm 12 GB; không suy ra large phù hợp chỉ từ dung lượng weights. [Repo chính chủ](https://github.com/muscriptor/muscriptor), [paper](https://arxiv.org/abs/2607.08168), [HF Small](https://huggingface.co/MuScriptor/muscriptor-small), [HF Medium](https://huggingface.co/MuScriptor/muscriptor-medium), [HF Large](https://huggingface.co/MuScriptor/muscriptor-large).

### Basic Pitch và Harmonica

Basic Pitch là baseline nhẹ có ONNX và nhiều runtime; phù hợp một nhạc cụ tại một thời điểm hơn là tách nhãn nhạc cụ trong cả bản phối. Nó không cung cấp riêng toàn bộ bài toán hợp âm, nhịp và lead sheet. Nên lấy artifact từ Spotify thay vì gắn nhãn bản mirror HF là chính chủ. [Repo Spotify](https://github.com/spotify/basic-pitch).

Harmonica xuất hiện tháng 09/2026 và đáng theo dõi cho inference nhẹ. Trong lần nghiên cứu này chưa xác minh được public checkpoint HF/code chính chủ có thể đưa ngay vào ứng dụng. Chỉ đưa vào danh sách theo dõi. [Trang tác giả](https://www.oulongshen.xyz/amt).

### Phương án dự phòng cần biết trước

SheetSage1 (`chrisdonahue/sheetsage`) có pipeline lead sheet hoàn chỉnh. Chế độ mặc định không yêu cầu GPU; nhánh Jukebox yêu cầu từ 12 GB VRAM và download thêm. Upstream hướng Linux/Docker, nên cần thử riêng nếu dùng trên Windows qua WSL2. Code MIT nhưng transcription weights CC-BY-NC-SA-3.0: đây không phải cách tự giải quyết điều kiện thương mại. [Repo chính chủ](https://github.com/chrisdonahue/sheetsage).

Beat This! cung cấp beat/downbeat trên CPU/CUDA. Code và published weights được tác giả công bố MIT; checkpoint `small0`/`final0` có nguồn chính chủ ngoài HF. Chọn `dbn=False` tránh kéo thêm madmom vào đường mặc định. [Repo chính chủ](https://github.com/CPJKU/beat_this).

ChordFormer (`mwaseemrandhawa/ChordFormer`) có checkpoint, ensemble/HMM và xuất nhãn hợp âm theo thời gian. Chưa xác minh được official HF model ID hoặc điều kiện code/weights mới đủ rõ để coi đã sẵn sàng phân phối. Chỉ là ứng viên thử sau khi làm rõ. [Repo chính chủ](https://github.com/mwaseemrandhawa/ChordFormer).

## 3. Hệ sinh thái ký âm và vận hành

- **MusicXML 4.0:** định dạng trao đổi sheet; có schema để kiểm tra cú pháp. Hợp lệ schema chưa chứng minh đúng bản nhạc. [Đặc tả của Music Notation Community Group](https://www.w3.org/2021/06/musicxml40/).
- **music21:** dùng xây dựng cấu trúc nhạc và xuất MusicXML. Không coi đây là thuật toán tự khắc phục mọi lỗi nhịp/nhận dạng. [MusicXML exporter](https://music21.org/music21docs/moduleReference/moduleMusicxmlM21ToXml.html).
- **OpenSheetMusicDisplay:** ứng viên hiển thị MusicXML trên frontend. Cần viết lớp thao tác/sửa dữ liệu riêng. [Repo OSMD](https://github.com/opensheetmusicdisplay/opensheetmusicdisplay).
- **MuseScore:** ứng viên xuất PDF và ứng dụng kiểm tra khả năng mở file. Ghim phiên bản CLI đã thử trên Windows. [CLI chính thức](https://handbook.musescore.org/appendix/command-line-usage).
- **Hugging Face Hub:** hỗ trợ tải/cache theo revision; ứng dụng phải ghim đầy đủ model cha, adapter và custom code. [Download guide](https://huggingface.co/docs/huggingface_hub/guides/download). Chế độ offline cần kiểm tra cả runtime/asset phụ, không chỉ đặt cờ Hub. [Biến môi trường](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables).
- **FastAPI:** API điều phối nên tách worker inference nặng. [Lưu ý về tác vụ nền](https://fastapi.tiangolo.com/tutorial/background-tasks/).
- **Tauri 2:** khả năng sidecar phù hợp launcher desktop về sau; chưa phải lý do gộp tất cả runtime AI vào một executable. [Sidecar](https://v2.tauri.app/develop/sidecar/).
- **mir_eval:** công cụ tham chiếu khi tính note precision/recall/F1. Phải ghi rõ tolerance và báo cáo thêm lỗi octave. [Transcription metrics](https://mir-eval.readthedocs.io/latest/api/transcription.html).

## 4. Mức độ chắc chắn

Đã xác minh từ nguồn: ID các ứng viên chính, đầu ra được công bố, luồng cửa sổ/padding, phụ thuộc nền, các hạn chế giấy phép nêu trên và lỗi bảng PDF.

Chưa xác minh trên máy thực: peak VRAM, tốc độ, độ chính xác trên nhạc Việt/Suno, chất lượng MusicXML chuyển đổi, độ ổn định bộ cài Windows và khả năng chạy hoàn toàn offline sau cài đặt. Các nội dung đó là **cổng nghiệm thu trong kế hoạch**, không phải kết quả đã đạt.

“Mới nhất” ở đây là các ứng viên có nguồn kiểm chứng được tại ngày nghiên cứu, không phải cam kết bao phủ mọi model trên Hugging Face hoặc khẳng định một mô hình đứng đầu tất cả thể loại nhạc.
