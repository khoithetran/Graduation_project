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

## Summary of Current State

| Area | Status |
|---|---|
| Backend infrastructure (`src/`) | Complete — all modules written |
| FastAPI routes (4 routers) | Complete |
| Frontend components | Complete |
| Deployment files | Complete |
| Integration testing | Pending |
| Git commit | Pending (awaiting approval) |
