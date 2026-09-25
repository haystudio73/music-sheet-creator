# Hướng dẫn Triển khai Ứng dụng Tạo Sheet Nhạc trên Google Colab (GPU T4)

Tài liệu này hướng dẫn cách chạy toàn bộ ứng dụng (FastAPI backend + SheetSage2 AI model + Web UI frontend) trên Google Colab với GPU T4 miễn phí và truy cập qua đường link Internet bằng Cloudflare Tunnel.

---

## BƯỚC 1: Tạo Notebook & Bật GPU
1. Truy cập [Google Colab](https://colab.research.google.com/) $\to$ **New Notebook**.
2. Vào menu **Runtime (Thời gian chạy)** $\to$ **Change runtime type (Thay đổi loại thời gian chạy)**.
3. Trong mục **Hardware accelerator (Bộ tăng tốc phần cứng)**: Chọn **T4 GPU** $\to$ Bấm **Save**.
4. Kiểm tra GPU bằng cách chạy cell:
   ```bash
   !nvidia-smi
   ```

---

## BƯỚC 2: Đưa Mã Nguồn vào Colab
Bạn có thể chọn 1 trong 2 cách:

### Cách A: Dùng Git Clone (Nếu code đã đẩy lên GitHub)
```bash
!git clone https://github.com/<tai-khoan>/<repo>.git /content/create-music-sheets
%cd /content/create-music-sheets
```

### Cách B: Nén và Tải lên trực tiếp
1. Nén toàn bộ thư mục dự án trên máy tính thành file `create-music-sheets.zip` (bỏ qua `.venv`, `.venv-model`, `.git`).
2. Kéo thả file `create-music-sheets.zip` vào khung File của Colab.
3. Giải nén bằng lệnh:
```bash
!mkdir -p /content/create-music-sheets
!unzip -q /content/create-music-sheets.zip -d /content/create-music-sheets
%cd /content/create-music-sheets
```

---

## BƯỚC 3: Cài đặt Dependencies

Chạy cell sau để cài đặt các thư viện cần thiết cho FastAPI và SheetSage2:

```bash
# 1. Cài các thư viện backend API
!pip install -q fastapi uvicorn python-multipart pydantic music21 mido httpx

# 2. Cài các thư viện AI phục vụ SheetSage2 (huggingface-hub mới tương thích môi trường Colab)
!pip install -q transformers==4.45.2 "huggingface-hub>=1.23.0" safetensors mir_eval pretty_midi
```

---

## BƯỚC 4: Tải Trọng số Mô hình (SheetSage2 & MERT-v2)

Chạy cell sau để tải snapshot chính thức của mô hình:

```bash
# Tải weights model về thư mục cache
!python workers/prepare_models.py

# Xác minh môi trường PyTorch & GPU
!python workers/prepare_models.py --probe
```
*(Nếu thành công, bạn sẽ thấy thông báo `status` hiển thị `cuda: true` kèm tên GPU NVIDIA).*

---

## BƯỚC 5: Thiết lập Biến Môi trường & Khởi chạy Server

Chạy cell sau để thiết lập cấu hình và mở cổng Cloudflare Tunnel:

```python
import os, sys, subprocess, time

# 1. Thiết lập biến môi trường tối ưu cho Colab
os.environ["SHEETSAGE2_PYTHON"] = sys.executable   # Dùng trực tiếp Python của Colab
os.environ["SHEET_STUDIO_NETWORK_MODE"] = "1"      # Cho phép truy cập qua mạng/Internet
os.environ["SHEET_STUDIO_MAX_WORKERS"] = "1"       # 1 worker để tránh tràn 15GB VRAM của T4
os.environ["SHEET_STUDIO_MAX_QUEUE"] = "10"        # Hàng đợi tối đa 10 bài
os.environ["SHEET_STUDIO_MAX_ACTIVE_PER_IP"] = "1" # Mỗi IP chỉ phân tích 1 bài tại 1 thời điểm
os.environ["SHEET_STUDIO_ALLOWED_HOSTS"] = "*"

# 2. Cài đặt cloudflared để tạo đường link truy cập ra ngoài Internet
!wget -q -nc https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
!dpkg -i cloudflared-linux-amd64.deb > /dev/null 2>&1

# 3. Mở Cloudflare Tunnel ngầm
subprocess.Popen(["cloudflared", "tunnel", "--url", "http://127.0.0.1:8765"],
                 stdout=open("/content/tunnel.log", "w"), stderr=subprocess.STDOUT)

# Chờ 3 giây để lấy đường link public
time.sleep(3)
with open("/content/tunnel.log", "r") as f:
    for line in f:
        if "trycloudflare.com" in line:
            print("==================================================")
            print("👉 ĐƯỜNG LINK TRUY CẬP ỨNG DỤNG CỦA BẠN:")
            print(line.strip())
            print("==================================================")

# 4. Khởi chạy Backend FastAPI + Web UI
!python -m uvicorn backend.app:app --host 0.0.0.0 --port 8765
```

---

## 🎯 Kiểm tra sau khi khởi chạy:
1. Nhấp vào đường link có đuôi `https://xxxx.trycloudflare.com`.
2. Giao diện Web **Sheet Studio** sẽ mở ra trên trình duyệt của bạn.
3. Bạn có thể upload file audio (WAV, MP3, FLAC) và bấm **Bắt đầu phân tích**. Quá trình suy luận của SheetSage2 sẽ chạy trực tiếp trên GPU T4 của Google Colab và trả về bản sheet nhạc!
