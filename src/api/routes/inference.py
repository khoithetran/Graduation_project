"""Inference and health endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.api.schemas import DetectImageResponse, HealthResponse, PredictResponse
from src.config.settings import get_settings
from src.core.history import persist_image_event
from src.core.predictor import get_predictor
from src.utils.detection import classify_event
from src.utils.image import decode_image_bytes, pil_to_numpy

router = APIRouter(tags=["inference"])
logger = logging.getLogger(__name__)
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
@router.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return service health and model-load information."""
    predictor = get_predictor()
    return HealthResponse(
        status="ok",
        model_loaded=predictor.is_loaded,
        model_path=predictor.model_path,
        device=predictor.device,
        model_format=predictor.model_format,
    )


@router.post("/predict", response_model=PredictResponse)
async def predict(file: UploadFile = File(...)) -> PredictResponse:
    """Run the production-ready predict endpoint required by the refactor."""
    predictor = get_predictor()
    if not predictor.is_loaded:
        try:
            predictor.load_model()
        except Exception as exc:
            logger.exception("Predictor could not be loaded for /predict.")
            raise HTTPException(status_code=503, detail="Model is unavailable.") from exc

    if file.content_type not in settings.allowed_image_content_types:
        raise HTTPException(status_code=415, detail="Only JPEG and PNG images are supported.")

    raw_bytes = await file.read()
    try:
        image = decode_image_bytes(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        detections = predictor.detect_image(pil_to_numpy(image))
    except Exception as exc:
        logger.exception("Inference failed for /predict.")
        raise HTTPException(status_code=500, detail="Inference failed.") from exc

    return PredictResponse(detections=detections)


@router.post("/api/detect/image", response_model=DetectImageResponse)
async def detect_image(
    file: UploadFile = File(...),
    source: str | None = Form(None),
) -> DetectImageResponse:
    """Run legacy image detection used by the frontend dashboard."""
    predictor = get_predictor()
    if not predictor.is_loaded:
        try:
            predictor.load_model()
        except Exception as exc:
            logger.exception("Predictor could not be loaded for /api/detect/image.")
            raise HTTPException(status_code=503, detail="Model is unavailable.") from exc

    if file.content_type not in settings.allowed_image_content_types:
        raise HTTPException(status_code=415, detail="Only JPEG and PNG images are supported.")

    raw_bytes = await file.read()
    try:
        image = decode_image_bytes(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        boxes = predictor.detect_image(pil_to_numpy(image))
    except Exception as exc:
        logger.exception("Inference failed for /api/detect/image.")
        raise HTTPException(status_code=500, detail="Inference failed.") from exc

    event_type = classify_event(boxes)
    is_video_frame = bool(file.filename and file.filename.startswith("frame"))
    if is_video_frame or event_type == "NONE":
        return DetectImageResponse(boxes=boxes, event_type=event_type)

    history_event = persist_image_event(
        image=image,
        boxes=boxes,
        source=source or file.filename or "Uploaded image",
        event_type=event_type,
    )

    return DetectImageResponse(
        boxes=boxes,
        global_image_url=history_event.global_image_url if history_event else None,
        crop_image_urls=history_event.crop_image_urls if history_event else [],
        event_type=event_type,
        history_event_id=history_event.id if history_event else None,
    )
