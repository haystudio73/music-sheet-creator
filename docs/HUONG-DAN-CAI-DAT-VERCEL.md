# Hướng dẫn Từng Bước Cài đặt & Triển khai Ứng dụng trên Vercel (vercel.app)

Tài liệu này hướng dẫn chi tiết cách triển khai giao diện Web của ứng dụng **Sheet Studio** (Tạo Sheet Nhạc) lên nền tảng **Vercel** (`*.vercel.app`) với CDN toàn cầu tốc độ cao và kết nối tới Backend xử lý AI/âm nhạc.

---

## 📌 Tổng quan Kiến trúc Kỹ thuật & Lưu ý Quan Trọng

Trước khi bắt đầu, cần hiểu rõ đặc tính kỹ thuật của hệ thống để triển khai đúng cách:

1. **Frontend (Web UI)**:
   - Viết bằng **React + TypeScript + Vite**, hiển thị khuông nhạc bằng OpenSheetMusicDisplay (OSMD) và Smoosic Editor.
   - **Hoàn toàn tương thích và cực kỳ tối ưu khi chạy trên Vercel** (Global Edge CDN, tự động SSL/HTTPS, CI/CD tự động khi push GitHub).

2. **Backend (Python + AI Models + FFmpeg + MuseScore)**:
   - Dùng **FastAPI**, lưu trữ dữ liệu vào thư mục `data/` (SQLite, tệp audio gốc, lịch sử bản ghi, file xuất).
   - Mô hình AI **SheetSage2 & MERT-v2** có dung lượng file trọng số (weights) hơn **3–4 GB**, cần bộ nhớ RAM/VRAM và card GPU để suy luận.
   - Các tác vụ phân tích âm thanh kéo dài từ **30 giây đến vài phút**.
   - **Vercel Serverless Functions không hỗ trợ môi trường này** do các giới hạn phần cứng:
     - Giới hạn gói mã nguồn serverless tối đa: 250 MB (PyTorch đã hơn 700 MB).
     - Giới hạn thời gian chạy (timeout): 10 giây (gói Hobby) / 60 giây (gói Pro).
     - Giới hạn kích thước upload body: tối đa **4.5 MB** (trong khi audio tải lên thường từ 10 MB – 50 MB).
     - Ổ đĩa serverless là tạm thời (ephemeral), mọi file nhạc đã lưu sẽ biến mất khi container tắt.

👉 **Mô hình triển khai chuẩn quốc tế (Decoupled Architecture)**:
- **Frontend**: Triển khai trên **Vercel.app** (miễn phí, nhanh, tên miền đẹp).
- **Backend**: Chạy tại **Máy tính cá nhân có GPU** (qua Cloudflare Tunnel miễn phí) **HOẶC** trên **Google Colab (GPU T4)** **HOẶC** trên **Cloud VPS / Render / Railway**.

---

## BƯỚC 1: Chuẩn bị Mã nguồn & Đưa lên GitHub

Nếu bạn đã có mã nguồn trên GitHub, có thể bỏ qua bước này sang Bước 2.

1. Đảm bảo file `.gitignore` trong thư mục gốc dự án đã bỏ qua các thư mục nặng:
   ```gitignore
   node_modules/
   .venv/
   .venv-model/
   .cache/
   data/
   tmp/
   output/
   dist/
   ```

2. Khởi tạo Git và đẩy mã nguồn lên GitHub:
   ```bash
   git init
   git add .
   git commit -m "feat: chuẩn bị cấu hình triển khai Vercel"
   git branch -M main
   git remote add origin https://github.com/<tai-khoan-github>/<ten-repo>.git
   git push -u origin main
   ```

---

## BƯỚC 2: Triển khai Frontend lên Vercel.app

