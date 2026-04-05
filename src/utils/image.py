"""Image loading, encoding, and drawing utilities."""

from __future__ import annotations

from io import BytesIO
import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from src.utils.detection import detection_color

logger = logging.getLogger(__name__)


def decode_image_bytes(raw_bytes: bytes) -> Image.Image:
    """Decode uploaded image bytes into a PIL RGB image."""
    try:
        return Image.open(BytesIO(raw_bytes)).convert("RGB")
    except Exception as exc:
        logger.warning("Pillow could not decode uploaded image: %s", exc)

    try:
        image_array = np.frombuffer(raw_bytes, np.uint8)
        decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if decoded is None:
            raise ValueError("cv2.imdecode returned None")
        rgb_image = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb_image)
    except Exception as exc:
        logger.exception("OpenCV could not decode uploaded image.")
        raise ValueError("Unable to decode uploaded image.") from exc


def save_pil_image(image: Image.Image, path: Path) -> None:
    """Persist a PIL image as a JPEG file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG", quality=90)


def pil_to_numpy(image: Image.Image) -> np.ndarray:
    """Convert a PIL image into a NumPy RGB array."""
    return np.array(image)


def clamp_bbox(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    """Clamp a bounding box so it fits within the image bounds."""
    x1_i, y1_i, x2_i, y2_i = map(int, [x1, y1, x2, y2])
    x1_i = max(0, min(x1_i, width - 1))
    y1_i = max(0, min(y1_i, height - 1))
    x2_i = max(0, min(x2_i, width))
    y2_i = max(0, min(y2_i, height))
    return x1_i, y1_i, x2_i, y2_i


def draw_detection(
    frame: np.ndarray,
    class_name: str,
    confidence: float,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    track_id: int | None = None,
) -> None:
    """Draw a labeled detection box on a frame."""
    color = detection_color(class_name)
    label = f"{class_name} {confidence:.2f}"
    if track_id is not None:
        label = f"ID {track_id} | {label}"

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(
        frame,
        label,
        (x1, max(0, y1 - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        1,
        cv2.LINE_AA,
    )


def encode_jpeg(frame: np.ndarray) -> bytes | None:
    """Encode a frame into JPEG bytes for MJPEG streaming."""
    success, jpeg = cv2.imencode(".jpg", frame)
    if not success:
        return None
    return jpeg.tobytes()
