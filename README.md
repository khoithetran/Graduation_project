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
| **ONNX-Optimized Inference** | Model exported from `.pt` to `.onnx` for significantly lower latency and memory footprint on CPU-only cloud environments; auto-selects CUDA provider when `onnxruntime-gpu` is available |
| **Visual Loading Feedback** | Indeterminate amber progress bar overlays the image/video preview during inference — no layout jump, no spinner |
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

## Person-First Detection Pipeline

> Available since this commit — off by default, no existing behaviour changes.

### Motivation

The baseline single-stage model (YOLOv8s) runs on the **full frame** and can
miss people in difficult poses (seated, crouched, partially occluded).  Because
the PPE conclusion is drawn from the model output alone, missed people produce
false "all helmets OK" frames.

### How It Works

```
Full frame
   │
   ▼
[Person detector – YOLOv8n]
   │  (x1,y1,x2,y2, track_id)  per person
   ▼
Upper-body crop  ──► [Helmet model – YOLOv8s ONNX]
   │                        │
   │                  (helmet / head / non-helmet)
   │                  mapped back to frame coords
   ▼
Same ViolationTracker  →  same alert / history logic
```

1. **Person detection** — YOLOv8n detects every `person` in the frame.
   It is ~5× smaller than YOLOv8s and better at detecting people at unusual
   poses because COCO training data covers diverse human poses.

2. **ByteTrack person tracking** — stable person IDs are maintained across
   frames (video/live modes) so the helmet status cache is keyed by person.

3. **Upper-body crop** — the top `UPPER_BODY_CROP_RATIO` (default 60 %) of
   each person bbox is cropped with a small margin and fed to the helmet model.
   The helmet now occupies a larger fraction of the model's input → better
   recall for small/distant people.

4. **Helmet status cache** — the helmet model only reruns every
   `HELMET_RECHECK_INTERVAL` frames per person (default: every 5 processed
   frames).  Between checks the last known status is reused.  This keeps the
   total compute roughly constant compared with the standard pipeline.

5. **Same outputs** — violation class names, confidence values, and frame
   coordinates flow into the exact same `_ViolationTracker` / alert /
   history / PDF / report logic.  No frontend changes required.

### Enabling Person-First Mode

Set in `.env` (or as an environment variable):

```env
PERSON_FIRST_ENABLED=true
```

The first request will auto-download `yolov8n.pt` (~6 MB) from Ultralytics
into `~/.ultralytics/`.  To pin a local copy:

```env
PERSON_MODEL_PATH=models/yolov8n.pt
```

Or export to ONNX for faster CPU inference:

```bash
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx', imgsz=640)"
mv yolov8n.onnx models/
```

```env
PERSON_MODEL_PATH=models/yolov8n.onnx
```

### Tuning Parameters

| Variable | Default | Effect |
|----------|---------|--------|
| `PERSON_CONFIDENCE_THRESHOLD` | `0.40` | Min confidence to accept a person detection |
| `UPPER_BODY_CROP_RATIO` | `0.60` | Top fraction of person bbox used as helmet crop |
| `PERSON_CROP_MARGIN` | `0.05` | Fractional padding added around the crop |
| `HELMET_RECHECK_INTERVAL` | `5` | Re-run helmet model every N processed frames per track |
| `PERSON_DETECTION_INTERVAL` | `1` | Run person detector every N processed frames — default=1 (every frame, full accuracy); set to 2–4 on weak CPU to halve person-model calls at the cost of brief lag when a new person enters |

### Visual Differences

When person-first is active:

**Video / IP Camera modes** (MJPEG overlay drawn server-side):
- **Thin blue bounding box + P{id} label** around each tracked person.
- **Standard coloured box** for the helmet/head/non-helmet detection inside the person.

