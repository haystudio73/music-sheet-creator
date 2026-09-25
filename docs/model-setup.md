# SheetSage2 chạy local trên Windows 11

Ứng dụng dùng hai môi trường riêng: `.venv` cho API/chuẩn hóa ký âm và `.venv-model` (Python 3.11) cho SheetSage2. Môi trường API không import PyTorch. Mỗi job AI chạy trong tiến trình riêng để hủy được inference và giải phóng VRAM khi tiến trình kết thúc.

## Cài đặt

Từ thư mục dự án, chạy PowerShell:

```powershell
.\scripts\setup.ps1
.\scripts\setup-model.ps1
```

`setup-model.ps1` cần `uv`, kết nối Internet để tải lần đầu, và NVIDIA driver hỗ trợ CUDA 12.6 cho bản GPU. Script tạo Python 3.11 trong `.runtime/python`, cài PyTorch 2.8.0+cu126, torchaudio 2.8.0+cu126, Transformers 4.45.2 và dependencies đã chọn theo runtime upstream. Dùng `-Cpu` để cài wheel PyTorch/torchaudio 2.8.0+cpu; bản này chưa được đo tốc độ cho bài hát dài. Chạy lại với `-Cpu` chuyển môi trường hiện có sang CPU; chạy lại không có `-Cpu` chuyển về CUDA 12.6. Script ghim rõ hậu tố wheel để thay đúng biến thể, giữ môi trường đã có và kiểm tra weights trước khi tải lại.

Weights tải trực tiếp từ hai repository công khai, theo commit cố định trong `models/registry.json`:

