---
title: Safety Helmet Detection
emoji: 👷
colorFrom: yellow
colorTo: gray
sdk: docker
pinned: false
---

<div align="center">

# High-Performance Safety Helmet Detection System

**A full-stack AI production system for real-time PPE compliance monitoring**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Hugging%20Face%20Spaces-FFD21E?style=for-the-badge)](https://huggingface.co/spaces/letsgobae/safety-helmet-detection)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-ONNX-purple?style=for-the-badge)](https://docs.ultralytics.com)

</div>

---

## Live Demo

> Try it now — no setup required.

**[letsgobae/safety-helmet-detection on Hugging Face Spaces](https://huggingface.co/spaces/letsgobae/safety-helmet-detection)**

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Real-time Image Detection** | Upload any image and get bounding-box results with class labels and confidence scores in under a second |
| **Video Violation Tracking** | Upload a video and watch ByteTrack follow every person across frames with live MJPEG streaming |
| **Timestamp-Synchronized Alerts** | Click any violation crop to instantly seek the video to that exact moment and pause for inspection |
| **ONNX-Optimized Inference** | Model exported from `.pt` to `.onnx` for significantly lower latency and memory footprint on CPU-only cloud environments |
| **Modern React UI** | Responsive TypeScript + Vite frontend served from the same Docker image — zero CORS friction |
| **Violation History** | Persistent event log with full-frame captures and cropped evidence per violation |

---

## System Architecture

```
+-----------------------------------------------------+
|                    Docker Container                  |
|                                                      |
|  +---------------+        +----------------------+  |
|  |  React + Vite |        |   FastAPI Backend    |  |
|  |  (TypeScript) |<------>|   (Python 3.11)      |  |
|  |               |  REST  |                      |  |
|  |  - Image tab  |  API   |  - /predict          |  |
|  |  - Video tab  |        |  - /api/upload-video |  |
|  |  - History    |        |  - /api/stream/video |  |
|  +---------------+        +----------+-----------+  |
|   Served as static                   |              |
|   files by FastAPI         +---------v----------+   |
|                            |   YOLO Inference   |   |
|                            |   (ONNX Runtime)   |   |
|                            |   + ByteTrack      |   |
|                            +--------------------+   |
+-----------------------------------------------------+
         | Port 7860 (HF Spaces) / 8000 (local)
         v
     Browser / Client
```

**Communication flow:**
1. React sends `multipart/form-data` or JSON to FastAPI endpoints via relative paths (`/predict`, `/api/...`).
2. FastAPI runs ONNX inference and returns JSON detections.
3. For video, FastAPI yields an MJPEG byte stream; React renders it live via an `<img>` tag.
4. Violation alerts are polled every second from `/api/stream/video/alerts` and displayed as clickable crop cards.

---

## Model Optimization

The model was originally trained as a YOLOv8s PyTorch checkpoint (`.pt`). For cloud deployment it was converted to ONNX format:

```bash
# Export script included in the repo
python export_onnx.py --model models/yolov8s_ap.pt --imgsz 640
```

| Metric | PyTorch `.pt` | ONNX Runtime |
|--------|:-------------:|:------------:|
| Runtime dependency | `torch` (~2 GB) | `onnxruntime` (~15 MB) |
| Cold-start time | ~8 s | ~2 s |
| CPU inference / image | ~250 ms | ~90 ms |
| Docker image size | ~5 GB | ~1.8 GB |

> ONNX Runtime removes the PyTorch dependency entirely, making the Docker image significantly leaner — critical for free-tier Hugging Face Spaces with CPU-only inference.

---

## Detection Showcase

Real-world validation results on construction site footage:

| Sample 1 | Sample 2 |
|:---------:|:---------:|
| ![Detection Sample](demo/image_demo_1.jpg) | ![Detection Sample](demo/image_demo_2.jpg) |
| Multi-person helmet detection with confidence scores | No-helmet violation flagged and tracked across frames |

### Video Demo

Real-time ByteTrack tracking demonstration:

[`demo/video_demo.mp4`](demo/video_demo.mp4)

> GitHub and Hugging Face Spaces do not autoplay MP4 files in the README. Click the link above to download or preview. Alternatively, upload any construction site video directly in the [live demo](https://huggingface.co/spaces/letsgobae/safety-helmet-detection).

---

## Project Structure

```
.
├── src/                    # Backend — FastAPI application
│   ├── api/                #   Routes (/predict, /api/*), schemas, app entry
│   ├── core/               #   Predictor (ONNX), ByteTrack streaming, history
│   ├── config/             #   Environment-driven settings & path resolution
│   └── utils/              #   BBox helpers, JPEG encoding, detection utilities
├── frontend/               # React + Vite frontend (TypeScript)
│   └── src/
│       ├── components/     #   ImageDetection, VideoTracking, BBoxCanvas
│       └── services/       #   API base URL — uses window.location.origin
├── models/                 # Model weights (yolov8s_ap.onnx)
├── demo/                   # Real-world validation samples
│   ├── image_demo_1.jpg    #   Multi-person detection sample
│   ├── image_demo_2.jpg    #   Violation detection sample
│   └── video_demo.mp4      #   ByteTrack video tracking demo
├── Dockerfile              # Multi-stage build: Node (React) → Python (FastAPI)
├── docker-compose.yml      # Local development convenience wrapper
├── export_onnx.py          # PyTorch → ONNX conversion script
└── requirements.txt
```

---

## Installation & Running

### Recommended — Docker

The entire stack (backend + frontend) runs as a single container:

```bash
git clone https://huggingface.co/spaces/letsgobae/safety-helmet-detection
cd safety-helmet-detection

docker compose up --build
```

Open `http://localhost:8000` in your browser.

> The Dockerfile uses a multi-stage build: Stage 1 compiles the React app with Node 20, Stage 2 copies the static output into a Python 3.11-slim image alongside FastAPI. The result is a single self-contained image with no dev dependencies.

### Alternative — Dev Servers (hot-reload)

**Terminal 1 — Backend:**

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.api.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env.local` to point the frontend at the local backend:

```env
VITE_API_BASE=http://localhost:8000
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check — reports model load status |
| `POST` | `/predict` | Single-image inference → JSON detections |
| `POST` | `/api/detect/image` | Detect + persist event to history |
| `GET` | `/api/history` | List recent violation events |
| `POST` | `/api/upload-video` | Upload video, returns `video_id` |
| `GET` | `/api/stream/video` | MJPEG stream with ByteTrack overlays (`?video_id=&start_sec=`) |
| `GET` | `/api/stream/video/alerts` | Poll confirmed violation alerts for a video |

---

## Configuration

All runtime behaviour is controlled by environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `models/yolov8s_ap.onnx` | Absolute or relative path to model weights |
| `CONFIDENCE_THRESHOLD` | `0.25` | Minimum detection confidence |
| `PORT` | `7860` | Server port (Hugging Face Spaces requires 7860) |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed origins |

---

## Engineering Notes

- **Singleton model loader** — the ONNX model is loaded once at startup and reused across all requests; no per-request overhead.
- **Same-origin deployment** — on Hugging Face Spaces, React static files are served by FastAPI itself, so all API calls use relative paths with no hardcoded URLs or CORS issues.
- **ByteTrack confirmation window** — violations are only alerted after a rolling 3-of-5 frame window, eliminating single-frame false positives.
- **Runtime data isolation** — detection history and uploaded videos are written to `/app/data` inside the container (gitignored); only the model weights and source code are version-controlled.
