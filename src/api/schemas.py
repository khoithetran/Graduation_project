"""Pydantic request and response models for the backend API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DetectionBoxOut(BaseModel):
    """Normalized detection box returned by inference endpoints."""

    id: str
    class_name: str
    confidence: float
    x: float
    y: float
    width: float
    height: float
    x1: int
    y1: int
    x2: int
    y2: int


class PredictResponse(BaseModel):
    """Response model for the generic predict endpoint."""

    detections: list[DetectionBoxOut]


class DetectImageResponse(BaseModel):
    """Response model for the legacy image detection endpoint."""

    boxes: list[DetectionBoxOut]
    global_image_url: Optional[str] = None
    crop_image_urls: list[str] = Field(default_factory=list)
    event_type: str
    history_event_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Service health response."""

    status: str
    model_loaded: bool
    model_path: str
    device: str
    model_format: str


class HistoryEvent(BaseModel):
    """Persisted history event."""

    id: str
    timestamp: str
    source: str
    type: str
    global_image_url: str
    crop_image_urls: list[str]
    num_violators: int


class HistoryLatestResponse(BaseModel):
    """Latest matching history event wrapper."""

    event: Optional[HistoryEvent] = None


class VideoDetectResponse(BaseModel):
    """Offline video processing response."""

    total_frames: int
    fps_input: float
    fps_used: float
    window_size: int
    violation_events: int
    suspicion_events: int
    events: list[HistoryEvent]


class UploadVideoResponse(BaseModel):
    """Response after a video upload."""

    video_id: str
    file_name: str


class LiveStartResponse(BaseModel):
    """Response after registering a live stream."""

    live_id: str
    source: str


class AutoLabelBox(BaseModel):
    """Auto-labeled box used for the update dataset review flow."""

    id: str
    class_name: str
    class_id: int
    confidence: float
    xc: float
    yc: float
    width: float
    height: float
    x: float
    y: float
    x1: float
    y1: float
    x2: float
    y2: float


class UpdateCandidatesResponse(BaseModel):
    """Paged response for update candidates."""

    total: int
    page: int
    page_size: int
    items: list[HistoryEvent]


class UpdateAutoLabelResponse(BaseModel):
    """Auto-label preview response."""

    event_id: str
    image_url: str
    boxes: list[AutoLabelBox]
    class_counts: dict[str, int]


class UpdateMarkRequest(BaseModel):
    """Request payload for approving or rejecting an update candidate."""

    event_id: str
    accepted: bool


class UpdateMarkResponse(BaseModel):
    """Response for update candidate review actions."""

    ok: bool
    accepted: bool
    image_path: Optional[str] = None
    label_path: Optional[str] = None
    num_boxes: Optional[int] = None


class UpdateStartResponse(BaseModel):
    """Response for the placeholder fine-tune trigger endpoint."""

    ok: bool
    started: bool
    message: str
    count: int
    required: int


class UpdateStatusResponse(BaseModel):
    """Response describing the current update dataset size."""

    num_images: int
    threshold: int
    ready: bool


class WebcamDetectionOut(BaseModel):
    """Single detection box returned per webcam frame."""

    class_name: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int


class LiveAlertOut(BaseModel):
    """Violation alert from a live stream (webcam or IP camera)."""

    id: str
    wall_time: str
    class_name: str
    confidence: float
    crop: str


class WebcamFrameResponse(BaseModel):
    """Response for a single processed webcam frame."""

    detections: list[WebcamDetectionOut]
    alerts: list[LiveAlertOut]
