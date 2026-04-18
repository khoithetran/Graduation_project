# Refactoring Plan: Safety Helmet Detection — Production-Ready Architecture

## Overarching Goal

Migrate the graduation project from a monolithic script-based repository (`backend/server.py` + ad-hoc frontend) into a scalable, modular, production-ready application following the spec in `agents.md`. The final deliverable is a containerised FastAPI backend + React frontend that can be deployed with a single `docker compose up`.

---

## Phase 1 — Backend Refactoring (src/)

### Core Infrastructure
- [x] Create new directory hierarchy: `src/api/`, `src/core/`, `src/config/`, `src/utils/`
- [x] `src/config/settings.py` — Centralised, environment-driven config (model path, confidence, CORS, FPS, etc.)
- [x] `src/config/logging.py` — Structured logging setup; no bare `print()` calls

### Core Inference Engine
- [x] `src/core/predictor.py` — Singleton `Predictor` class with:
  - [x] Automatic CUDA / CPU device selection
  - [x] `.pt` and `.onnx` format support
  - [x] `load_model()` called once at startup via FastAPI lifespan

### Domain Logic
- [x] `src/core/history.py` — Persist detection events (global frame + crop images, JSONL log)
- [x] `src/core/tracker.py` — Multi-frame object tracking for video streams
- [x] `src/core/streaming.py` — MJPEG / SSE frame-streaming logic with sliding-window event detection
- [x] `src/core/update_pool.py` — Accumulate reviewed images for future model fine-tuning

### Utilities
- [x] `src/utils/image.py` — Decode image bytes, PIL ↔ NumPy conversion
- [x] `src/utils/detection.py` — Event classification helper (`VI_PHAM` / `NGHI_NGO`)

### FastAPI Application
- [x] `src/api/main.py` — FastAPI app with lifespan, CORS middleware, static-file mount, all routers included
- [x] `src/api/schemas.py` — Pydantic request/response models (`HealthResponse`, `PredictResponse`, `DetectImageResponse`, etc.)
- [x] `src/api/routes/inference.py` — `GET /health`, `GET /api/health`, `POST /predict`, `POST /api/detect-image`
- [x] `src/api/routes/history.py` — `GET /api/history`, `DELETE /api/history`
- [x] `src/api/routes/stream.py` — `POST /api/stream/start`, streaming video endpoint
- [x] `src/api/routes/update.py` — `POST /api/update/review`, model update endpoints

### Legacy Backend Cleanup
- [x] `backend/server.py` — Replaced with a thin compatibility shim that imports and runs `src.api.main:app` via uvicorn (28 lines, down from ~1 900)
- [x] `backend/Yolov8m_3class.pt` — Removed from `backend/`; weight files now live in `models/`
- [x] `backend/yolov8s_ap.pt` — Removed from `backend/`; weight files now live in `models/`

---

## Phase 2 — Frontend Refactoring (frontend/)

- [x] `frontend/src/App.tsx` — Simplified two-tab shell (`image` | `video`) with history polling
- [x] `frontend/src/components/ImageDetection.tsx` — Self-contained image upload + bbox display component
- [x] `frontend/src/components/VideoTracking.tsx` — Video upload + MJPEG stream component
- [x] `frontend/src/components/BBoxCanvas.tsx` — Canvas overlay renderer for bounding boxes
- [x] `frontend/src/components/HistorySidebar.tsx` — Scrollable event history panel
- [x] `frontend/src/content/app-text.vi.json` — Vietnamese i18n string table (no hardcoded UI text)
- [x] `frontend/src/services/api.ts` — Centralised `API_BASE` constant
- [x] Remove old tab-based components: `DetectionTab.tsx`, `HistoryTab.tsx`, `UpdateTab.tsx`, `MainLayout.tsx`
- [x] Remove old hooks/store: `useViolationTracker.ts`, `appStore.ts`, `types.ts`

---

## Phase 3 — Project Hygiene

- [x] `.gitignore` — Excludes `__pycache__`, `.venv`, `.env`, `*.pt`, `*.onnx`, `*.engine`, large data files
- [x] `requirements.txt` — Pinned production dependencies (FastAPI, uvicorn, ultralytics, opencv-headless, Pillow, numpy, python-multipart)
- [x] `data/` directory scaffold — `history/`, `temp_videos/`, `update_pool/`, `videos/` (auto-created by settings on startup)
- [x] `models/` directory — Holds weight files locally; excluded from git via `.gitignore`

---

## Phase 4 — Deployment (Containerisation)

- [x] `deployment/Dockerfile` — Multi-stage Python 3.11 slim image; installs system libs (`libgl1`, `libglib2.0`), copies `src/`, `data/`, `models/`; exposes port 8000
- [x] `deployment/docker-compose.yml` — Single-service compose with `MODEL_PATH` and `CONFIDENCE_THRESHOLD` env overrides, volume mounts for `data/` and `models/`

### Remaining Deployment Tasks
- [ ] Add a `models/.gitkeep` placeholder so the `models/` directory is tracked in git (weight files remain gitignored)
- [ ] Verify `docker compose build` completes without errors
- [ ] Verify `docker compose up` starts the API and `/health` returns `{"status":"ok","model_loaded":true,...}`
- [ ] Confirm frontend `npm run dev` can reach the backend at `http://localhost:8000`

---

## Phase 5 — Git Staging & Commit

- [ ] Stage all new `src/` files (routes, core, utils, config)
- [ ] Stage all new frontend component files
- [ ] Stage `requirements.txt`, `.gitignore`, `deployment/`, `data/`, `models/.gitkeep`
- [ ] Stage deletions: old `backend/` model files, old frontend tabs/hooks/store
- [ ] Stage modified files: `backend/server.py` (shim), `frontend/src/App.tsx`, `frontend/src/index.css`, etc.
- [ ] Commit with message: `refactor: migrate to modular FastAPI + React architecture`

