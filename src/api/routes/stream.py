"""Video and live stream endpoints."""

from __future__ import annotations

import logging
import re
from pathlib import Path
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from src.api.schemas import (
    LiveAlertOut,
    LiveStartResponse,
    UploadVideoResponse,
    VideoDetectResponse,
    WebcamFrameResponse,
)
from src.config.settings import get_settings
from src.core.predictor import get_predictor
from src.core.streaming import (
    LIVE_ALERTS,
    LIVE_STREAMS,
    VIDEO_ALERTS,
    WEBCAM_SESSIONS,
    analyze_uploaded_video,
    generate_live_stream,
    generate_processed_video_stream,
    process_webcam_frame,
    register_live_stream,
    register_uploaded_video,
)

router = APIRouter(tags=["stream"])
logger = logging.getLogger(__name__)
settings = get_settings()


@router.post("/api/detect_video", response_model=VideoDetectResponse)
async def detect_video(
    file: UploadFile = File(...),
    source: str | None = Form(None),
) -> VideoDetectResponse:
    """Analyze a full uploaded video offline."""
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a video.")

    raw_bytes = await file.read()
    temp_path = settings.temp_videos_dir / f"{uuid.uuid4().hex}__{Path(file.filename or 'uploaded_video.mp4').name}"
    temp_path.write_bytes(raw_bytes)

    predictor = get_predictor()
    try:
        return analyze_uploaded_video(
            temp_path=temp_path,
            predictor=predictor,
            source=source or file.filename or "Uploaded video",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Offline video analysis failed.")
        raise HTTPException(status_code=500, detail="Offline video analysis failed.") from exc
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/api/upload-video", response_model=UploadVideoResponse)
async def upload_video(file: UploadFile = File(...)) -> UploadVideoResponse:
    """Store a video that will later be processed as an MJPEG stream."""
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a video.")

    raw_bytes = await file.read()
    return register_uploaded_video(filename=file.filename or "uploaded_video.mp4", raw_bytes=raw_bytes)


@router.get("/api/stream/video/alerts")
def stream_video_alerts(video_id: str = Query(...)) -> list[dict]:
    """Return accumulated violation alerts for a streaming video."""
    return VIDEO_ALERTS.get(video_id, [])


@router.get("/api/video/file/{video_id}")
def get_video_file(video_id: str) -> FileResponse:
    """Serve the raw uploaded video with Range header support for browser seeking."""
    if not re.fullmatch(r"[0-9a-f]{32}", video_id):
        raise HTTPException(status_code=400, detail="Invalid video_id format.")
    matches = list(settings.videos_dir.glob(f"{video_id}__*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Video file not found.")
    video_path = matches[0]
    suffix = video_path.suffix.lower()
    media_types = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}
    media_type = media_types.get(suffix, "video/mp4")
    return FileResponse(video_path, media_type=media_type)


@router.get("/api/stream/video")
def stream_video(
    video_id: str = Query(...),
    file_name: str = Query(...),
    source: str | None = Query(None),
    start_sec: float = Query(0.0),
) -> StreamingResponse:
    """Stream a processed uploaded video as MJPEG."""
    video_path = settings.videos_dir / f"{video_id}__{Path(file_name).name}"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Uploaded video was not found.")

    predictor = get_predictor()
    stream = generate_processed_video_stream(
        video_path=video_path,
        predictor=predictor,
        source=source or file_name,
        video_id=video_id,
        start_sec=start_sec,
    )
    return StreamingResponse(stream, media_type="multipart/x-mixed-replace; boundary=frame")


@router.post("/api/live/start", response_model=LiveStartResponse)
async def live_start(
    stream_url: str = Form(...),
    source: str | None = Form(None),
) -> LiveStartResponse:
    """Register a live stream URL used by the frontend."""
    try:
        return register_live_stream(stream_url=stream_url, source=source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/live/stream")
def live_stream(live_id: str = Query(...)) -> StreamingResponse:
    """Stream a registered live source as MJPEG."""
    if live_id not in LIVE_STREAMS:
        raise HTTPException(status_code=404, detail="Live stream was not found.")

    predictor = get_predictor()
    try:
        stream = generate_live_stream(live_id=live_id, predictor=predictor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamingResponse(stream, media_type="multipart/x-mixed-replace; boundary=frame")


@router.post("/api/live/webcam/frame", response_model=WebcamFrameResponse)
async def live_webcam_frame(
    file: UploadFile = File(...),
    session_id: str = Form(...),
) -> WebcamFrameResponse:
    """Process a single webcam frame and return detections + any new violation alerts."""
    predictor = get_predictor()
    raw_bytes = await file.read()
    result = process_webcam_frame(
        frame_bytes=raw_bytes,
        session_id=session_id,
        predictor=predictor,
    )
    return WebcamFrameResponse(
        detections=result["detections"],
        alerts=result["alerts"],
    )


@router.get("/api/live/webcam/alerts")
def live_webcam_alerts(session_id: str = Query(...)) -> list[dict]:
    """Return all accumulated violation alerts for a webcam session."""
    session = WEBCAM_SESSIONS.get(session_id)
    if session is None:
        return []
    return session.alerts


@router.get("/api/live/alerts/{live_id}")
def live_stream_alerts(live_id: str) -> list[dict]:
    """Return accumulated violation alerts for an IP camera live stream."""
    return LIVE_ALERTS.get(live_id, [])