**Webcam mode** (bboxes drawn client-side by the browser):
- Toggle the **Person-First** switch in the UI — the frontend sends `person_first=true` with every frame.
- Backend creates a per-session `PersonFirstPipeline` and returns `person_boxes` alongside normal detections.
- Selecting the **Person** filter chip shows the thin orange person bounding boxes on the canvas overlay.

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
│   │   ├── predictor.py    #   ONNX singleton loader (helmet model)
│   │   ├── person_detector.py  #   Singleton YOLOv8n person detector + ByteTrack
│   │   ├── person_first.py     #   Two-stage pipeline: person → helmet crop
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
| `MODEL_PATH` | `models/yolov8s_ap.onnx` | Path to helmet model weights |
| `CONFIDENCE_THRESHOLD` | `0.25` | Minimum detection confidence |
| `PORT` | `7860` | Server port (Hugging Face Spaces requires 7860) |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed origins |
| `ONNX_EXECUTION_PROVIDER` | _(auto)_ | ONNX Runtime provider: empty = auto-detect; set to `CPUExecutionProvider` to force CPU or `CUDAExecutionProvider` to force GPU (requires `onnxruntime-gpu`) |
| `GEMINI_API_KEY` | _(empty)_ | Google Gemini API key for AI reports — free at [aistudio.google.com](https://aistudio.google.com/apikey) |
| `REPORT_INTERVAL_HOURS` | `4` | Auto PDF generation interval (hours) |

> If `GEMINI_API_KEY` is not set, the system still works — "Xem báo cáo" returns a pre-built fallback report instead of calling Gemini.

### Person-First Pipeline Variables

Only relevant when `PERSON_FIRST_ENABLED=true`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PERSON_FIRST_ENABLED` | `false` | Enable two-stage person → helmet pipeline |
| `PERSON_MODEL_PATH` | _(auto)_ | Path to person detector weights; supports `.pt` and `.onnx`; omit to auto-download `yolov8n.pt` |
| `PERSON_CONFIDENCE_THRESHOLD` | `0.40` | Minimum confidence to accept a person detection |
| `PERSON_DETECTION_INTERVAL` | `1` | Run person detector every N processed frames (default=1, full accuracy; increase to 2–4 on weak CPU to reduce load with minor temporal lag) |
| `HELMET_RECHECK_INTERVAL` | `5` | Re-run helmet model every N frames per tracked person |
| `PERSON_CROP_MARGIN` | `0.05` | Fractional padding added around each person crop |
| `UPPER_BODY_CROP_RATIO` | `0.60` | Top fraction of person bbox used as helmet crop |

**Using an ONNX person model** (faster CPU inference):
```bash
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx', imgsz=640)"
mv yolov8n.onnx models/
```
Then set `PERSON_MODEL_PATH=models/yolov8n.onnx`. The backend auto-detects the format and selects the appropriate device.

---

## Engineering Notes
- **Frontend demo refresh (2025-04)** — UI shifted to a light `#9fe7f5`-led visual system with DM Sans throughout. Hero shows a single-line title + 4 stat cards; a 5-step pipeline diagram accurately describes the default single-stage flow with a note that ByteTrack/rolling-window (step 4) is Video/Live only; a dedicated callout card inside the pipeline section explains the person-first 2-stage variant (YOLOv8n → crop → YOLOv8s) and clarifies it is opt-in via `PERSON_FIRST_ENABLED=true` and applies to Video, Live Stream, and Webcam — not image-only requests; real demo images are embedded as a showcase section; three mode-selector cards explain each detection mode. Existing component functionality unchanged.
- **Singleton model loader** — the ONNX model is loaded once at startup and reused across all requests; no per-request overhead.
- **Same-origin deployment** — on Hugging Face Spaces, React static files are served by FastAPI itself, so all API calls use relative paths with no hardcoded URLs or CORS issues.
- **ByteTrack confirmation window** — violations are only alerted after a rolling 3-of-5 frame window, eliminating single-frame false positives.
- **Deferred PIL conversion** — `cv2.cvtColor + Image.fromarray` in the streaming loop runs only when a threshold crossing actually triggers `persist_window_event`, not on every processed frame.
- **ONNX provider auto-detection** — both the helmet predictor and the person detector check `onnxruntime.get_available_providers()` at model load and select CUDAExecutionProvider automatically if available; no manual config required for GPU machines.
- **Gemini rate limiter** — a global threading lock enforces ≤12 calls/minute (safely under the free-tier 15 RPM limit); in-flight deduplication prevents redundant calls for the same alert.
- **Instant PDF** — `POST /api/report/simple-pdf` accepts raw alert data from the frontend and builds a PDF immediately without history lookup or LLM calls; image aspect ratios are preserved.
- **Runtime data isolation** — detection history and uploaded videos are written to `/app/data` inside the container (gitignored); only the model weights and source code are version-controlled.
- **Filter-aware violation alerts** — the `classes` URL parameter passed at stream start is applied to both the visual overlay and the alert store; only classes matching the user's filter selection are saved in `VIDEO_ALERTS` / `LIVE_ALERTS`, so polled alerts are already pre-filtered. For webcam, the frontend filters `data.alerts` client-side using the active class set before adding to state.
- **Per-session person-first (webcam)** — `person_first` is sent as a form field with every webcam frame POST. A new session initialises a `PersonFirstPipeline` when `person_first=true` regardless of the global `PERSON_FIRST_ENABLED` env var, so the UI toggle works independently of server configuration.
- **Active filter indicator** — after clicking "Bắt đầu nhận dạng" on Video or Webcam, a badge strip appears beneath the stream header listing every class currently being filtered, so the active filter is always visible during inference.
