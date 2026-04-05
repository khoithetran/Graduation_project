# Phát Hiện Mũ Bảo Hộ

Ứng dụng FastAPI + Streamlit để phát hiện mũ bảo hộ theo thời gian thực sử dụng YOLOv8.

## Cấu Trúc Dự Án

```
.
├── src/              # Backend (FastAPI, inference YOLOv8)
├── frontend/         # Giao diện React + Vite (cũ)
├── app.py            # Giao diện Streamlit (triển khai)
├── models/           # File trọng số YOLO (.pt / .onnx)
├── data/             # Dữ liệu runtime (lịch sử, video, update pool)
├── deployment/       # Dockerfile và docker-compose
├── requirements.txt
└── .gitignore
```

## Chạy Trên Máy Cục Bộ

### Cách 1 — Streamlit (Đơn giản)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
streamlit run app.py
```

Mở trình duyệt tại `http://localhost:8501`

### Cách 2 — FastAPI + React (Đầy đủ tính năng)

**Terminal 1 — Backend (cổng 8000):**

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python backend/server.py
```

**Terminal 2 — Frontend (cổng 5173):**

```bash
cd frontend
npm install
npm run dev
```

Mở `http://localhost:5173` trên trình duyệt.

> Cả hai terminal phải chạy đồng thời.

## Triển Khai lên Streamlit Community Cloud

1. Push code lên GitHub (đảm bảo `models/yolov8s_ap.pt` đã được commit)
2. Truy cập [share.streamlit.io](https://share.streamlit.io) và đăng nhập bằng GitHub
3. Chọn **New app** → chọn repo → nhánh `main` → file `app.py`
4. Nhấn **Deploy** (lần đầu mất khoảng 5 phút)

## Các API Endpoint Chính

| Phương thức | Đường dẫn | Mô tả |
|-------------|-----------|-------|
| GET | `/health` | Kiểm tra trạng thái model |
| POST | `/predict` | Inference một ảnh |
| POST | `/api/detect/image` | Phát hiện + lưu lịch sử |
| GET | `/api/history` | Danh sách sự kiện đã phát hiện |
| POST | `/api/upload-video` | Tải video lên để xử lý |
| GET | `/api/stream/video` | Stream video đã xử lý (MJPEG) |
| GET | `/api/stream/video/alerts` | Lấy cảnh báo vi phạm của video |

## Docker

```bash
docker compose -f deployment/docker-compose.yml up --build
```

## Lưu Ý

- Đặt file trọng số vào thư mục `models/` (ví dụ: `models/yolov8s_ap.pt`)
- Để đổi model, đặt biến môi trường `MODEL_PATH`
- Dữ liệu runtime (ảnh lịch sử, video tải lên) đã được gitignore — chỉ cấu trúc thư mục được theo dõi