| Thành phần | Repository | Commit | Dung lượng weights |
| --- | --- | --- | --- |
| Adapter + decoder | [m-a-p/SheetSage2](https://huggingface.co/m-a-p/SheetSage2) | `80af707174fc7ee521c25925d5f014729f0e61ae` | 228,738,564 byte |
| Encoder MERT-v2 | [m-a-p/MERT-v2-FullSong](https://huggingface.co/m-a-p/MERT-v2-FullSong) | `d8ba1c745e733b3908ce6ad16ebeb17ac7600a42` | 2,529,812,848 byte |

Ngoài khoảng 2.76 GB weights, cần chỗ cho Python, CUDA/PyTorch wheels, dependencies và cache cài đặt. Không dùng `main` lúc inference. `models/installed.json` ghi đường dẫn và SHA256 từng file; weights được so với checksum do Hugging Face cung cấp, encoder còn được so với hash cố định trong registry. Worker kiểm tra code/config/weights trước khi bật `trust_remote_code=True` cho custom code đã tải.

Setup không tự chấp nhận điều khoản truy cập. Nếu Hugging Face trả 401/403, người dùng cần tự xem model page và cấp quyền nếu phù hợp. Token tùy chọn lấy từ biến `HF_TOKEN`, không ghi vào file. Trong lần cài thực tế này, cả hai snapshot tải được công khai, không cần token.

Sau setup, inference dùng file local với `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, cache nằm trong thư mục dự án. Audio không gửi tới Hugging Face. Token Hugging Face không được truyền cho worker. FFmpeg dùng để giải mã audio; có thể trỏ `FFMPEG_PATH` đến `ffmpeg.exe` nếu chưa có trong `PATH`.

## Giới hạn của bản đầu

- SheetSage2 tạo events giai điệu và hợp âm thực. Người dùng chọn bè `instrumental` hoặc `vocal`; app lấy đúng track tương ứng. Kết quả luôn mang trạng thái cần kiểm tra.
- Adapter v0 dùng **tempo, giọng và số chỉ nhịp cố định do người dùng chọn**. Thời gian nốt/hợp âm lượng tử hóa thành lưới 1/16; chưa dùng beat map dự đoán để ký âm rubato hoặc thay đổi nhịp. Giữ events/timestamps gốc trong thư mục job để nâng cấp sau.
- Nốt chồng nhau được giữ và có cảnh báo để sửa; không âm thầm cắt mất nốt. Hợp âm chưa hỗ trợ được đánh dấu `unknown`; khác với `N.C.` do model dự đoán rõ ràng.
- Audio tối đa 10 phút. Worker có thời hạn 60 phút và hủy job bằng cách kết thúc tiến trình model.
- Model upstream pad mỗi cửa sổ tới **300 giây**. Cắt audio thật ngắn không bảo đảm giảm peak VRAM của encoder. RTX 3060 12 GB cần đo thực; trạng thái “đã cài” không phải cam kết về chất lượng hay tốc độ trên mọi bài.
- Chế độ **Giai điệu đơn · DSP thử nghiệm** dùng YIN/FFT và NumPy/SciPy để dò một giai điệu sạch. Chế độ này không dùng AI, không tách giai điệu trong bản phối và không tạo hợp âm tự động. Đây là lựa chọn chạy thử luồng local khi model chưa sẵn sàng.

## Kiểm tra lại

```powershell
.\.venv-model\Scripts\python.exe workers\prepare_models.py --probe
.\.venv\Scripts\python.exe -m pytest tests\test_transcription.py -q
.\.venv\Scripts\python.exe -m workers.smoke_model
```

Lệnh cuối tạo tín hiệu nhạc tổng hợp 4 giây rồi chạy **inference thật** qua worker offline. Kết quả được lưu tại `.cache/model-smoke/smoke-result.json`, chi tiết job tại `.cache/model-smoke/job`. Đây là phép thử tích hợp và phần cứng; số nốt/hợp âm xuất ra không phải thước đo độ chính xác trên bản phối thật. Test DSP có đáp án cao độ và thời gian biết trước; test này cũng không đại diện cho khả năng phân tích bài hát nhiều nhạc cụ.

### Kết quả thực trên máy phát triển, 20/09/2026

- Windows 11, NVIDIA GeForce RTX 3060 **12,288 MiB**, driver 610.88; Python 3.11.15, torch 2.8.0+cu126, Transformers 4.45.2.
- Smoke chạy offline thành công: input tổng hợp 4 giây → **8 nốt instrumental, 2 khoảng hợp âm**, không có warning upstream.
- Inference do model báo: **6.609 giây**. Toàn luồng giải mã, kiểm tra checksum, nạp model và dựng score: **42.38 giây** trong lần chạy đầu.
- Peak bộ nhớ GPU do `torch.cuda.max_memory_allocated` báo: **3,370.37 MiB**. Đây là phần PyTorch cấp phát cho worker, không phải tổng VRAM toàn máy hay bảo đảm cho mọi input.
- `tests/test_transcription.py`: **11 test pass**, gồm pitch YIN với họa âm, FFmpeg → DSP với khoảng lặng/thời gian biết trước, input im lặng, hủy trước/trong xử lý, phân biệt unknown/N.C. và chọn bè model.

Sau smoke, ứng dụng cũng đã xử lý thành công bản thu người dùng nhập dài **479,4 giây**, qua 3 cửa sổ: 303 nốt nhạc cụ và 164 khoảng hợp âm trong score. Model báo 29,610 giây inference, peak PyTorch allocated 3.380,33 MiB. Đây là xác nhận chạy được bản thu dài, chưa phải đo độ đúng của nốt, nhịp hay hợp âm. Chi tiết nằm trong [VALIDATION.vi.md](VALIDATION.vi.md).

## Giấy phép

Weights upstream dùng **CC-BY-NC-4.0**. Phù hợp thử nghiệm phi thương mại theo điều kiện của giấy phép; không mặc định cho phép phát hành thương mại. Giữ `LICENSE` và `THIRD_PARTY_NOTICES.md` cùng snapshot. Giấy phép code phải xem cùng các notices upstream, chưa xác nhận một giấy phép code độc lập bao trùm toàn bộ repository. Nâng version model cần xem lại custom code, giấy phép, checksum và chạy lại smoke/benchmark; không tự động chọn model mới nhất mỗi lần khởi động.
