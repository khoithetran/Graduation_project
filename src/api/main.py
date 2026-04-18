"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes.history import router as history_router
from src.api.routes.inference import router as inference_router
from src.api.routes.stream import router as stream_router
from src.api.routes.update import router as update_router
from src.config.logging import setup_logging
from src.config.settings import get_settings
from src.core.predictor import get_predictor

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Resolved path to the compiled React build (populated in Docker; absent locally)
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _cleanup_old_videos(max_age_hours: int = 24) -> None:
    """Delete uploaded video files older than max_age_hours from videos_dir."""
    cutoff = time.time() - max_age_hours * 3600
    cleaned = 0
    for video_file in settings.videos_dir.glob("*"):
        if video_file.is_file() and video_file.stat().st_mtime < cutoff:
            video_file.unlink(missing_ok=True)
            cleaned += 1
    if cleaned:
        logger.info("Startup cleanup: removed %d old video file(s) from videos_dir.", cleaned)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model once on startup and keep the app resilient on failure."""
    _cleanup_old_videos()
    predictor = get_predictor()
    try:
        predictor.load_model()
    except Exception:
        logger.exception("Model preload failed; health endpoint will report model_loaded=false.")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Runtime data (history images, uploaded videos) ───────────────────────────
app.mount("/static", StaticFiles(directory=settings.data_dir), name="static")

# ── API routers (must be registered before the SPA catch-all) ────────────────
app.include_router(inference_router)
app.include_router(history_router)
app.include_router(stream_router)
app.include_router(update_router)

# ── React SPA — only mounted when the compiled build exists ──────────────────
if _FRONTEND_DIST.exists():
    # Serve JS/CSS/image assets produced by Vite
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> HTMLResponse:
        """Return index.html for every path that is not matched by an API route."""
        return HTMLResponse((_FRONTEND_DIST / "index.html").read_text(encoding="utf-8"))
else:
    logger.info("Frontend dist not found at %s — serving API only.", _FRONTEND_DIST)
