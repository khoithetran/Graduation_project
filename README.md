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

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Hugging%20Face%20Spaces-FFD21E?style=for-the-badge)](https://huggingface.co/spaces/tr-th-khoi/safety-helmet-detection)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-ONNX-purple?style=for-the-badge)](https://docs.ultralytics.com)

</div>

---

## Live Demo

> Try it now — no setup required.

**[tr-th-khoi/safety-helmet-detection on Hugging Face Spaces](https://huggingface.co/spaces/tr-th-khoi/safety-helmet-detection)**

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Real-time Image Detection** | Upload any image and get bounding-box results with class labels and confidence scores in under a second |
| **Video Violation Tracking** | Upload a video and watch ByteTrack follow every person across frames with live MJPEG streaming |
| **Live Stream Monitoring** | Connect a webcam or IP camera for continuous real-time detection with bbox overlays |
| **Timestamp-Synchronized Alerts** | Click any violation crop to instantly seek the video to that exact moment and pause for inspection |
| **AI Violation Reports** | Gemini 2.0 Flash generates Vietnamese-language reports per alert — risk level, description, recommendations |
| **Instant PDF Export** | Download a violation report PDF from the current session at any time, no history or LLM required |
| **ONNX-Optimized Inference** | Model exported from `.pt` to `.onnx` for significantly lower latency and memory footprint on CPU-only cloud environments |
| **Modern React UI** | Responsive TypeScript + Vite frontend served from the same Docker image — zero CORS friction |
| **Violation History** | Persistent event log with full-frame captures and cropped evidence per violation |

---

## System Architecture

```
+------------------------------------------------------------------+
|                        Docker Container                           |
|                                                                   |
|  +------------------+        +------------------------------+    |
|  |  React + Vite    |        |      FastAPI Backend          |    |
|  |  (TypeScript)    |<------>|      (Python 3.11)            |    |
|  |                  |  REST  |                               |    |
|  |  - Image tab     |  API   |  - /predict                   |    |
|  |  - Video tab     |        |  - /api/upload-video          |    |
|  |  - LiveStream tab|        |  - /api/stream/video          |    |
|  |  - ReportModal   |        |  - /api/live/webcam/frame     |    |
|  +------------------+        |  - /api/report/simple-pdf     |    |
|   Served as static           +----------+--------------------+    |
|   files by FastAPI                      |                         |
|                              +----------v-----------+             |
|                              |    YOLO Inference    |             |
|                              |    (ONNX Runtime)    |             |
|                              |    + ByteTrack       |             |
|                              +----------+-----------+             |
|                                         |                         |
|                              +----------v-----------+             |
|                              |  Gemini 2.0 Flash    |             |
|                              |  (AI Report Engine)  |             |
|                              +----------------------+             |
+------------------------------------------------------------------+
         | Port 7860 (HF Spaces) / 8000 (local)
         v
     Browser / Client
```

**Communication flow:**
1. React sends `multipart/form-data` or JSON to FastAPI endpoints via relative paths.
2. FastAPI runs ONNX inference and returns JSON detections.
3. For video/live, FastAPI yields an MJPEG byte stream; React renders it live via `<img>` or `<video>` tags.
4. Violation alerts are polled every second and displayed as clickable crop cards.
5. On demand, Gemini 2.0 Flash generates a Vietnamese report per alert (rate-limited to 12 req/min).
6. "Tải PDF" sends current session alerts to `/api/report/simple-pdf` and downloads instantly.

---

## Model Optimization

The model was originally trained as a YOLOv8s PyTorch checkpoint (`.pt`). For cloud deployment it was converted to ONNX format:

```bash
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

> GitHub and Hugging Face Spaces do not autoplay MP4 files in the README. Click the link above to download or preview. Alternatively, upload any construction site video directly in the [live demo](https://huggingface.co/spaces/tr-th-khoi/safety-helmet-detection).

---

## Project Structure

```
.
├── src/                    # Backend — FastAPI application
│   ├── api/
│   │   ├── routes/         #   inference, history, stream, update, report
│   │   ├── schemas.py      #   Pydantic models (all request/response types)
│   │   └── main.py         #   App factory, lifespan, CORS, routers
│   ├── core/
│   │   ├── predictor.py    #   ONNX singleton loader
│   │   ├── streaming.py    #   MJPEG streaming, ByteTrack, ViolationTracker
│   │   ├── history.py      #   JSONL event log + image persistence
│   │   ├── llm_reporter.py #   Gemini 2.0 Flash report generator (rate-limited)
│   │   ├── pdf_builder.py  #   reportlab PDF builder (instant + scheduled)
│   │   └── scheduler.py    #   APScheduler auto-report every 4h
│   ├── config/             #   Environment-driven settings, dotenv loader
│   └── utils/              #   Image decode, detection helpers
├── frontend/               # React + Vite frontend (TypeScript)
│   └── src/
│       ├── components/
│       │   ├── ImageDetection.tsx
│       │   ├── VideoTracking.tsx   # + "Xem báo cáo" + "Tải PDF" buttons
│       │   ├── LiveStream.tsx      # + "Xem báo cáo" + "Tải PDF" buttons
│       │   ├── AlertDetailModal.tsx
│       │   └── ReportModal.tsx     # AI report display (risk badge + recommendations)
│       ├── content/
│       │   └── app-text.vi.json   # Vietnamese i18n strings
│       └── services/api.ts
├── models/                 # Model weights (yolov8s_ap.onnx) — gitignored
├── demo/                   # Real-world validation samples
├── Dockerfile              # Multi-stage build: Node (React) → Python (FastAPI)
├── docker-compose.yml
├── export_onnx.py
└── requirements.txt
```

---

## Installation & Running

### Recommended — Docker

```bash
git clone https://huggingface.co/spaces/tr-th-khoi/safety-helmet-detection
cd safety-helmet-detection
cp .env.example .env   # add GEMINI_API_KEY for AI reports (optional)
docker compose up --build
```

Open `http://localhost:8000` in your browser.

### Alternative — Dev Servers (hot-reload)

**Terminal 1 — Backend:**

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit MODEL_PATH, GEMINI_API_KEY, etc.
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

Rate limits are enforced per IP address (no API key required):

| Endpoint | Limit |
|----------|-------|
| `POST /predict` | 30 req/min |
| `POST /api/detect_video` | 5 req/min |
| `POST /api/live/webcam/frame` | 600 req/min |

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check — reports model load status |
| `POST` | `/predict` | Single-image inference → JSON detections |
| `POST` | `/api/detect/image` | Detect + persist event to history |
| `GET` | `/api/history` | List recent violation events |
| `POST` | `/api/upload-video` | Upload video, returns `video_id` |
| `GET` | `/api/stream/video` | MJPEG stream with ByteTrack overlays |
| `GET` | `/api/stream/video/alerts` | Poll confirmed violation alerts for a video |
| `POST` | `/api/live/webcam/frame` | Process single webcam frame → detections + alerts |
| `GET` | `/api/live/alerts/{live_id}` | Poll alerts for an IP camera stream |
| `POST` | `/api/report/from-alert` | Generate AI report for a live/video alert (cached) |
| `GET` | `/api/report/event/{event_id}` | Generate AI report for a history event |
| `POST` | `/api/report/simple-pdf` | **Instant PDF** from current session alerts (no LLM) |
| `GET` | `/api/report/download` | Full PDF report from history (last N hours) |

---

## Configuration

All runtime behaviour is controlled by environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PATH` | `models/yolov8s_ap.onnx` | Path to model weights |
| `CONFIDENCE_THRESHOLD` | `0.25` | Minimum detection confidence |
| `PORT` | `7860` | Server port (Hugging Face Spaces requires 7860) |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed origins |
| `GEMINI_API_KEY` | _(empty)_ | Google Gemini API key for AI reports — free at [aistudio.google.com](https://aistudio.google.com/apikey) |
| `REPORT_INTERVAL_HOURS` | `4` | Auto PDF generation interval (hours) |

> If `GEMINI_API_KEY` is not set, the system still works — "Xem báo cáo" returns a pre-built fallback report instead of calling Gemini.

---

## Engineering Notes

- **Singleton model loader** — the ONNX model is loaded once at startup and reused across all requests; no per-request overhead.
- **Same-origin deployment** — on Hugging Face Spaces, React static files are served by FastAPI itself, so all API calls use relative paths with no hardcoded URLs or CORS issues.
- **ByteTrack confirmation window** — violations are only alerted after a rolling 3-of-5 frame window, eliminating single-frame false positives.
- **Gemini rate limiter** — a global threading lock enforces ≤12 calls/minute (safely under the free-tier 15 RPM limit); in-flight deduplication prevents redundant calls for the same alert.
- **Instant PDF** — `POST /api/report/simple-pdf` accepts raw alert data from the frontend and builds a PDF immediately without history lookup or LLM calls; image aspect ratios are preserved.
- **Runtime data isolation** — detection history and uploaded videos are written to `/app/data` inside the container (gitignored); only the model weights and source code are version-controlled.
