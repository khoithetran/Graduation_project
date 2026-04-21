"""Inference and health endpoints."""

import logging

import cv2
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from src.api.rate_limit import limiter
from src.api.schemas import DetectImageResponse, DetectionBoxOut, HealthResponse, PredictResponse
from src.config.settings import get_settings
from src.core.history import persist_image_event
from src.core.person_first import make_person_first_pipeline
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
@limiter.limit("30/minute")
async def predict(request: Request, file: UploadFile = File(...)) -> PredictResponse:
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
    person_first: bool = Form(False),
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
        if person_first:
            bgr = cv2.cvtColor(pil_to_numpy(image), cv2.COLOR_RGB2BGR)
            pipeline = make_person_first_pipeline()
            height, width = bgr.shape[:2]
            pf_results = pipeline.process_frame(bgr, use_tracking=False)

            detect_boxes: list[DetectionBoxOut] = []
            for i, r in enumerate(pf_results):
                bw = r.helmet_x2 - r.helmet_x1
                bh = r.helmet_y2 - r.helmet_y1
                if bw <= 1 or bh <= 1:
                    continue
                detect_boxes.append(DetectionBoxOut(
                    id=f"box_{i}",
                    class_name=r.helmet_class,
                    confidence=r.helmet_conf,
                    x=r.helmet_x1 / width,
                    y=r.helmet_y1 / height,
                    width=bw / width,
                    height=bh / height,
                    x1=r.helmet_x1,
                    y1=r.helmet_y1,
                    x2=r.helmet_x2,
                    y2=r.helmet_y2,
                ))

            person_display_boxes: list[DetectionBoxOut] = []
            for j, (px1, py1, px2, py2, pconf, _tid) in enumerate(pipeline._last_persons):
                bw = px2 - px1
                bh = py2 - py1
                if bw <= 1 or bh <= 1:
                    continue
                person_display_boxes.append(DetectionBoxOut(
                    id=f"person_{j}",
                    class_name="person",
                    confidence=pconf,
                    x=px1 / width,
                    y=py1 / height,
                    width=bw / width,
                    height=bh / height,
                    x1=px1,
                    y1=py1,
                    x2=px2,
                    y2=py2,
                ))

            all_boxes = detect_boxes + person_display_boxes
        else:
            detect_boxes = predictor.detect_image(pil_to_numpy(image))
            all_boxes = detect_boxes
    except Exception as exc:
        logger.exception("Inference failed for /api/detect/image.")
        raise HTTPException(status_code=500, detail="Inference failed.") from exc

    event_type = classify_event(detect_boxes)
    is_video_frame = bool(file.filename and file.filename.startswith("frame"))
    if is_video_frame or event_type == "NONE":
        return DetectImageResponse(boxes=all_boxes, event_type=event_type)

    history_event = persist_image_event(
        image=image,
        boxes=detect_boxes,
        source=source or file.filename or "Uploaded image",
        event_type=event_type,
    )

    return DetectImageResponse(
        boxes=all_boxes,
        global_image_url=history_event.global_image_url if history_event else None,
        crop_image_urls=history_event.crop_image_urls if history_event else [],
        event_type=event_type,
        history_event_id=history_event.id if history_event else None,
    )