1. Truy cập [https://vercel.com](https://vercel.com) và đăng nhập bằng tài khoản GitHub của bạn.
2. Tại bảng điều khiển Vercel Dashboard, nhấp vào nút **Add New...** $\to$ Chọn **Project**.
3. Trong danh sách kho lưu trữ GitHub của bạn, tìm kho lưu trữ chứa dự án này và bấm **Import**.

### Thiết lập cấu hình Project trên Vercel:

| Mục cấu hình | Giá trị thiết lập | Ghi chú |
|---|---|---|
| **Project Name** | Đặt tên tuỳ thích (ví dụ: `sheet-studio-app`) | Tên miền sẽ là `https://<ten>.vercel.app` |
| **Framework Preset** | `Vite` | Vercel thường tự nhận diện |
| **Root Directory** | Bấm **Edit** $\to$ Chọn `frontend` | **Rất quan trọng**: giao diện nằm trong thư mục `frontend` |
| **Build Command** | `npm run build` | Mặc định (tự động chạy `prepare-editor.mjs` trước) |
| **Output Directory** | `dist` | Mặc định của Vite |
| **Install Command** | `npm install` | Mặc định |

### Thiết lập Biến Môi Trường (Environment Variables):
Trong mục **Environment Variables**, thêm biến sau:
- **Key**: `VITE_API_URL`
- **Value**: Địa chỉ URL của Backend của bạn (ví dụ: `https://xxxx.trycloudflare.com` hoặc `https://api.yourdomain.com`).
  *(Nếu hiện tại bạn chưa bật backend, có thể để tạm `http://127.0.0.1:8765` hoặc để trống, sau khi có URL backend ở Bước 3 bạn có thể vào Settings $\to$ Environment Variables để cập nhật lại).*

4. Nhấp vào nút **Deploy**.
5. Chờ Vercel hoàn tất quá trình build và đóng gói (khoảng 1–2 phút). Khi màn hình xuất hiện pháo hoa chúc mừng, bạn đã có đường link chính thức:
   👉 `https://<ten-du-an>.vercel.app`

---

## BƯỚC 3: Thiết lập Backend Kết nối với Vercel

Chọn **1 trong 3 phương án** dưới đây để làm backend cho ứng dụng:

### 🌟 PHƯƠNG ÁN A (Khuyên dùng nhất): Chạy Backend tại máy tính cá nhân + Cloudflare Tunnel
> **Ưu điểm**: Hoàn toàn MIỄN PHÍ, tận dụng sức mạnh GPU NVIDIA có sẵn trên máy của bạn để phân tích nhạc bằng AI SheetSage2 siêu nhanh, không giới hạn dung lượng lưu trữ, không cần mở port modem (NAT/Port Forwarding).

1. **Khởi chạy Backend ở chế độ mạng (Network Mode)**:
   Mở PowerShell tại thư mục dự án và chạy:
   ```powershell
   $env:SHEET_STUDIO_NETWORK_MODE="1"
   $env:SHEET_STUDIO_ALLOWED_HOSTS="*"
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1
   ```
   *(Backend sẽ khởi động tại `http://127.0.0.1:8765` với chế độ cho phép kết nối từ xa và bật CORS).*

2. **Cài đặt Cloudflare Tunnel (`cloudflared`) để cấp link HTTPS Internet**:
   - Tải `cloudflared.exe` cho Windows từ trang chính thức của Cloudflare:
     [https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe](https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe)
   - Đổi tên file tải về thành `cloudflared.exe` và đặt vào một thư mục tiện lợi (ví dụ trong thư mục dự án).
   - Mở thêm một cửa sổ PowerShell khác và chạy lệnh:
     ```powershell
     .\cloudflared.exe tunnel --url http://127.0.0.1:8765
     ```
   - Trong màn hình terminal sẽ xuất hiện đường link dạng:
     ```text
     +--------------------------------------------------------------------------------------------+
     | Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
     | https://random-words-here.trycloudflare.com                                                |
     +--------------------------------------------------------------------------------------------+
     ```
   - **Copy đường link HTTPS đó** (ví dụ: `https://random-words-here.trycloudflare.com`).

3. **Cập nhật URL vào Vercel**:
   - Vào Vercel Dashboard $\to$ Chọn dự án của bạn $\to$ **Settings** $\to$ **Environment Variables**.
   - Sửa hoặc thêm biến `VITE_API_URL` thành:
     `https://random-words-here.trycloudflare.com`
   - Vào tab **Deployments** $\to$ Bấm vào dấu 3 chấm cạnh bản deploy mới nhất $\to$ Chọn **Redeploy** để áp dụng biến môi trường mới.

---

### 🚀 PHƯƠNG ÁN B: Chạy Backend trên Google Colab (GPU T4 Miễn phí)
> **Ưu điểm**: Không cần mở máy tính cá nhân liên tục; dùng GPU T4 của Google Cloud miễn phí.

1. Làm theo hướng dẫn chi tiết tại [`docs/deploy-colab.md`](deploy-colab.md).
2. Khi Colab khởi chạy xong, bạn sẽ nhận được một đường link Cloudflare Tunnel (ví dụ: `https://xxxx.trycloudflare.com`).
3. Dán link này vào biến môi trường `VITE_API_URL` trên Vercel và bấm **Redeploy**.

---

### ☁️ PHƯƠNG ÁN C: Triển khai Backend lên Cloud VPS / Render / Railway
> **Ưu điểm**: Chạy 24/7 ổn định trên cloud có IP tĩnh hoặc domain riêng.

1. Thiết lập biến môi trường trên server:
   ```bash
   export SHEET_STUDIO_NETWORK_MODE="1"
   export SHEET_STUDIO_ALLOWED_HOSTS="*"
   export SHEET_STUDIO_DATA="/app/data"
   ```
2. Chạy FastAPI bằng Uvicorn:
   ```bash
   uvicorn backend.app:app --host 0.0.0.0 --port 8765
   ```
3. Cài đặt Nginx làm Reverse Proxy hoặc gán domain SSL (ví dụ: `https://api.yourdomain.com`).
4. Cấu hình biến `VITE_API_URL=https://api.yourdomain.com` trên Vercel.

---

## BƯỚC 4: Kiểm tra Hoạt động trên Vercel

1. Mở trình duyệt và truy cập vào đường link Vercel của bạn: `https://your-project.vercel.app`.
2. Kiểm tra các chức năng:
   - ✅ Kéo thả hoặc chọn file bài hát (MP3, WAV, FLAC) để tải lên.
   - ✅ Bấm **Analyze Audio** để dò tempo, key và nhịp.
   - ✅ Bấm **Bắt đầu phân tích** (suy luận AI qua SheetSage2 hoặc DSP).
   - ✅ Xem khuông nhạc hiển thị mượt mà trên trình duyệt.
   - ✅ Thử nghiệm chỉnh sửa nốt, lời bài hát, và nghe thử audio gốc cùng giai điệu dựng lại.
   - ✅ Xác nhận kiểm tra và xuất file **MusicXML**, **MIDI**, **PDF**, **ABC**.

---

## 🛠️ Xử lý Sự cố Thường gặp (Troubleshooting)

### 1. Lỗi "Không kết nối được máy chủ" trên web Vercel
- **Nguyên nhân**: Backend chưa bật, URL Cloudflare Tunnel đã đổi (khi tắt/bật lại), hoặc chưa redeploy Vercel sau khi sửa `VITE_API_URL`.
- **Cách khắc phục**:
  - Kiểm tra xem cửa sổ chạy backend và cửa sổ `cloudflared tunnel` có đang hoạt động không.
  - Thử mở trực tiếp đường link backend trên trình duyệt (`https://xxxx.trycloudflare.com/api/projects`), nếu hiển thị danh sách `[]` dạng JSON tức là backend đang chạy tốt.
  - Đảm bảo biến `VITE_API_URL` trên Vercel đã khớp chính xác với URL backend và đã bấm **Redeploy**.

### 2. Lỗi CORS (Cross-Origin Resource Sharing)
- Backend của ứng dụng đã được tích hợp sẵn middleware CORS khi bật `SHEET_STUDIO_NETWORK_MODE=1`.
- Đảm bảo bạn đã truyền biến môi trường `$env:SHEET_STUDIO_NETWORK_MODE="1"` trước khi chạy server backend.

### 3. File upload lớn bị lỗi 413 trên Vercel
- Nếu bạn gọi API qua cơ chế proxy/rewrite của Vercel, Vercel giới hạn tối đa **4.5 MB**.
- **Giải pháp**: Thiết lập trực tiếp biến `VITE_API_URL` thành URL backend đầy đủ (ví dụ `https://xxxx.trycloudflare.com`). Ứng dụng sẽ gửi file trực tiếp từ trình duyệt đến backend, cho phép upload tệp nhạc lên tới **200 MB** mà không bị giới hạn bởi Vercel.