---

## Phase 6 — Các tính năng đã triển khai nhưng chưa có trong kế hoạch

> Phần này ghi nhận các tính năng thực tế đã được xây dựng vượt ra ngoài phạm vi ban đầu, phát sinh trong quá trình phát triển sau phases 1–4.

### Backend — Endpoints bổ sung

- [x] `GET /api/stream/video/alerts` — Trả về danh sách `VIDEO_ALERTS` tích lũy trong bộ nhớ cho một `video_id`; được frontend poll mỗi 1 giây
- [x] `GET /api/video/file/{video_id}` — Phục vụ file video gốc đã upload để trình duyệt có thể seek; validate `video_id` bằng regex `[0-9a-f]{32}` chống glob injection
- [x] `POST /api/live/start` + `GET /api/live/stream` — Đăng ký URL live camera và stream MJPEG; lưu trong dict `LIVE_STREAMS`
- [x] `POST /api/detect_video` — Phân tích video offline (không stream), trả về `VideoDetectResponse` với số lượng sự kiện và danh sách `HistoryEvent`
- [x] `GET /api/history/latest` — Trả về sự kiện history gần nhất, hỗ trợ filter `source` và `types`
- [x] `GET /api/history/{event_id}` — Trả về một sự kiện history theo ID
- [x] `GET /api/update/candidates`, `GET /api/update/auto-label/{event_id}`, `POST /api/update/mark`, `POST /api/update/start`, `GET /api/update/status` — 5 update endpoints (PLAN.md chỉ ghi 1 endpoint `POST /api/update/review`)

### Backend — Logic xử lý bổ sung

- [x] `_ViolationTracker` (trong `streaming.py`) — Xác nhận vi phạm qua rolling-window N-of-M (`_WINDOW_SIZE=5`, `_MIN_HITS=3`), grace period (`_TRACK_PATIENCE=3`), và IoU spatial fallback khi ByteTrack không gán được ID
- [x] `VIDEO_ALERTS` dict trong bộ nhớ — Tích lũy alert có trường `id`, `timestamp_sec`, `class_name`, `confidence`, `crop` (base64), `x1/y1/x2/y2`; reset khi video được stream lại
- [x] `INFERENCE_FRAME_INTERVAL = 30` — Chỉ chạy inference trên 1/30 frame thô để giảm tải CPU/GPU
- [x] `src/core/bytetrack_video.yaml` — Config ByteTrack tùy chỉnh cho sparse video inference

### Frontend — Components bổ sung

- [x] `frontend/src/components/AlertDetailModal.tsx` — Modal video player với: seek đến timestamp của alert, canvas bbox overlay (HiDPI-aware, glow + label), progress bar tùy chỉnh, đóng bằng Escape hoặc click backdrop
- [x] `frontend/src/types.ts` — Type `VideoAlert` mới (thay thế file `types.ts` cũ đã xoá; không nên nhầm với file cũ)
- [x] Video pause/freeze-frame trong `VideoTracking.tsx` — Click vào stream MJPEG để pause; chụp canvas snapshot từ `<img>` tag để hiển thị khi paused
- [x] `HistorySidebar.tsx` — Đã xoá; thiết kế cũ dùng polling liên tục, thay bằng inline alerts section trong `VideoTracking` (chỉ hiển thị khi phát hiện vi phạm)

### Frontend — Tính năng bổ sung trong components hiện có

- [x] `VideoTracking.tsx` — Violation alerts section (grid 2 cột) hiển thị alert từ polling; click card mở `AlertDetailModal`
- [x] `ImageDetection.tsx` — Bbox opacity slider (0–100%); click detection card → scroll đến ảnh + highlight bbox 2.5s
- [x] `services/api.ts` — Hàm `toApiAssetUrl()` để resolve URL asset tương đối/tuyệt đối ngoài `API_BASE`

---

## Nợ kỹ thuật (Tech Debt) — Đã xử lý

| Vấn đề | Giải pháp | Mức độ |
|---|---|---|
| ~~`print()` debug còn trong production code~~ | Thay bằng `logger.debug/info` trong `streaming.py` | Cao ✅ |
| ~~`VIDEO_ALERTS` dict không giới hạn kích thước~~ | `OrderedDict` + `_MAX_VIDEO_IDS=50` + `_MAX_ALERTS_PER_VIDEO=200` | Trung bình ✅ |
| ~~Files video trong `videos_dir` không bao giờ bị xoá~~ | Cleanup startup trong `lifespan` — xoá files cũ hơn 24h | Trung bình ✅ |
| ~~`formatTime()` bị trùng lặp~~ | Extracted ra `frontend/src/utils/format.ts` | Thấp ✅ |
| ~~`DELETE /api/history` chưa implement~~ | Thêm `delete_all_history()` vào core + `DELETE /api/history` route | Thấp ✅ |
| ~~`HistorySidebar` dead code~~ | Xoá hoàn toàn — thiết kế cũ, đã thay bằng inline alerts trong `VideoTracking` | Thấp ✅ |
| ~~`ImageDetection` gọi `/predict` thay vì `/api/detect/image`~~ | Đổi sang `/api/detect/image` + thêm `source` field | Thấp ✅ |

---

## Summary of Current State

| Area | Status |
|---|---|
| Backend infrastructure (`src/`) | Complete — all modules written |
| FastAPI routes (4 routers + extras) | Complete |
| Frontend components | Complete |
| Deployment files | Complete |
| Integration testing | Pending |
| Git commit | Pending (awaiting approval) |
| Tech debt cleanup | Complete ✅ |
